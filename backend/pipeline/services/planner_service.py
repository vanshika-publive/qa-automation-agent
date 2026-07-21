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
from pipeline.knowledge.dashboard_facts import (
    facts_for_all_mentioned_pages, matched_pages_for_prompt, PAGE_FACTS,
)
from pipeline.constants import MAX_PLANNER_ITERATIONS, PLANNER_NUDGE_THRESHOLD
from pipeline.prompts.planner_prompt import build_planner_system_prompt
from pipeline.tools.planner_tools import PLANNER_CUSTOM_TOOLS
from pipeline.transforms.plan_validator import validate_plan_content, CONTENT_TYPE_FILTER_MAP, _snapshot_is_error_page


class PlannerService:

    ALLOWED_MCP = {
        'browser_navigate',
        'browser_snapshot',
        'browser_click',
        'browser_hover',
        'browser_wait_for',
    }

    # Substrings in a browser_click result that mean the click never actually landed — the target
    # was in the accessibility snapshot but not truly actionable (hover-reveal, opacity:0, or
    # overlapped by another layer). Triggers the native-click recovery in _handle_tool.
    _CLICK_FAILED_MARKERS = (
        'intercepts pointer events',
        'Timeout',
        'timeout',
        'not visible',
        'not stable',
        'not enabled',
        'waiting for element',
        'element is not',
        'ERROR calling browser_click',
    )

    @staticmethod
    def run(test_plan, plan_path: str, planning_memory=(), correction=None) -> None:
        """Drive a live browser to discover the UI and write plan.md.

        planning_memory: up-to-4 human navigation corrections injected into the system prompt.
            Empty -> no corrections injected.
        correction: optional dict {prefix_steps, failed_at_step, text} for a human-initiated
            corrective replan. When set, the planner is told to keep the prefix and re-plan
            the tail from the correction; the caller enforces prefix preservation afterward.
        """
        ai = AiClientFactory.create()
        openai = ai['client']
        model = ai['model']
        # read_only: the planner only observes the UI to write plan.md — it must never mutate the
        # live dashboard. A confirm-Delete/Publish click while exploring (e.g. verifying a delete
        # flow) would otherwise hit the real API; the guard blocks the request in-browser.
        bridge = MCPBridge(read_only=True)
        snapshot_cache = {}
        # Diagnosis state — initialized before the try so a crash during setup (before the
        # agentic loop starts) can still produce a structured failure report, not a bare
        # traceback. iteration starts at -1 so a pre-loop crash reports 0 iterations attempted.
        plan_saved = False
        iteration = -1
        snapshot_call_count = 0
        plan_rejection_count = 0
        last_action = None
        last_rejection = None

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
                heuristics, facts, CredentialManager.get_publisher(), planning_memory
            )

            # When the flow targets exactly one known page (e.g. the Content-Type-Builder
            # custom-component list), start the planner there directly. The orchestrator only
            # knows the environment base URL, so without this the planner improvises navigation
            # and can land on a same-named-but-wrong page (e.g. Custom *Page* content vs Custom
            # *Component* config). A single unambiguous match has a confirmed path — go straight to it.
            start_url = test_plan.url
            _matched = matched_pages_for_prompt(plan_text)
            if len(_matched) == 1 and _matched[0].path.startswith('/'):
                start_url = f"{test_plan.url.rstrip('/')}{_matched[0].path}"

            user_content = (
                f'Here is the TestPlan to implement:\n\n'
                f'{json.dumps(PlannerService._to_dict(test_plan), indent=2)}\n\n'
                f'{PlannerService._correction_directive(correction)}'
                f'Start immediately by calling planner_setup_page with url: {start_url}'
            )
            messages = [
                {'role': 'system', 'content': planner_system_prompt},
                {'role': 'user', 'content': user_content},
            ]

            setup_page_count = 0
            last_setup_url = ''
            plan_just_rejected = False
            # Each flow needs a genuine navigate+snapshot pass on its target page (plus a few
            # combobox snapshots), so scale the snapshot budget with flow count instead of a flat
            # cap — capped below MAX_PLANNER_ITERATIONS so a runaway snapshot loop still gets cut off.
            snapshot_budget = min(16, 4 + 3 * max(1, len(test_plan.flows)))

            AgentUtils.reset_call_counter()
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
                                'Your plan was rejected — re-read the most recent PLAN REJECTED message, it states '
                                'the exact fix. If it hands you a concrete replacement URL or names a specific field '
                                'to add, just edit the plan text accordingly and call planner_save_plan again — do NOT '
                                're-browse for something you already have. Only if the rejection explicitly says a URL '
                                'or field is still unverified, click through the UI to confirm it first:\n'
                                '1. Call browser_snapshot (no args) to see the current page and sidebar\n'
                                '2. Find the feature you need in the sidebar — look for its link or "Create" button\n'
                                '3. Call browser_click on that element to navigate there\n'
                                '4. Call browser_snapshot again to see the form and confirm the URL\n'
                                '5. Then call planner_save_plan with steps using that confirmed URL'
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
                    last_action = f'{name}({json.dumps(args)[:120]})'
                    # planner_save_plan logged in full — truncation hid plan text on rejection loops,
                    # making it impossible to tell if the model resubmitted the same broken URL.
                    if name == 'planner_save_plan':
                        print(f'Planner calling: {name}({json.dumps(args)})')
                    else:
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
                        last_rejection = result_str
                    if plan_saved_flag:
                        plan_saved = True
                    max_chars = AgentUtils.MAX_SNAPSHOT_RESULT_CHARS if name == 'browser_snapshot' else None
                    tool_results.append({
                        'role': 'tool',
                        'tool_call_id': call.id,
                        # Lift any open overlay (popover/modal/dropdown) to the front before
                        # truncation — portaled overlays serialize last and are otherwise cut off
                        # on big pages, hiding the very option the click just opened.
                        'content': AgentUtils.truncate_result(
                            AgentUtils.surface_overlays(result_str), max_chars
                        ),
                    })

                messages.extend(tool_results)

                if not plan_saved and snapshot_call_count >= snapshot_budget:
                    messages.append({
                        'role': 'user',
                        'content': (
                            'STOP calling browser_snapshot — you have snapshotted enough and are wasting '
                            'iterations. Call planner_save_plan NOW with the complete markdown plan, using the '
                            'Verified Page Facts for field labels (for an edit flow: the create-page fields plus '
                            'the "Save Changes" button). Do not call any tool other than planner_save_plan.\n'
                            'EXCEPTION: if you have NOT yet visited the target feature page (e.g. the create '
                            'page for the flow under test), navigate there NOW with browser_click on the '
                            'sidebar link — one click + one snapshot — then call planner_save_plan immediately.'
                        ),
                    })

                if plan_just_rejected:
                    _remaining = MAX_PLANNER_ITERATIONS - 1 - iteration
                    _urgency = (
                        f' — YOU HAVE {_remaining} ITERATION(S) LEFT. Navigate NOW: '
                        f'browser_snapshot → browser_click the feature link → browser_snapshot → planner_save_plan. '
                        f'No time for anything else.'
                    ) if _remaining <= 3 else ''
                    messages.append({
                        'role': 'user',
                        'content': (
                            f'Your plan was rejected — see the reason above{_urgency}\n'
                            'First check whether the fix is already available to you: a URL you already '
                            'visited earlier in this conversation (check your own prior planner_setup_page / '
                            'browser_click calls and their results), or a fact already stated in your system '
                            'prompt (KNOWN FACTS / Verified Page Facts). If so, just correct the plan text '
                            'to match it and call planner_save_plan again — do NOT re-navigate.\n'
                            'Only click through the UI if the fix genuinely requires something you have not '
                            'yet observed (a real URL, field label, or option text):\n'
                            '1. Call browser_snapshot (no args) to see the sidebar\n'
                            '2. Find the target feature — its sidebar link or "Create" button\n'
                            '3. Call browser_click on that element\n'
                            '4. Call browser_snapshot immediately after\n'
                            '5. Write the plan using the confirmed URL/field from this page'
                        ),
                    })

                nudge_iteration = int(MAX_PLANNER_ITERATIONS * PLANNER_NUDGE_THRESHOLD) - 1
                if not plan_saved and iteration == nudge_iteration:
                    nudge_msg = (
                        'Your plan keeps getting rejected. Re-read the most recent PLAN REJECTED message — '
                        'it states the exact fix. If it gives a concrete replacement URL or a specific field '
                        'to add, edit the plan text to match it EXACTLY and call planner_save_plan again NOW — '
                        'do NOT call browser_snapshot or browser_click for a fix you already have. Only re-browse '
                        'if the rejection explicitly says a URL or field is still unverified.'
                    ) if plan_rejection_count > 0 else (
                        'You have explored enough pages. Call planner_save_plan NOW with the complete '
                        'markdown plan. Do NOT write page.goto() for any URL you have not personally '
                        'snapshotted in this session — those will be rejected. If you have not yet '
                        'visited the target create/list page, use browser_click on its sidebar link '
                        'NOW, browser_snapshot to confirm the URL, then call planner_save_plan.'
                    )
                    messages.append({'role': 'user', 'content': nudge_msg})

                messages = AgentUtils.prune_history(messages, 10)
                if plan_saved:
                    break

            print(f'[planner] {AgentUtils.get_token_summary()}')
            if not plan_saved:
                diagnosis = PlannerService._build_failure_diagnosis(
                    iterations=iteration + 1,
                    snapshots=snapshot_call_count,
                    rejections=plan_rejection_count,
                    last_action=last_action,
                    last_rejection=last_rejection,
                    snapshot_cache=snapshot_cache,
                )
                err = RuntimeError(diagnosis['message'])
                # Persisted to step-failure.json by the pipeline's except handler — drives the "Failure reason" panel.
                err.diagnosis = diagnosis['report']
                raise err
            print(f'Planner complete — plan saved to {plan_path}')

        except Exception as err:
            # Attach a diagnosis to crash paths not covered above (setup / mid-loop errors)
            # so the "Failure reason" panel shows cause rather than a bare traceback.
            if not plan_saved and getattr(err, 'diagnosis', None) is None:
                diagnosis = PlannerService._build_failure_diagnosis(
                    iterations=iteration + 1,
                    snapshots=snapshot_call_count,
                    rejections=plan_rejection_count,
                    last_action=last_action,
                    last_rejection=last_rejection,
                    snapshot_cache=snapshot_cache,
                    error=err,
                )
                err.diagnosis = diagnosis['report']
            raise
        finally:
            bridge.close()

    @staticmethod
    def _build_failure_diagnosis(iterations, snapshots, rejections,
                                 last_action, last_rejection, snapshot_cache, error=None):
        """Turn the planner's end-state into a structured, human-readable failure report.

        Returns {'message': str, 'report': dict}. `report` is persisted as step-failure.json
        and drives the "Failure reason" panel. `error` is set for mid-run crashes; omit for
        the iteration-budget-exhausted case.
        """
        last_page = None
        last_snapshot_excerpt = None
        if snapshot_cache:
            last_page, last_snapshot = next(reversed(snapshot_cache.items()))
            last_snapshot_excerpt = (last_snapshot or '')[:800]

        if error is not None:
            category = 'Planner error'
            summary = (
                f'The planner stopped with an error before saving a plan: '
                f'{PlannerService._truncate(PlannerService._first_line(str(error)), 200)}. '
                f'Last action: {last_action or "none"}'
                + (f' — last page observed: {last_page}' if last_page else '')
            )
        elif rejections and last_rejection:
            category = 'Planner blocked'
            reason = PlannerService._strip_rejection_prefix(last_rejection)
            summary = (
                f'The planner drafted a plan but the validator rejected it {rejections}× and it '
                f'was never saved. Last rejection: {PlannerService._truncate(reason, 240)}'
            )
        else:
            category = 'Planner blocked'
            summary = (
                f'The planner ran {iterations} iterations ({snapshots} snapshots) without saving a '
                f'valid plan. Last action: {last_action or "none"}'
                + (f' — last page observed: {last_page}' if last_page else '')
            )

        report = {
            'step': 'planner',
            'category': category,
            'summary': summary,
            'locator': last_action,
            'iterations': iterations,
            'snapshots': snapshots,
            'rejections': rejections,
            'last_action': last_action,
            'last_rejection': last_rejection or None,
            'last_page': last_page,
            'last_snapshot_excerpt': last_snapshot_excerpt,
        }

        message = (
            'PLANNER COULD NOT PRODUCE A PLAN\n'
            f'Reason: {summary}\n'
            f'Iterations: {iterations}/{MAX_PLANNER_ITERATIONS}   '
            f'Snapshots: {snapshots}   Rejections: {rejections}\n'
            f'Last action: {last_action or "none"}\n'
            f'Last page observed: {last_page or "none"}\n'
            + (f'Last validator rejection:\n{PlannerService._strip_rejection_prefix(last_rejection)}\n'
               if last_rejection else '')
            + '\nThe flow may be genuinely blocked, or the model may be looping. '
              'The full tool-call trace is in the planner step log above.'
        )
        return {'message': message, 'report': report}

    @staticmethod
    def _strip_rejection_prefix(text):
        """Drop the 'PLAN REJECTED — ' wrapper and trailing period from a rejection tool-result."""
        cleaned = re.sub(r'^\s*PLAN REJECTED\s*[—-]\s*', '', str(text or '')).strip()
        return cleaned.rstrip('.')

    @staticmethod
    def _truncate(text, limit):
        text = str(text or '').strip()
        return text if len(text) <= limit else text[:limit].rstrip() + '…'

    @staticmethod
    def _first_line(text):
        for line in str(text or '').splitlines():
            line = line.strip()
            if line:
                return line
        return str(text or '').strip()

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
                landed_facts = PlannerService._facts_for_path(landed_path)
                if (landed_facts is not None and landed_facts.launch_button
                        and PlannerService._is_creation_flow(test_plan)):
                    # Dialog-launched page. If we already opened the dialog on the first landing,
                    # its snapshot is cached — do NOT re-navigate or re-open; the model has looped
                    # here before, so hard-stop it toward writing the plan. Otherwise open it now.
                    cached = snapshot_cache.get(target_url + '#create-dialog', '')
                    if cached and re.search(r'(?im)^\s*[-*]?\s*(?:dialog|alertdialog)\b', cached):
                        result = (
                            f'You are already on {target_url} and the "{landed_facts.launch_button}" '
                            f'dialog was already opened for you earlier — its snapshot is in this '
                            f'conversation. STOP navigating. Call planner_save_plan NOW with the full '
                            f'flow (goto → click "{landed_facts.launch_button}" → fill every dialog "*" '
                            f'field → advance button → any later field-builder steps from the Verified '
                            f'Page Facts). Do not call planner_setup_page or browser_click again.'
                        )
                    else:
                        dialog_result = PlannerService._drive_dialog_flow(
                            bridge, target_url, landed_facts, snapshot_cache
                        )
                        result = dialog_result or (
                            f'Already on {target_url} — a dialog-launched create page. Click button '
                            f'"{landed_facts.launch_button}" to open the create dialog, then '
                            f'browser_snapshot to read its required "*" fields, then planner_save_plan.'
                        )
                elif is_known_target:
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
                        # Some pages (e.g. Configuration sub-pages) load inside an iframe and produce
                        # a nearly-empty first snapshot. Retry once to give the iframe time to render.
                        if len(snapshot) < 400:
                            import time as _time_module
                            _time_module.sleep(1.5)
                            snapshot2 = bridge.call_tool('browser_snapshot', {})
                            if len(snapshot2) > len(snapshot):
                                snapshot = snapshot2
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
                        elif _snapshot_is_error_page(snapshot):
                            result = PlannerService._guide_to_create_page(
                                bridge, test_plan.url, test_plan, snapshot_cache, attempted_url=target_url
                            )
                        else:
                            result = f'Navigated to {target_url}. Page snapshot:\n{AgentUtils.truncate_result(snapshot, 3000)}'
                            # On first landing of a creation flow, inject live create routes from
                            # the "Content Type" sidebar so the planner never guesses a create URL.
                            landed_is_known = any(p in landed_path for p in PAGE_FACTS.keys())
                            # Dialog-launched create flow: the form is behind a dialog, not on this
                            # page. Open it deterministically NOW (before the model can loop trying to
                            # verify fields that aren't here) and hand over the real dialog snapshot.
                            landed_facts = PlannerService._facts_for_path(landed_path)
                            if (landed_facts is not None and landed_facts.launch_button
                                    and PlannerService._is_creation_flow(test_plan)):
                                # Cache under target_url (the key the "already on" re-visit branch
                                # looks up) so a later same-URL setup_page is recognized as already
                                # driven and hard-stopped instead of re-opening the dialog.
                                dialog_result = PlannerService._drive_dialog_flow(
                                    bridge, target_url, landed_facts, snapshot_cache
                                )
                                if dialog_result:
                                    result = dialog_result
                            print(f'[planner:setup] count={setup_page_count} '
                                  f'creation_flow={PlannerService._is_creation_flow(test_plan)} '
                                  f'known_target={landed_is_known} '
                                  f'title={getattr(test_plan, "title", None)!r}')
                            # Only hand over the live create-route map when the planner landed on a page
                            # we DON'T already have facts for. If the page is a known target (in PAGE_FACTS),
                            # the planner already has the confirmed URL + field facts — proactively guiding
                            # it elsewhere would drag it off the correct page and burn iterations.
                            if (setup_page_count == 1 and not landed_is_known
                                    and PlannerService._is_creation_flow(test_plan)):
                                guide = PlannerService._guide_to_create_page(
                                    bridge, test_plan.url, test_plan, snapshot_cache
                                )
                                if guide:
                                    result = (
                                        f'{result}\n\nThis is a content-creation flow, so the real '
                                        f'create page was located live for you:\n{guide}'
                                    )
                    except Exception:
                        result = f'Navigated to {target_url}. Call browser_snapshot (no args) to see the page.'
                except Exception as err:
                    result = f'ERROR navigating to {target_url}: {err}'

        elif name == 'planner_save_plan':
            content = PlannerService._auto_fix_plan(str(args.get('content', '')))
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

        elif name == 'browser_click':
            try:
                result = bridge.call_tool(name, args)
            except Exception as err:
                result = f'ERROR calling {name}: {err}'
            # Sidebar elements (opacity:0 panels, popover cards) appear in the accessibility
            # snapshot but fail pointer events — the click times out without landing. Recover
            # with a native el.click() which fires the handler regardless of opacity/interception.
            target = args.get('target') or args.get('ref') or args.get('selector')
            if target and any(m in result for m in PlannerService._CLICK_FAILED_MARKERS):
                element_desc = args.get('element') or 'the element'
                try:
                    bridge.call_tool('browser_evaluate', {
                        'target': target,
                        'element': element_desc,
                        'function': '(el) => { el.scrollIntoView({block: "center"}); el.click(); }',
                    })
                    snapshot = bridge.call_tool('browser_snapshot', {})
                    url_match = re.search(r'^- Page URL:\s*(\S+)', snapshot, flags=re.MULTILINE)
                    cache_key = url_match.group(1) if url_match else f'snapshot-{id(snapshot)}'
                    snapshot_cache[cache_key] = snapshot
                    result = (
                        f'A normal click on {element_desc} could not land — it was present in the '
                        f'snapshot but not directly clickable (a hover-reveal / opacity:0 / overlapped '
                        f'element, which is normal for this dashboard\'s Content Type sidebar and its '
                        f'create-type popovers). Recovered automatically with a native click. Below is '
                        f'the RESULTING page — CONTINUE the flow from here (read its "- Page URL:" and '
                        f'any popover/menu that opened); do NOT abandon the flow or fall back to a '
                        f'guessed/hardcoded plan:\n{snapshot}'
                    )
                except Exception as rec_err:
                    result = (
                        f'{result}\n\nNative-click recovery also failed: {rec_err}. If this element '
                        f'is a link or a create option, read its target URL from the snapshot and '
                        f'reach the page with planner_setup_page instead of clicking.'
                    )
            # Click result IS the resulting page snapshot — cache it so click-navigated pages
            # count as visited for the plan validator's URL and required-field checks.
            click_url = re.search(r'^- Page URL:\s*(\S+)', result, flags=re.MULTILINE)
            if click_url:
                snapshot_cache[click_url.group(1)] = result

        else:
            try:
                result = bridge.call_tool(name, args)
                if name == 'browser_snapshot':
                    # Parse URL from snapshot text ("- Page URL: <url>" on line 1) rather than
                    # a browser_evaluate round-trip — avoids a stale id()-based fallback key
                    # that the plan validator's URL lookup could never match.
                    url_match = re.search(r'^- Page URL:\s*(\S+)', result, flags=re.MULTILINE)
                    cache_key = url_match.group(1) if url_match else f'snapshot-{id(result)}'
                    snapshot_cache[cache_key] = result
                    # If the LLM snapshotted a page it reached via a guessed create URL and it is the
                    # "Something went wrong" screen, hand it the real create routes discovered live —
                    # this is the point where the full page text is guaranteed present.
                    if _snapshot_is_error_page(result):
                        result = PlannerService._guide_to_create_page(
                            bridge, test_plan.url, test_plan, snapshot_cache, attempted_url=cache_key
                        )
            except Exception as err:
                result = f'ERROR calling {name}: {err}'

        return result, setup_page_count, last_setup_url, plan_just_rejected, plan_saved

    @staticmethod
    def _is_creation_flow(test_plan) -> bool:
        """True when the test is about creating/adding new content — the case where the planner
        benefits from being handed the live create-route map up front."""
        try:
            parts = [str(test_plan.title or '')]
            for f in test_plan.flows:
                parts += [str(f.name or ''), str(f.description or '')]
                parts += [str(s) for s in (f.steps or [])]
            text = ' '.join(parts).lower()
        except Exception:
            return False
        # Prefix match (no trailing \b) so "create"/"creation"/"adding" all count — a trailing
        # boundary would only match the bare tokens "creat"/"add" and miss every real title.
        return bool(re.search(r'\b(creat|add|new|publish|make|compos)', text))

    @staticmethod
    def _discover_create_routes(bridge, base_url: str) -> list:
        """Read the live 'Content Type' sidebar to enumerate the REAL create routes as (label, url).

        Nothing is hardcoded: navigate to the posts listing (where the sidebar is interactive),
        open every '+' Create popover — which reveals nested options such as Custom Content ->
        Template Page / Blank Canvas — and collect every create link straight from the DOM.
        Returns a list of (label, absolute_url); [] on any failure.
        """
        try:
            bridge.call_tool('browser_navigate', {'url': f"{base_url.rstrip('/')}/posts/published?content=true"})
            # Open the per-type '+' create popovers so their nested option links render into the DOM.
            bridge.call_tool('browser_evaluate', {'function': (
                '() => { document.querySelectorAll(\'.create-redirect.popover, button[title="Create"]\')'
                '.forEach(b => { try { b.click(); } catch (e) {} }); }'
            )})
            # The Ant popover renders ASYNC after the click — without a beat the very next read runs
            # before the "Blank Canvas"/"Template Page" option links exist in the DOM (confirmed: only
            # the bare "Create" links were found). A snapshot call blocks until the page is stable.
            try:
                bridge.call_tool('browser_snapshot', {})
            except Exception:
                pass
            raw = bridge.call_tool('browser_evaluate', {'function': (
                '() => { const seen = new Set(); const out = []; '
                'document.querySelectorAll("a[href]").forEach(a => { '
                'const h = a.getAttribute("href") || ""; '
                'const l = (a.getAttribute("title") || a.textContent || "").trim().replace(/\\s+/g, " ").slice(0, 90); '
                'if ((/\\/create(\\b|$|\\?)/.test(h) || /create=/.test(h)) && l && !seen.has(h)) { '
                'seen.add(h); out.push(l + "  =>  " + h); } }); return out.join("\\n"); }'
            )})
            routes = []
            for line in (raw or '').splitlines():
                if '  =>  ' not in line:
                    continue
                label, href = [x.strip() for x in line.split('  =>  ', 1)]
                if not href:
                    continue
                if href.startswith('/'):
                    origin = base_url.split('/v2')[0].rstrip('/')
                    href = f'{origin}{href}'
                routes.append((label, href))
            return routes
        except Exception:
            return []

    @staticmethod
    def _best_matching_route(test_plan, routes: list):
        """Pick the create route whose label best matches the test's intent (by distinctive word
        overlap). Returns (label, url) or None when nothing matches confidently."""
        stop = {'create', 'page', 'pages', 'new', 'add', 'test', 'the', 'and', 'for', 'with',
                'content', 'custom', 'unstructured', 'structures', 'code', 'response', 'formats'}
        try:
            title = (test_plan.title or '').lower()
        except Exception:
            title = ''
        tokens = [t for t in re.findall(r'[a-z]{4,}', title) if t not in stop]
        best, best_score = None, 0
        for label, href in routes:
            ll = label.lower()
            score = sum(1 for t in set(tokens) if t in ll)
            if score > best_score:
                best, best_score = (label, href), score
        return best if best_score > 0 else None

    @staticmethod
    def _facts_for_path(path: str):
        """Return the PageFacts whose key is a substring of `path` (same match rule the landing
        branches use for is_known_target), or None. Longest key wins so a more specific page
        (e.g. .../custom-component/<id>) is preferred over a prefix match."""
        best = None
        best_len = -1
        for key, facts in PAGE_FACTS.items():
            if key and key in (path or '') and len(key) > best_len:
                best, best_len = facts, len(key)
        return best

    @staticmethod
    def _drive_dialog_flow(bridge, page_url: str, facts, snapshot_cache: dict) -> str:
        """Deterministically open a dialog-launched create flow so the planner observes the REAL
        form. On a launcher page the required fields live behind facts.launch_button, not on the
        landing page — so the runtime clicks the launcher itself (read-only-safe: opening a dialog
        is a GET, and the readonly guard blocks any mutation regardless) and snapshots the opened
        dialog. The dialog snapshot is cached under a DISTINCT "#create-dialog" key (never the bare
        page URL) so a later list-page snapshot the model may take cannot overwrite it — the plan
        validator unions all cached snapshots, so the dialog's "*" fields stay visible to it. The
        snapshot is also handed to the planner inline. Returns a guidance string, or '' if the
        dialog could not be confirmed open (caller falls back to generic guidance)."""
        launch = facts.launch_button
        # Try the accessible-name role selector first (matches exactly what the generator's
        # get_by_role('button', name=...) will use), then a has-text fallback for buttons whose
        # label is nested. A role=dialog node (Ant modals render as one) is the proof the click
        # landed and opened the form. CRITICAL: the dialog animates in, so a snapshot taken
        # immediately after the click routinely misses it -- poll a few times with a short delay
        # before giving up, otherwise we fall back, never cache the dialog, and the validator then
        # rejects the dialog's real "*" fields as "nonexistent on any visited page".
        import time as _time_module
        dialog_re = r'(?im)^\s*[-*]?\s*(?:dialog|alertdialog)\b'
        snapshot = ''
        for selector in (f'role=button[name="{launch}"]', f'button:has-text("{launch}")'):
            try:
                bridge.call_tool('browser_click', {'target': selector, 'element': f'"{launch}" button'})
            except Exception as err:
                print(f'[planner:dialog] click via {selector!r} failed: {err}')
                continue
            for _attempt in range(4):
                try:
                    snapshot = bridge.call_tool('browser_snapshot', {})
                except Exception:
                    snapshot = ''
                if re.search(dialog_re, snapshot):
                    break
                _time_module.sleep(0.7)
            if re.search(dialog_re, snapshot or ''):
                break
        if not re.search(dialog_re, snapshot or ''):
            print(f'[planner:dialog] "{launch}" click did not surface a dialog — falling back')
            return ''
        # Distinct key so a later list-page snapshot under the bare page_url can't clobber it.
        snapshot_cache[page_url + '#create-dialog'] = snapshot
        print(f'[planner:dialog] opened "{launch}" dialog on {page_url} and cached its snapshot')
        return (
            f'This is a DIALOG-LAUNCHED create flow — the form is NOT on the list page itself. '
            f'The "{launch}" dialog has been opened for you; its live snapshot is below. Write the '
            f'plan for the FULL flow:\n'
            f"  1. page.goto('{page_url}')  (this exact URL — it is verified)\n"
            f'  2. click button "{launch}" to open the dialog\n'
            f'  3. a fill/select step for EVERY control in the dialog whose accessible name ends in '
            f'"*" (required) — use ONLY the labels shown in THIS dialog snapshot, never copy fields '
            f'from other content types\n'
            f'  4. click the dialog\'s advance button (e.g. "Continue"/"Save"), waiting '
            f'expect(...).to_be_enabled(timeout=15000) before the click\n'
            f'  5. continue through any subsequent steps described in the Verified Page Facts for this '
            f'page (later dialogs/field-builder steps).\n'
            f'Do NOT call planner_setup_page again for this page — you have everything you need here.\n\n'
            f'Dialog snapshot:\n{AgentUtils.truncate_result(snapshot, 3000)}'
        )

    @staticmethod
    def _guide_to_create_page(bridge, base_url: str, test_plan, snapshot_cache: dict, attempted_url=None) -> str:
        """Discover the real create routes live, and if one clearly matches the test intent, NAVIGATE
        to it and snapshot it so it is genuinely visited (URL verified + fields observable), then hand
        the planner explicit instructions. Falls back to just listing the routes. Used both proactively
        (first landing of a creation flow) and to rescue a navigation that hit the error page.
        """
        prefix = (
            f'"{attempted_url}" is NOT a real page — it rendered the "Something went wrong" error '
            f'screen. Do NOT write a plan on top of it and do NOT guess another URL.\n'
            f'DO NOT call planner_setup_page with another guessed URL — use browser_click only.\n\n'
            if attempted_url else ''
        )
        routes = PlannerService._discover_create_routes(bridge, base_url)
        print(f'[planner:guide] discovered {len(routes)} create routes; '
              f'match={PlannerService._best_matching_route(test_plan, routes)}')
        if not routes:
            return (prefix + 'Could not read the create routes automatically — open the left '
                    '"Content Type" list, click the target type\'s "+" Create button, and click the '
                    'option you need; then use the resulting page URL in page.goto().') if prefix else ''

        match = PlannerService._best_matching_route(test_plan, routes)
        routes_list = '\n'.join(f'{label}  =>  {href}' for label, href in routes)
        if match:
            label, url = match
            try:
                bridge.call_tool('browser_navigate', {'url': url})
                snapshot = bridge.call_tool('browser_snapshot', {})
                if not _snapshot_is_error_page(snapshot):
                    key = url
                    um = re.search(r'^- Page URL:\s*(\S+)', snapshot, flags=re.MULTILINE)
                    if um:
                        key = um.group(1)
                    snapshot_cache[key] = snapshot
                    return (
                        f'{prefix}The item to create matches the "{label}" create page, which is now '
                        f'OPEN and confirmed live at:\n{url}\n\nWrite step 1 of the plan as '
                        f"page.goto('{url}') (this exact URL — it is verified). Then read the snapshot "
                        f'below and add a fill/select step for EVERY control whose accessible name ends '
                        f'in "*" (required), and an enabled-wait before the submit button. Do NOT copy '
                        f'required fields from other content types — use ONLY what this snapshot shows:'
                        f'\n{AgentUtils.truncate_result(snapshot, 3000)}'
                    )
            except Exception:
                pass

        # No matching content-creation route. Only take over the browser when this is an ERROR-page
        # rescue (attempted_url set) — the planner is stranded on a broken page and needs to be moved.
        # On a PROACTIVE call (attempted_url is None) the planner is already on a page that loaded fine;
        # navigating it away to /posts/published would hijack a working flow, so stay silent and let it
        # keep planning from where it is.
        if not attempted_url:
            return ''

        # Navigate to a known page that reliably renders the full sidebar so the planner can
        # click through to the correct section. The base URL (/v2) loads inside an iframe and
        # produces a nearly empty snapshot — use the posts list page instead, which always shows
        # the full sidebar including Configuration, Settings, Analytics, etc.
        sidebar_url = f"{base_url.rstrip('/')}/posts/published?content=true"
        try:
            bridge.call_tool('browser_navigate', {'url': sidebar_url})
            sidebar_snap = bridge.call_tool('browser_snapshot', {})
            um = re.search(r'^- Page URL:\s*(\S+)', sidebar_snap, flags=re.MULTILINE)
            cache_key = um.group(1) if um else sidebar_url
            snapshot_cache[cache_key] = sidebar_snap
            return (
                f'{prefix}None of the Content Type sidebar routes match this test — the feature is '
                f'likely under a different section (e.g. Configuration, Settings, Analytics). '
                f'The full dashboard sidebar is shown below. Find the correct section and call '
                f'browser_click on the relevant link ref, then browser_snapshot to confirm the URL.\n'
                f'DO NOT call planner_setup_page with another guessed URL — navigate by clicking only.\n'
                f'NEVER guess a URL — only write page.goto() with a URL you confirmed by clicking:\n\n'
                f'{AgentUtils.truncate_result(sidebar_snap, 3000)}'
            )
        except Exception:
            pass
        return (
            f'{prefix}Could not load a sidebar. Navigate to {sidebar_url} using planner_setup_page, '
            f'call browser_snapshot to see the sidebar, find the relevant section, and click through '
            f'to the target page. NEVER guess a sub-URL.'
        )

    @staticmethod
    def _auto_fix_plan(content: str) -> str:
        """Deterministically fix issues the LLM reliably fails to self-correct.

        Content-type URL bleed: the LLM is told verbatim "Replace X with Y" and still
        re-submits the same wrong URL. Fix in code, not prompts.
        """
        lower = content.lower()
        matches = [
            (label, filter_url)
            for label, filter_url in CONTENT_TYPE_FILTER_MAP.items()
            if re.search(rf'\b{re.escape(label)}\b', lower)
        ]
        if len(matches) == 1:
            _, filter_url = matches[0]
            # Replace bare /posts/published (no query string) with the filtered URL.
            # Negative lookahead skips already-correct filtered URLs and sub-paths like /published/geographies.
            content = re.sub(r'/posts/published(?![?/\w])', filter_url, content)

        # Vacuous-emptiness auto-fix: the LLM reliably asserts deletion with to_have_count(0)
        # (or loops on .count()) WITHOUT first proving the target rows rendered — the exact case
        # plan_validator.emptiness_without_existence rejects. It is told verbatim to add the
        # wait-for-visible proof and still omits it, so inject it deterministically (mirrors the
        # validator's own regexes) rather than burning retry iterations on a fix the LLM won't make.
        asserts_empty = bool(re.search(r"\.to_have_count\(\s*0\b", content)) or bool(
            re.search(r"\b(?:while|for each|for every)\b[^\n]*\.count\(\)", content, flags=re.IGNORECASE)
        )
        proves_rendered = bool(
            re.search(r"\.wait_for\(\s*state\s*=\s*['\"](?:visible|attached)['\"]", content) or
            re.search(r"\.to_have_count\(\s*[1-9][0-9]*\b", content) or
            re.search(r"\.to_be_visible\(", content)
        )
        if asserts_empty and not proves_rendered:
            row_loc_match = re.search(r"page\.locator\(\s*['\"]tr['\"]\s*\)\.filter\([^\n]*?\)", content)
            row_loc = row_loc_match.group(0) if row_loc_match else "page.locator('tr')"
            proof = (
                f'Before asserting deletion, prove the target row(s) rendered: '
                f'rows = {row_loc}; rows.first.wait_for(state=\'visible\', timeout=15000).'
            )
            lines = content.splitlines()
            for i, ln in enumerate(lines):
                if re.search(r"\.to_have_count\(\s*0\b", ln):
                    indent = re.match(r'\s*', ln).group(0)
                    lines.insert(i, f'{indent}{proof}')
                    break
            else:
                lines.append(proof)
            content = '\n'.join(lines)
        return content

    @staticmethod
    def _correction_directive(correction) -> str:
        """Preamble for a corrective replan: keep the working prefix, re-plan the tail.

        Returns '' for a normal (non-correction) run so the initial message is unchanged.
        """
        if not correction:
            return ''
        prefix = correction.get('prefix_steps') or []
        n = correction.get('failed_at_step')
        text = (correction.get('text') or '').strip()
        prefix_block = '\n'.join(f'{i + 1}. {s}' for i, s in enumerate(prefix)) or '(none)'
        return (
            'CORRECTIVE REPLAN — a human watched a failed run and gave a fix.\n'
            f'These earlier steps ALREADY WORK and must be kept EXACTLY as-is (steps 1..{max(n - 1, 0)}):\n'
            f'{prefix_block}\n\n'
            f'The run went wrong at step {n}. Human correction (authoritative — this is HOW to '
            f'navigate, follow it): "{text}"\n'
            'Re-plan from the failing step onward using this correction. Reproduce the working '
            'steps above verbatim as the start of the plan, then continue with the corrected path. '
            'Browse live to confirm the corrected navigation before saving.\n\n'
        )

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
