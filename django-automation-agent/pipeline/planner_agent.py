import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from pipeline.mcp_bridge import MCPBridge
from pipeline.ai_client import create_ai_client
from pipeline.credential_manager import get_credentials
from pipeline.login_helper import ensure_mcp_authenticated
from pipeline.agent_utils import (
    mcp_to_openai_tool,
    truncate_result,
    prune_history,
    call_with_retry,
    parse_tool_args,
)
from pipeline.knowledge.heuristics_loader import get_heuristics
from pipeline.knowledge.dashboard_facts import facts_for_all_mentioned_pages, PAGE_FACTS
from pipeline.constants import MAX_PLANNER_ITERATIONS, PLANNER_NUDGE_THRESHOLD
from pipeline.prompts.planner_prompt import build_planner_system_prompt
from pipeline.tools.planner_tools import PLANNER_CUSTOM_TOOLS
from pipeline.transforms.plan_validator import validate_plan_content


PLANNER_ALLOWED_MCP = {
    'browser_navigate',
    'browser_snapshot',
    'browser_click',
    'browser_hover',
    'browser_wait_for',
}


def run_planner_agent(test_plan, plan_path: str) -> None:
    """
    Run the planner agent loop: browse the live dashboard, discover UI structure,
    and write a concrete markdown test plan to plan_path.
    """
    ai = create_ai_client()
    openai = ai['client']
    model = ai['model']
    bridge = MCPBridge()
    snapshot_cache = {}

    try:
        mcp_tools = bridge.list_tools()
        ensure_mcp_authenticated(bridge, get_credentials()['dashboard_url'])

        # Planner is read-only: navigate, snapshot, click. Form filling is the test's job.
        filtered_mcp = [t for t in mcp_tools if t['name'] in PLANNER_ALLOWED_MCP]
        all_tools = PLANNER_CUSTOM_TOOLS + [mcp_to_openai_tool(t) for t in filtered_mcp]

        heuristics = get_heuristics()
        # Concatenate every TestPlan text field so facts_for_all_mentioned_pages catches every mentioned entity.
        plan_text = ' '.join(
            [test_plan.title]
            + [
                text
                for f in test_plan.flows
                for text in [f.name, f.description] + f.steps
            ]
        )
        facts = facts_for_all_mentioned_pages(plan_text)
        print(
            f'[heuristics] Injected dashboard heuristics ({len(heuristics)} chars) '
            f'+ {len(facts) if facts else 0} chars of page facts into planner prompt'
        )
        planner_system_prompt = build_planner_system_prompt(heuristics, facts)

        messages = [
            {'role': 'system', 'content': planner_system_prompt},
            {
                'role': 'user',
                'content': (
                    f'Here is the TestPlan to implement:\n\n'
                    f'{json.dumps(_test_plan_to_dict(test_plan), indent=2)}\n\n'
                    f'Start immediately by calling planner_setup_page with url: {test_plan.url}'
                ),
            },
        ]

        plan_saved = False
        setup_page_count = 0
        last_setup_url = ''
        plan_rejection_count = 0
        plan_just_rejected = False

        for iteration in range(MAX_PLANNER_ITERATIONS):
            response = call_with_retry(lambda: openai.chat.completions.create(
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
                args = parse_tool_args(call.function.arguments)

                print(f'Planner calling: {name}({json.dumps(args)[:120]})')

                result = ''

                if name == 'planner_setup_page':
                    raw_url = str(args.get('url', ''))
                    if raw_url.startswith('/'):
                        target_url = f"{test_plan.url.rstrip('/')}{raw_url}"
                    else:
                        target_url = raw_url
                    setup_page_count += 1

                    if setup_page_count > 1 and target_url == last_setup_url:
                        print('planner_setup_page called again for same URL — returning current state')
                        current_snapshot = ''
                        try:
                            current_snapshot = bridge.call_tool('browser_snapshot', {})
                        except Exception:
                            pass

                        # If already on a known target page, avoid the click-through loop.
                        try:
                            landed_path = urlparse(target_url).path
                        except Exception:
                            landed_path = target_url

                        is_known_target = any(p in landed_path for p in PAGE_FACTS.keys())

                        if is_known_target:
                            result = (
                                f'Already on {target_url} — this IS a known target page '
                                f'(it has Verified Page Facts in your system prompt). '
                                f'Do NOT call planner_setup_page again. Do NOT try to navigate elsewhere. '
                                f'You have everything you need: the snapshot below + the Verified Page Facts for this URL. '
                                f'Write the plan now by calling planner_save_plan with concrete steps '
                                f'using the field labels from the Verified Page Facts.\n\n'
                                f'Current snapshot:\n{current_snapshot[:2000]}'
                            )
                        else:
                            result = (
                                f'Already on {target_url}. Do NOT call planner_setup_page again. '
                                f'Look at the snapshot below — find the feature you need in the sidebar '
                                f'and call browser_click on its link or "Create" button to navigate to it. '
                                f'Do NOT write the plan until you have clicked through to the actual feature page.\n\n'
                                f'Current snapshot:\n{current_snapshot[:2000]}'
                            )

                    elif setup_page_count > 6:
                        result = (
                            f'Too many page navigations ({setup_page_count}). '
                            f'Use KNOWN FACTS from your system prompt for remaining details '
                            f'and call planner_save_plan now.'
                        )
                    else:
                        last_setup_url = target_url
                        try:
                            bridge.call_tool('browser_navigate', {'url': target_url})
                            # Auto-snapshot so the URL lands in snapshot_cache even if the planner jumps away next.
                            try:
                                snapshot = bridge.call_tool('browser_snapshot', {})
                                cache_key = target_url
                                try:
                                    url_result = bridge.call_tool(
                                        'browser_evaluate',
                                        {'expression': 'window.location.href'},
                                    )
                                    url_match = re.search(r'https?://[^\s\'"]+', url_result)
                                    if url_match:
                                        cache_key = url_match.group(0)
                                except Exception:
                                    pass
                                snapshot_cache[cache_key] = snapshot

                                # Silent login redirect = feature not available for this publisher.
                                try:
                                    landed_path = urlparse(cache_key).path
                                except Exception:
                                    landed_path = cache_key

                                if '/login' in landed_path:
                                    result = (
                                        f'WARNING: Navigating to {target_url} redirected to the login page '
                                        f'({cache_key}). '
                                        f'This feature is NOT available for this publisher — do NOT write '
                                        f'test steps for it. '
                                        f'Instead: take a snapshot of the home page to see which features ARE '
                                        f'in the sidebar, and only write plans for pages that exist in the sidebar '
                                        f'or that you have personally confirmed load correctly.'
                                    )
                                else:
                                    result = (
                                        f'Navigated to {target_url}. Page snapshot:\n'
                                        f'{truncate_result(snapshot, 3000)}'
                                    )
                            except Exception:
                                result = (
                                    f'Navigated to {target_url}. '
                                    f'Call browser_snapshot (no args) to see the page.'
                                )
                        except Exception as err:
                            result = f'ERROR navigating to {target_url}: {err}'

                elif name == 'planner_save_plan':
                    content = str(args.get('content', ''))
                    rejection_issues = validate_plan_content(
                        content, snapshot_cache, planner_system_prompt
                    )

                    if rejection_issues:
                        plan_rejection_count += 1
                        plan_just_rejected = True
                        print(
                            f'[planner] Plan rejected (attempt {plan_rejection_count}): '
                            f'{rejection_issues}'
                        )
                        result = f'PLAN REJECTED — {rejection_issues}.'
                    else:
                        os.makedirs(os.path.dirname(plan_path), exist_ok=True)
                        Path(plan_path).write_text(content, encoding='utf-8')
                        snapshot_path = re.sub(r'plan\.md$', 'plan-snapshots.json', plan_path)
                        Path(snapshot_path).write_text(
                            json.dumps(snapshot_cache, indent=2), encoding='utf-8'
                        )
                        plan_saved = True
                        result = f'Plan saved to {plan_path}'

                elif name == 'browser_navigate':
                    # Hallucinated URLs are caught at save time by unvalidatedPaths; blocking here
                    # caused loops when real-but-unknown routes were explored.
                    try:
                        result = bridge.call_tool(name, args)
                    except Exception as err:
                        result = f'ERROR calling {name}: {err}'

                else:
                    try:
                        result = bridge.call_tool(name, args)
                        if name == 'browser_snapshot':
                            try:
                                url_result = bridge.call_tool(
                                    'browser_evaluate',
                                    {'expression': 'window.location.href'},
                                )
                                url_match = re.search(r'https?://[^\s\'"]+', url_result)
                                cache_key = url_match.group(0) if url_match else f'snapshot-{id(result)}'
                                snapshot_cache[cache_key] = result
                            except Exception:
                                pass
                    except Exception as err:
                        result = f'ERROR calling {name}: {err}'

                tool_results.append({
                    'role': 'tool',
                    'tool_call_id': call.id,
                    'content': truncate_result(result),
                })

            messages.extend(tool_results)

            # After rejection, inject click-through directive AFTER tool results
            # so the LLM sees both together.
            if plan_just_rejected:
                messages.append({
                    'role': 'user',
                    'content': (
                        'Your plan was rejected. DO NOT write the plan again yet. '
                        'You need to click through to the actual feature page first:\n'
                        '1. Call browser_snapshot (no args) NOW to see the sidebar\n'
                        '2. In the snapshot, find the target feature — look for its sidebar link '
                        'or "Create" button\n'
                        '3. Call browser_click on that element\n'
                        '4. Call browser_snapshot immediately after — you are now on the real creation form\n'
                        '5. Observe the form fields from this snapshot\n'
                        '6. Write the plan using the URL from this page '
                        '(check the link hrefs in the snapshot for the path)\n'
                        'Only call planner_save_plan after you have completed all 6 steps above.'
                    ),
                })

            nudge_iteration = int(MAX_PLANNER_ITERATIONS * PLANNER_NUDGE_THRESHOLD) - 1
            if not plan_saved and iteration == nudge_iteration:
                if plan_rejection_count > 0:
                    nudge_msg = (
                        'Your plan has been rejected. You STILL need to click the feature button '
                        'in the sidebar to discover the real URL. '
                        'Call browser_snapshot, find the Create button or link for the target feature, '
                        'call browser_click on it, snapshot again, then write the plan with the confirmed URL.'
                    )
                else:
                    nudge_msg = (
                        'You have explored enough pages. Call planner_save_plan NOW with the complete '
                        'markdown plan. Use KNOWN FACTS from your system prompt for any details you did '
                        'not directly observe.'
                    )
                messages.append({'role': 'user', 'content': nudge_msg})

            messages = prune_history(messages, 10)
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


def _test_plan_to_dict(plan):
    """Convert a TestPlan dataclass to a JSON-serializable dict."""
    return {
        'url': plan.url,
        'title': plan.title,
        'flows': [
            {
                'id': f.id,
                'name': f.name,
                'description': f.description,
                'steps': f.steps,
                'assertions': f.assertions,
            }
            for f in plan.flows
        ],
        'pages': plan.pages,
    }
