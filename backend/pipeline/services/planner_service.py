import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from pipeline.infrastructure.mcp_bridge import MCPBridge
from pipeline.infrastructure.ai_client import AiClientFactory
from pipeline.infrastructure.login_helper import SessionManager
from pipeline.utils.credential_manager import CredentialManager
from pipeline.utils.agent_utils import AgentUtils
from pipeline.knowledge.heuristics_loader import get_heuristics
from pipeline.knowledge.dashboard_facts import facts_for_all_mentioned_pages, PAGE_FACTS
from pipeline.constants import MAX_PLANNER_ITERATIONS, PLANNER_NUDGE_THRESHOLD
from pipeline.prompts.planner_prompt import build_planner_system_prompt
from pipeline.tools.planner_tools import PLANNER_CUSTOM_TOOLS
from pipeline.transforms.plan_validator import validate_plan_content


class PlannerService:

    ALLOWED_MCP = {
        'browser_navigate',
        'browser_snapshot',
        'browser_click',
        'browser_hover',
        'browser_wait_for',
    }

    @staticmethod
    def run(test_plan, plan_path: str) -> None:
        ai = AiClientFactory.create()
        openai = ai['client']
        model = ai['model']
        bridge = MCPBridge()
        snapshot_cache = {}

        try:
            mcp_tools = bridge.list_tools()
            SessionManager.ensure_mcp_authenticated(bridge, CredentialManager.get_all()['dashboard_url'])

            filtered_mcp = [t for t in mcp_tools if t['name'] in PlannerService.ALLOWED_MCP]
            all_tools = PLANNER_CUSTOM_TOOLS + [AgentUtils.mcp_to_openai_tool(t) for t in filtered_mcp]

            heuristics = get_heuristics()
            plan_text = ' '.join(
                [test_plan.title]
                + [text for f in test_plan.flows for text in [f.name, f.description] + f.steps]
            )
            facts = facts_for_all_mentioned_pages(plan_text)
            print(
                f'[heuristics] Injected dashboard heuristics ({len(heuristics)} chars) '
                f'+ {len(facts) if facts else 0} chars of page facts into planner prompt'
            )
            planner_system_prompt = build_planner_system_prompt(
                heuristics, facts, CredentialManager.get_publisher()
            )

            messages = [
                {'role': 'system', 'content': planner_system_prompt},
                {
                    'role': 'user',
                    'content': (
                        f'Here is the TestPlan to implement:\n\n'
                        f'{json.dumps(PlannerService._to_dict(test_plan), indent=2)}\n\n'
                        f'Start immediately by calling planner_setup_page with url: {test_plan.url}'
                    ),
                },
            ]

            plan_saved = False
            setup_page_count = 0
            last_setup_url = ''
            plan_rejection_count = 0
            plan_just_rejected = False
            snapshot_call_count = 0
            # Each flow needs a genuine navigate+snapshot pass on its target page (plus a few
            # combobox snapshots), so scale the snapshot budget with flow count instead of a flat
            # cap — capped below MAX_PLANNER_ITERATIONS so a runaway snapshot loop still gets cut off.
            snapshot_budget = min(12, 4 + 3 * max(1, len(test_plan.flows)))

            for iteration in range(MAX_PLANNER_ITERATIONS):
                response = AgentUtils.call_with_retry(lambda: openai.chat.completions.create(
                    model=model,
                    max_tokens=4096,
                    temperature=0.2,
                    messages=messages,
                    tools=all_tools,
                    tool_choice='required',
                ))

                msg = response.choices[0].message
                messages.append(msg.model_dump())

                tool_calls = msg.tool_calls
                if not tool_calls or len(tool_calls) == 0:
                    if not plan_saved:
                        print(f'Planner returned text without tool calls at iteration {iteration}. Nudging...')
                        if plan_rejection_count > 0:
                            nudge = (
                                'Your plan was rejected because you used an unverified URL or missed a required field. '
                                'You MUST click through the UI to find the real page first:\n'
                                '1. Call browser_snapshot (no args) to see the current page and sidebar\n'
                                '2. Find the feature you need in the sidebar — look for its link or "Create" button\n'
                                '3. Call browser_click on that element to navigate there\n'
                                '4. Call browser_snapshot again to see the form and confirm the URL\n'
                                '5. Only then call planner_save_plan with steps using that confirmed URL'
                            )
                        else:
                            nudge = (
                                'You must use tools to complete the plan. '
                                'Call browser_snapshot (no args) to see the current page. '
                                'If you do not know the URL for the feature, use browser_click on the sidebar link '
                                'or Create button to navigate there first.'
                            )
                        messages.append({'role': 'user', 'content': nudge})
                        continue
                    break

                tool_results = []
                plan_just_rejected = False

                for call in tool_calls:
                    name = call.function.name
                    args = AgentUtils.parse_tool_args(call.function.arguments)
                    print(f'Planner calling: {name}({json.dumps(args)[:120]})')
                    if name == 'browser_snapshot':
                        snapshot_call_count += 1
                    result = PlannerService._handle_tool(
                        name, args, bridge, test_plan, plan_path, snapshot_cache,
                        planner_system_prompt, setup_page_count, last_setup_url,
                        plan_rejection_count,
                    )
                    # _handle_tool returns a tuple (result_str, updated counters)
                    result_str, setup_page_count, last_setup_url, plan_just_rejected_flag, plan_saved_flag = result
                    if plan_just_rejected_flag:
                        plan_rejection_count += 1
                        plan_just_rejected = True
                    if plan_saved_flag:
                        plan_saved = True
                    max_chars = AgentUtils.MAX_SNAPSHOT_RESULT_CHARS if name == 'browser_snapshot' else None
                    tool_results.append({
                        'role': 'tool',
                        'tool_call_id': call.id,
                        'content': AgentUtils.truncate_result(result_str, max_chars),
                    })

                messages.extend(tool_results)

                # Hard stop against snapshot loops: repeatedly calling browser_snapshot wastes API
                # iterations and never advances the plan. After the per-flow budget, force the write.
                if not plan_saved and snapshot_call_count >= snapshot_budget:
                    messages.append({
                        'role': 'user',
                        'content': (
                            'STOP calling browser_snapshot — you have snapshotted enough and are wasting '
                            'iterations. Call planner_save_plan NOW with the complete markdown plan, using the '
                            'Verified Page Facts for field labels (for an edit flow: the create-page fields plus '
                            'the "Save Changes" button). Do not call any tool other than planner_save_plan.'
                        ),
                    })

                if plan_just_rejected:
                    messages.append({
                        'role': 'user',
                        'content': (
                            'Your plan was rejected — see the reason above. First check whether the fix is '
                            'already available to you: a URL you already visited earlier in this conversation '
                            '(check your own prior planner_setup_page / browser_click calls and their results), '
                            'or a fact already stated in your system prompt (KNOWN FACTS / Verified Page Facts). '
                            'If so, just correct the plan text to match it and call planner_save_plan again — '
                            'do NOT re-navigate or re-explore for information you already have.\n'
                            'Only click through the UI from scratch if the fix genuinely requires something you '
                            'have not yet observed (a real URL, field label, or option text):\n'
                            '1. Call browser_snapshot (no args) to see the sidebar\n'
                            '2. Find the target feature — look for its sidebar link or "Create" button\n'
                            '3. Call browser_click on that element\n'
                            '4. Call browser_snapshot immediately after\n'
                            '5. Write the plan using the confirmed URL/field from this page'
                        ),
                    })

                nudge_iteration = int(MAX_PLANNER_ITERATIONS * PLANNER_NUDGE_THRESHOLD) - 1
                if not plan_saved and iteration == nudge_iteration:
                    nudge_msg = (
                        'Your plan has been rejected. You STILL need to click the feature button '
                        'in the sidebar to discover the real URL. '
                        'Call browser_snapshot, find the Create button or link for the target feature, '
                        'call browser_click on it, snapshot again, then write the plan with the confirmed URL.'
                    ) if plan_rejection_count > 0 else (
                        'You have explored enough pages. Call planner_save_plan NOW with the complete '
                        'markdown plan. Use KNOWN FACTS from your system prompt for any details you did '
                        'not directly observe.'
                    )
                    messages.append({'role': 'user', 'content': nudge_msg})

                messages = AgentUtils.prune_history(messages, 10)
                if plan_saved:
                    break

            if not plan_saved:
                raise RuntimeError(
                    f'Planner hit the {MAX_PLANNER_ITERATIONS}-iteration limit without saving a plan.\n'
                    'The model may be stuck in a loop. Try running again or simplify your prompt.'
                )
            print(f'Planner complete — plan saved to {plan_path}')

        finally:
            bridge.close()

    @staticmethod
    def _handle_tool(name, args, bridge, test_plan, plan_path, snapshot_cache,
                     planner_system_prompt, setup_page_count, last_setup_url, plan_rejection_count):
        plan_just_rejected = False
        plan_saved = False
        result = ''

        if name == 'planner_setup_page':
            raw_url = str(args.get('url', ''))
            target_url = f"{test_plan.url.rstrip('/')}{raw_url}" if raw_url.startswith('/') else raw_url
            setup_page_count += 1

            if setup_page_count > 1 and target_url == last_setup_url:
                current_snapshot = ''
                try:
                    current_snapshot = bridge.call_tool('browser_snapshot', {})
                except Exception:
                    pass
                try:
                    landed_path = urlparse(target_url).path
                except Exception:
                    landed_path = target_url
                is_known_target = any(p in landed_path for p in PAGE_FACTS.keys())
                if is_known_target:
                    result = (
                        f'Already on {target_url} — this IS a known target page. '
                        f'Do NOT call planner_setup_page again. Using the snapshot below, VERIFY the live '
                        f'form before writing: (1) list EVERY required field — any textbox/combobox whose '
                        f'accessible name ends in "*"; (2) confirm the submit button (Publish / Save Changes / '
                        f'Save as Draft / Save / Save Category) is present and note its EXACT name. '
                        f'Then call planner_save_plan with a plan that fills EVERY required field and waits '
                        f'expect(get_by_role("button", name="<name>")).to_be_enabled(timeout=15000) before '
                        f'clicking it (for an edit flow, use the create-page fields plus the "Save Changes" button).\n\n'
                        f'Current snapshot:\n{current_snapshot[:2000]}'
                    )
                else:
                    result = (
                        f'Already on {target_url}. Do NOT call planner_setup_page again. '
                        f'Look at the snapshot below — find the feature you need in the sidebar '
                        f'and call browser_click on its link or "Create" button to navigate to it.\n\n'
                        f'Current snapshot:\n{current_snapshot[:2000]}'
                    )
            elif setup_page_count > 6:
                result = (
                    f'Too many page navigations ({setup_page_count}). '
                    f'Use KNOWN FACTS from your system prompt and call planner_save_plan now.'
                )
            else:
                last_setup_url = target_url
                try:
                    bridge.call_tool('browser_navigate', {'url': target_url})
                    try:
                        snapshot = bridge.call_tool('browser_snapshot', {})
                        cache_key = target_url
                        try:
                            url_result = bridge.call_tool('browser_evaluate', {'expression': 'window.location.href'})
                            url_match = re.search(r'https?://[^\s\'"]+', url_result)
                            if url_match:
                                cache_key = url_match.group(0)
                        except Exception:
                            pass
                        snapshot_cache[cache_key] = snapshot
                        try:
                            landed_path = urlparse(cache_key).path
                        except Exception:
                            landed_path = cache_key
                        if '/login' in landed_path:
                            result = (
                                f'WARNING: Navigating to {target_url} redirected to the login page. '
                                f'This feature is NOT available for this publisher.'
                            )
                        else:
                            result = f'Navigated to {target_url}. Page snapshot:\n{AgentUtils.truncate_result(snapshot, 3000)}'
                    except Exception:
                        result = f'Navigated to {target_url}. Call browser_snapshot (no args) to see the page.'
                except Exception as err:
                    result = f'ERROR navigating to {target_url}: {err}'

        elif name == 'planner_save_plan':
            content = str(args.get('content', ''))
            rejection_issues = validate_plan_content(content, snapshot_cache, planner_system_prompt)
            if rejection_issues:
                plan_just_rejected = True
                print(f'[planner] Plan rejected (attempt {plan_rejection_count + 1}): {rejection_issues}')
                result = f'PLAN REJECTED — {rejection_issues}.'
            else:
                os.makedirs(os.path.dirname(plan_path), exist_ok=True)
                Path(plan_path).write_text(content, encoding='utf-8')
                snapshot_path = re.sub(r'plan\.md$', 'plan-snapshots.json', plan_path)
                Path(snapshot_path).write_text(json.dumps(snapshot_cache, indent=2), encoding='utf-8')
                plan_saved = True
                result = f'Plan saved to {plan_path}'

        elif name == 'browser_navigate':
            try:
                result = bridge.call_tool(name, args)
            except Exception as err:
                result = f'ERROR calling {name}: {err}'

        else:
            try:
                result = bridge.call_tool(name, args)
                if name == 'browser_snapshot':
                    # The snapshot result itself always carries "- Page URL: <url>" as its first
                    # line (confirmed across every non-error snapshot on record) — reading it
                    # directly is both simpler and more reliable than a separate browser_evaluate
                    # round-trip, whose failure used to fall back to a meaningless id()-based key
                    # that the plan validator's URL-based snapshot lookup could never match,
                    # silently letting it validate against the wrong (often stale/empty) snapshot.
                    url_match = re.search(r'^- Page URL:\s*(\S+)', result, flags=re.MULTILINE)
                    cache_key = url_match.group(1) if url_match else f'snapshot-{id(result)}'
                    snapshot_cache[cache_key] = result
            except Exception as err:
                result = f'ERROR calling {name}: {err}'

        return result, setup_page_count, last_setup_url, plan_just_rejected, plan_saved

    @staticmethod
    def _to_dict(plan) -> dict:
        return {
            'url': plan.url,
            'title': plan.title,
            'flows': [
                {
                    'id': f.id, 'name': f.name, 'description': f.description,
                    'steps': f.steps, 'assertions': f.assertions,
                }
                for f in plan.flows
            ],
            'pages': plan.pages,
        }
