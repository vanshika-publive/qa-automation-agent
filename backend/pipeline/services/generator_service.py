import json
import os
import re
from pathlib import Path

from pipeline.infrastructure.mcp_bridge import MCPBridge
from pipeline.infrastructure.ai_client import AiClientFactory
from pipeline.infrastructure.login_helper import SessionManager
from pipeline.utils.credential_manager import CredentialManager
from pipeline.utils.agent_utils import AgentUtils
from pipeline.knowledge.heuristics_loader import get_heuristics
from pipeline.knowledge.dashboard_facts import facts_for_all_mentioned_pages
from pipeline.constants import (
    MAX_GENERATOR_ITERATIONS,
    GENERATOR_NUDGE_THRESHOLD,
    GENERATOR_FINAL_WARNING_THRESHOLD,
)
from pipeline.prompts.generator_prompt import build_generator_system_prompt
from pipeline.tools.generator_tools import GENERATOR_CUSTOM_TOOLS
from pipeline.transforms.plan_parser import parse_plan_md, extract_scenario_url
from pipeline.transforms.spec_sanitizer import sanitize_spec
from pipeline.transforms.spec_validator import (
    validate_spec_semantics,
    validate_spec_data_uniqueness,
    validate_spec_matches_plan,
)


class GeneratorService:

    ALLOWED_MCP = {'browser_navigate', 'browser_snapshot', 'browser_click', 'browser_wait_for'}
    MAX_NO_TOOL_NUDGES = 3

    @staticmethod
    def run(plan_path: str, tests_dir: str) -> list:
        if not os.path.exists(plan_path):
            raise FileNotFoundError(f'Plan file not found at {plan_path}. Run the planner first.')

        plan_content = Path(plan_path).read_text(encoding='utf-8')
        scenarios = parse_plan_md(plan_content)

        snapshot_path = re.sub(r'plan\.md$', 'plan-snapshots.json', plan_path)
        plan_snapshots = {}
        if os.path.exists(snapshot_path):
            try:
                plan_snapshots = json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
                print(f'Loaded {len(plan_snapshots)} planner snapshots for generator context')
            except Exception:
                pass

        if len(scenarios) == 0:
            preview = plan_content[:500].replace('\n', '↵ ')
            raise ValueError(
                f'No scenarios found in {plan_path}.\n'
                'Expected at least one "## Flow N:" section containing a '
                '"### Scenario:" with numbered steps.\n\n'
                f'Plan preview (first 500 chars):\n  {preview}\n\n'
                'Re-run the planner to regenerate the plan.'
            )

        url_match = re.search(r'^URL:\s*(.+)$', plan_content, re.MULTILINE)
        url = url_match.group(1).strip() if url_match else CredentialManager.get_all()['dashboard_url']

        ai = AiClientFactory.create()
        openai_client = ai['client']
        model = ai['model']
        written = []

        # The planner rewrites plan.md at the start of every full pipeline run, so its mtime marks
        # "when the current plan was produced". A spec is only safe to reuse if it was written from
        # THAT plan (i.e. it is at least as new as the plan). A spec older than the plan is stale —
        # it predates a plan the planner has since improved — and reusing it silently runs outdated
        # code (this is exactly how a fixed "upload the required image" plan still executed the old
        # image-less spec and failed on a disabled Publish button). Specs written earlier in this
        # same generator run are newer than the plan, so genuine mid-run resumes still skip.
        plan_mtime = os.path.getmtime(plan_path)
        AgentUtils.reset_call_counter()
        for scenario in scenarios:
            spec_path = os.path.join(tests_dir, f'test_{scenario.file_name}.py')
            if os.path.exists(spec_path) and os.path.getmtime(spec_path) >= plan_mtime:
                print(f'Skipping up-to-date spec: test_{scenario.file_name}.py — delete it to force regenerate')
                written.append(spec_path)
                continue
            if os.path.exists(spec_path):
                print(f'Regenerating stale spec (plan is newer): test_{scenario.file_name}.py')
            print(f'Generating: {scenario.scenario_name}')
            file_path = GeneratorService._generate_scenario(
                openai_client, model, scenario, url, tests_dir, plan_snapshots
            )
            if file_path:
                written.append(file_path)

        print(f'[generator] {AgentUtils.get_token_summary()}')
        return written

    @staticmethod
    def _generate_scenario(openai_client, model, scenario, url, tests_dir, plan_snapshots=None) -> str:
        if plan_snapshots is None:
            plan_snapshots = {}

        # read_only: the generator observes the UI to write pytest code — it must never mutate the
        # live dashboard while exploring. See MCPBridge/readonly_guard.js. The runner (which runs the
        # generated spec for real) uses pytest directly, not MCPBridge, so it is unaffected.
        bridge = MCPBridge(read_only=True)
        action_log = []
        written_file = None
        no_tool_nudges = 0

        def _persist_test(raw_content, file_name_hint):
            nonlocal written_file
            rejection_message = (
                validate_spec_data_uniqueness(raw_content)
                or validate_spec_semantics(raw_content)
                or validate_spec_matches_plan(raw_content, scenario.steps)
            )
            if rejection_message:
                print('  [rejected] ' + ' | '.join(
                    ln.strip() for ln in rejection_message.splitlines() if ln.strip()
                )[:600])
                return rejection_message
            file_name = re.sub(r'[^a-zA-Z0-9._-]', '', os.path.basename(str(file_name_hint or '')))
            if not file_name.endswith('.py'):
                file_name = re.sub(r'\.(ts|spec\.ts|spec)$', '', file_name)
                if not file_name.startswith('test_'):
                    file_name = f'test_{file_name}'
                file_name = f'{file_name}.py'
            file_path = os.path.join(tests_dir, file_name)
            os.makedirs(tests_dir, exist_ok=True)
            sanitized = sanitize_spec(raw_content, scenario.scenario_name)
            Path(file_path).write_text(sanitized, encoding='utf-8')
            written_file = file_path
            return f'Written: {file_path}'

        try:
            mcp_tools = bridge.list_tools()
            filtered_mcp = [t for t in mcp_tools if t['name'] in GeneratorService.ALLOWED_MCP]
            all_tools = GENERATOR_CUSTOM_TOOLS + [AgentUtils.mcp_to_openai_tool(t) for t in filtered_mcp]

            SessionManager.ensure_mcp_authenticated(bridge, CredentialManager.get_all()['dashboard_url'])

            scenario_url = extract_scenario_url(scenario.steps, url)
            snapshot_entries = list(plan_snapshots.items())
            snapshot_context = (
                '\n\nARIA SNAPSHOTS from planner session '
                '(use as ground truth for locators — re-browse only if you need a page not listed here):\n'
                + '\n'.join(f'\n--- Page: {pu} ---\n{snap[:3000]}' for pu, snap in snapshot_entries)
            ) if snapshot_entries else ''

            goto_paths = re.findall(
                r"page\.goto\(['\"`](https?:\/\/[^'\"`]+|\/[^'\"`]+)['\"`]\)", '\n'.join(scenario.steps)
            )
            pages_to_browse = (
                [p if p.startswith('http') else f'{url}{p}' for p in goto_paths] if goto_paths else [scenario_url]
            )

            workflow_lines = []
            for i, p in enumerate(pages_to_browse):
                workflow_lines.append(f'{i * 2 + 1}. generator_setup_page(url: "{p}")')
                workflow_lines.append(f'{i * 2 + 2}. browser_snapshot({{}})')
            workflow_lines.append(f'{len(pages_to_browse) * 2 + 1}. generator_write_test(fileName, content)')

            user_message = (
                f'Write the Playwright test for this scenario:\n\n'
                f'Scenario: {scenario.scenario_name}\n'
                f'Flow: {scenario.flow_name}\n'
                f'File: test_{scenario.file_name}.py\n\n'
                f'Plan steps (translate these directly into Playwright code):\n'
                + '\n'.join(f'{i + 1}. {s}' for i, s in enumerate(scenario.steps))
                + '\n\nExpected assertions:\n'
                + '\n'.join(f'- {e}' for e in scenario.expected)
                + f'\n\nDashboard base URL: {url}\n'
                f"Pages this scenario visits: {', '.join(pages_to_browse)}\n\n"
                f'Follow the workflow:\n' + '\n'.join(workflow_lines)
                + '\n\nThe plan steps above are your source of truth for locators and actions. '
                f'Translate them into Python pytest-playwright code using the rules in your system prompt.'
                + snapshot_context
            )

            heuristics = get_heuristics()
            scenario_text = ' '.join([scenario.scenario_name, scenario.flow_name] + scenario.steps)
            facts = facts_for_all_mentioned_pages(scenario_text)
            print(
                f'[heuristics] Injected dashboard heuristics ({len(heuristics)} chars) '
                f'+ {len(facts) if facts else 0} chars of page facts into generator prompt'
            )
            generator_system_prompt = build_generator_system_prompt(
                heuristics, facts, CredentialManager.get_publisher()
            )

            messages = [
                {'role': 'system', 'content': generator_system_prompt},
                {'role': 'user', 'content': user_message},
            ]

            for iteration in range(MAX_GENERATOR_ITERATIONS):
                response = AgentUtils.call_with_retry(lambda: openai_client.chat.completions.create(
                    model=model,
                    max_tokens=4096,
                    temperature=0,
                    messages=messages,
                    tools=all_tools,
                    tool_choice='auto',
                ))

                msg = response.choices[0].message
                messages.append(msg.model_dump())

                tool_calls = msg.tool_calls
                if not tool_calls or len(tool_calls) == 0:
                    if written_file:
                        break
                    salvaged = GeneratorService._extract_python_code(msg.content or '')
                    if salvaged:
                        result_status = _persist_test(salvaged, f'test_{scenario.file_name}.py')
                        print(f'  [salvage] recovered test from assistant message — {result_status}')
                        if written_file:
                            break
                        feedback = (
                            f'{result_status}\nYou returned the test as a chat message instead of calling '
                            'generator_write_test. Fix the issue above and call generator_write_test '
                            'with `fileName` and the corrected `content`.'
                        )
                    else:
                        feedback = (
                            'You replied without calling a tool and no test has been written yet. '
                            'Call generator_write_test now with `fileName` and `content`.'
                        )
                    no_tool_nudges += 1
                    if no_tool_nudges > GeneratorService.MAX_NO_TOOL_NUDGES:
                        break
                    messages.append({'role': 'user', 'content': feedback})
                    continue

                tool_results = []
                for call in tool_calls:
                    name = call.function.name
                    args = AgentUtils.parse_tool_args(call.function.arguments)
                    print(f'  -> {name}')
                    result = ''

                    if name == 'generator_setup_page':
                        action_log.clear()
                        bridge.call_tool('browser_navigate', {'url': str(args.get('url', ''))})
                        action_log.append(f"navigate: {args.get('url', '')}")
                        result = (
                            f"Navigated to {args.get('url', '')}. Action log reset. "
                            f'Call browser_snapshot (no args) to see the page.'
                        )
                    elif name == 'generator_read_log':
                        result = json.dumps(action_log, indent=2)
                    elif name == 'generator_discover_limits':
                        try:
                            result = bridge.call_tool('browser_evaluate', {
                                'function': (
                                    '() => {\n'
                                    '  return Array.from(document.querySelectorAll(\''
                                    'input[type="text"], input:not([type]), textarea\'))\n'
                                    '    .filter(el => !el.readOnly && !el.disabled && el.offsetParent !== null)\n'
                                    '    .map(el => ({\n'
                                    '      label: el.getAttribute(\'aria-label\') || '
                                    'el.getAttribute(\'placeholder\') || el.name || el.id || \'(unlabelled)\',\n'
                                    '      maxLength: el.maxLength > 0 ? el.maxLength : null,\n'
                                    '      minLength: el.minLength > 0 ? el.minLength : null,\n'
                                    '      required: el.required,\n'
                                    '    }));\n'
                                    '}'
                                ),
                            })
                        except Exception as err:
                            result = f'ERROR: {err}'
                        result = (
                            f'Field constraints (DOM read-only, no interaction):\n{result}\n\n'
                            'safe_fill() and safe_sequential_fill() auto-truncate to DOM maxLength at runtime.'
                        )
                    elif name == 'generator_write_test':
                        result = _persist_test(str(args.get('content', '')), args.get('fileName', ''))
                    else:
                        try:
                            result = bridge.call_tool(name, args)
                        except Exception as err:
                            result = f'ERROR calling {name}: {err}'
                        action_log.append(f'{name}: {json.dumps(args)[:120]}')

                    max_chars = AgentUtils.MAX_SNAPSHOT_RESULT_CHARS if name == 'browser_snapshot' else None
                    tool_results.append({
                        'role': 'tool',
                        'tool_call_id': call.id,
                        # Surface any open overlay (popover/modal/dropdown) ahead of truncation —
                        # see AgentUtils.surface_overlays; portaled overlays are otherwise cut off
                        # on content-heavy pages.
                        'content': AgentUtils.truncate_result(
                            AgentUtils.surface_overlays(result), max_chars
                        ),
                    })

                messages.extend(tool_results)

                nudge_iteration = int(MAX_GENERATOR_ITERATIONS * GENERATOR_NUDGE_THRESHOLD) - 1
                if not written_file and iteration == nudge_iteration:
                    messages.append({
                        'role': 'user',
                        'content': (
                            'You are past 70% of your iteration budget. If you have not yet called '
                            'generator_discover_limits, call it now. '
                            'Then immediately call generator_write_test with the complete Python test.'
                        ),
                    })

                final_warning_iteration = int(MAX_GENERATOR_ITERATIONS * GENERATOR_FINAL_WARNING_THRESHOLD) - 1
                if not written_file and iteration == final_warning_iteration:
                    messages.append({
                        'role': 'user',
                        'content': (
                            'FINAL WARNING: Call generator_write_test NOW with the complete Python test. '
                            'Use the plan steps and KNOWN DASHBOARD FACTS from your system prompt.'
                        ),
                    })

                messages = AgentUtils.prune_history(messages, AgentUtils.DEFAULT_KEEP_TURNS)
                if written_file:
                    break

            if written_file:
                print(f'  Written: {written_file}')
            else:
                print(f'  generator_write_test was never called for scenario: {scenario.scenario_name}')

            return written_file

        finally:
            bridge.close()

    @staticmethod
    def _extract_python_code(text: str):
        if not text:
            return None
        fence = re.search(r'```(?:python|py)?\s*\n(.*?)```', text, flags=re.DOTALL)
        candidate = fence.group(1).strip() if fence else text.strip()
        if 'def test_' in candidate and ('import' in candidate or 'page' in candidate):
            return candidate
        return None
