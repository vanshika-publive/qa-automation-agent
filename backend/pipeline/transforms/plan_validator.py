import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from pipeline.knowledge.dashboard_facts import KNOWN_PATH_PREFIXES, PAGE_FACTS, VIRTUALIZED_COMBOBOX_NAMES


def _extract_goto_paths(content: str) -> List[str]:
    """Extracts paths from both code form (page.goto('/path') or page.goto('https://host/v2/path')) and prose form."""
    paths: List[str] = []
    for m in re.finditer(r"page\.goto\(['\"`](https?:\/\/[^'\"`\)]+|\/[^'\"`\)]+)['\"`]\)", content):
        raw = m.group(1)
        if raw.startswith('http'):
            raw = re.sub(r'^/v2(?=/|$)', '', urlparse(raw).path) or '/'
        paths.append(raw)
    for line in content.split('\n'):
        if not re.search(r'page\.goto\s*\(\s*\)', line):
            continue
        # Capture the query string too (?page_type=...&create=...) — the prompt teaches the prose
        # form "Navigate to <PATH> via page.goto()", so the content-type filter lives OUTSIDE the
        # parens. Truncating at '?' turned a correct filtered URL into the bare /posts/published and
        # made the content-type-bleed check reject a valid plan forever (confirmed loop, 2026-07-01).
        for m in re.finditer(r"(?<![:\w])(\/[a-zA-Z][\w\-/]*(?:\?[^\s'\"`)]*)?)", line):
            paths.append(m.group(1))
    return list(dict.fromkeys(paths))  # unique, preserving order


def _field_distinctive_tokens(field_name: str) -> List[str]:
    """Length filter (>=3, or >=4 inside parens) skips connector words."""
    cleaned = field_name.replace('*', '').strip()
    paren_match = re.search(r'\(\s*([^)]+?)\s*\)', cleaned)
    if paren_match:
        before = cleaned[:cleaned.index('(')].strip()
        inside = paren_match.group(1).strip()
        tokens = before.split() + inside.split()
        return [re.sub(r'[^A-Za-z0-9]', '', w) for w in tokens if len(re.sub(r'[^A-Za-z0-9]', '', w)) >= 4]
    tokens = cleaned.split()
    return [re.sub(r'[^A-Za-z0-9]', '', w) for w in tokens if len(re.sub(r'[^A-Za-z0-9]', '', w)) >= 3]


def _is_field_referenced(field_name: str, content: str) -> bool:
    tokens = _field_distinctive_tokens(field_name)
    if len(tokens) == 0:
        return True
    return all(re.search(rf'\b{re.escape(tok)}\b', content, flags=re.IGNORECASE) for tok in tokens)


def normalize_field_name(s: str) -> str:
    result = re.sub(r'\\([()*])', r'\1', s)
    result = result.replace('*', '')
    result = re.sub(r'\s+', ' ', result)
    return result.lower().strip()


def extract_fill_labels(text: str) -> List[str]:
    """Extract fill labels from safe_fill/safe_sequential_fill and get_by_role textbox calls.
    Accepts both Python and legacy TypeScript syntax so plans in either style validate identically.
    Placeholders like '...', '*', '<label>' are skipped — flagging them would cause unrecoverable rejection loops.
    """
    fill = r"(?:safe_fill|safe_sequential_fill|safeFill|safeSequentialFill)"
    name = r"(?:name\s*=\s*|\{\s*name:\s*)"
    labels: List[str] = []
    for m in re.finditer(fill + r"\(\s*page\s*,\s*['\"]([^'\"]+)['\"]", text):
        labels.append(m.group(1))
    for m in re.finditer(fill + r"\(\s*page\s*,\s*re\.compile\(\s*r?['\"]([^'\"]+)['\"]", text):
        labels.append(m.group(1))
    for m in re.finditer(fill + r"\(\s*page\s*,\s*/([^/]+)/", text):
        labels.append(m.group(1))
    for m in re.finditer(r"(?:get_by_role|getByRole)\(\s*['\"]textbox['\"]\s*,\s*" + name + r"['\"]([^'\"]+)['\"]", text):
        labels.append(m.group(1))
    for m in re.finditer(r"(?:get_by_role|getByRole)\(\s*['\"]textbox['\"]\s*,\s*" + name + r"re\.compile\(\s*r?['\"]([^'\"]+)['\"]", text):
        labels.append(m.group(1))
    for m in re.finditer(r"(?:get_by_role|getByRole)\(\s*['\"]textbox['\"]\s*,\s*" + name + r"/([^/]+)/", text):
        labels.append(m.group(1))
    seen: Set[str] = set()
    unique: List[str] = []
    for label in labels:
        if re.search(r'[a-zA-Z]{2,}', label) and label not in seen:
            seen.add(label)
            unique.append(label)
    return unique


def find_hardcoded_virtualized_titles(content: str) -> List[tuple]:
    """Flags get_by_title() option selections made right after opening a combobox known to be
    virtualized + per-publisher (e.g. Primary Category). Even when the title text was genuinely
    visible during planning/generation, the option list re-renders differently (only ~9 of 65+
    options are in the DOM at once) and varies per publisher and over time, so a hardcoded title
    that passed live verification at plan time can still time out at test-run time. These fields
    must always use the dynamic '.ant-select-item-option' pattern instead.
    """
    findings: List[tuple] = []
    for name in VIRTUALIZED_COMBOBOX_NAMES:
        for m in re.finditer(
            rf"get_by_role\(\s*['\"]combobox['\"]\s*,\s*name\s*=\s*['\"]{re.escape(name)}['\"]\)",
            content,
        ):
            window = content[m.end():m.end() + 400]
            next_combobox = re.search(r"get_by_role\(\s*['\"]combobox['\"]", window)
            if next_combobox:
                window = window[:next_combobox.start()]
            if 'ant-select-item-option' in window:
                continue
            title_match = re.search(r"get_by_title\(\s*['\"]([^'\"]+)['\"]", window)
            if title_match:
                findings.append((name, title_match.group(1)))
    return findings


# Maps a content-type keyword to the EXACT filtered published-list URL its single-item flow must use.
# Confirmed bug (2026-07-01): a plan for "edit the topmost video" visited the bare /posts/published
# (which interleaves every content type sorted by recency) and picked row.nth(1), which matched the
# topmost LIVE BLOG instead of a video. Enforced here in addition to the prompt guidance, since the
# planner has been observed to see the filtered sidebar links live and still write the bare URL.
# The value is a ready-to-paste page.goto() path — the rejection message hands it to the model verbatim
# so correcting the plan is a one-line text edit, not a re-exploration of the sidebar.
CONTENT_TYPE_FILTER_MAP = {
    'live blog': '/posts/published?page_type=LiveBlog&ptype=LiveBlog&create=live-blog',
    'liveblog': '/posts/published?page_type=LiveBlog&ptype=LiveBlog&create=live-blog',
    'video': '/posts/published?page_type=Video&ptype=Video&create=video',
    'web story': '/posts/published?page_type=Web Story&ptype=Web Story&create=web-story',
    'photo gallery': '/posts/published?page_type=Gallery&ptype=Gallery&create=gallery',
    'custom content': '/posts/published?page_type=CustomPage&ptype=CustomPage&create=custom-page',
    'custom page': '/posts/published?page_type=CustomPage&ptype=CustomPage&create=custom-page',
    'article': '/posts/published?page_type=Article&ptype=Article&create=article',
}


def validate_plan_content(
    content: str,
    snapshot_cache: Dict[str, str],
    system_prompt: str,
) -> Optional[str]:
    has_flow = bool(re.search(r'^## (Flow \d+|[A-Z])', content, flags=re.MULTILINE))
    has_scenario = bool(re.search(r'^### ', content, flags=re.MULTILINE))
    has_steps = bool(re.search(r'^\d+\.\s+\S', content, flags=re.MULTILINE))
    has_errors = bool(re.search(
        r'Failed to|error with the browser|Unable to complete|could not take snapshot',
        content, flags=re.IGNORECASE
    ))

    # Match an actual code call only; bare prose mentions like "do NOT navigate to /posts/article/create"
    # legitimately appear in geography-filter plan warnings.
    has_article_create = bool(re.search(r"page\.goto\(['\"`]\/?posts\/article\/create", content))
    has_permalink = bool(re.search(r'Permalink', content))
    missing_permalink = has_article_create and not has_permalink

    # Catches "planner collapsed multiple required fields into one fill"
    visited_paths_in_plan = _extract_goto_paths(content)
    plan_clicks_publish = bool(re.search(r"""name\s*=\s*['\"]Publish['\"]""", content))

    # Required-field enforcement only makes sense for flows that actually SUBMIT a form -- the whole
    # point is "don't leave a required field unfilled or the Save/Publish button stays disabled." A
    # delete or read-only/verify journey fills nothing and never submits, so a required field seen on
    # a visited page (e.g. the "File name *" input in the media edit panel a delete flow merely opens)
    # must NOT be demanded. Without this gate such flows hit an unwinnable rejection loop: the planner
    # correctly refuses to add a fill step that would break the delete, and burns every iteration.
    plan_submits_form = bool(re.search(
        r"""[Cc]lick[^\n]*name\s*=\s*['\"](?:Publish|Save Changes|Save as Draft|Save Category|Save|Update|Create|Submit)['\"]""",
        content,
    ))

    missing_required_fields: List[str] = []
    for visited in visited_paths_in_plan:
        facts = PAGE_FACTS.get(visited)
        if not facts or not plan_submits_form:
            continue
        required_fields = list(facts.required_for_draft)
        # When the flow actually publishes, the publish-only required fields (e.g. Summary,
        # Meta Description on articles) also gate the Publish button — enforce them too.
        if facts.save_button == 'Publish' and plan_clicks_publish:
            required_fields += list(facts.required_for_publish)
        for required in required_fields:
            if not _is_field_referenced(required.field, content):
                missing_required_fields.append(f'{visited} -> "{required.field}"')

    # Live-discovered required fields: for any visited page NOT in PAGE_FACTS, read the
    # asterisk-marked required fields straight from the snapshot captured for that page and
    # require each to be filled. Extends the required-fields guarantee to EVERY flow, not just
    # the hand-maintained known pages.
    for visited in visited_paths_in_plan:
        if PAGE_FACTS.get(visited) is not None or not plan_submits_form:
            continue
        snap = None
        for url, snapshot in snapshot_cache.items():
            try:
                snap_path = urlparse(url).path
            except Exception:
                snap_path = url
            if visited and snap_path.find(visited) != -1:
                snap = snapshot
                break
        if not snap:
            continue
        # Role-agnostic on purpose: required fields aren't always textbox/combobox/spinbutton
        # (e.g. an Ant Upload control renders its trigger as role="button"). Any control whose
        # accessible name is asterisk-marked in the live snapshot counts as required.
        live_required = re.findall(r'\b\w+\s+"([^"]*\*[^"]*)"', snap)

        # Some required markers aren't embedded in any control's accessible name at all -- the
        # dashboard sometimes renders the label and the "*" as separate sibling nodes with the
        # actual interactive control carrying no accessible name whatsoever (e.g. Web Story's
        # image upload: a `text: Web Story` node next to a standalone `generic ...: "*"` node,
        # both siblings of an unlabelled clickable drop-zone). Reconstruct these by pairing a
        # standalone asterisk-only node with the nearest preceding label text.
        snap_lines = snap.split('\n')
        for i, line in enumerate(snap_lines):
            if not re.search(r':\s*"\*"\s*$', line):
                continue
            label = None
            for back in range(1, 7):
                j = i - back
                if j < 0:
                    break
                label_match = re.search(r'(?:text|paragraph)[^:]*:\s*(.+)$', snap_lines[j])
                if label_match:
                    candidate = label_match.group(1).strip()
                    if re.search(r'[A-Za-z]{2,}', candidate):
                        label = candidate
                    break
            if not label:
                continue
            # These reconstructed labels are often the content type's own name (e.g. "Web
            # Story" on a "create a web story" plan), which trivially "matches" ordinary prose
            # describing the flow even when the field itself was never actually filled. When
            # the surrounding UI clearly reads as an upload/drop-zone, don't trust bare prose
            # mentions -- require the plan to reference the drop-zone's OWN prompt text.
            context_window = '\n'.join(snap_lines[max(0, i - 8):i + 8])
            if re.search(r'upload|drop.?zone|drag.?(?:and|&).?drop', context_window, flags=re.IGNORECASE):
                # The drop-zone renders a distinctive prompt like "Upload your Web Story image".
                # Requiring THAT exact phrase (not just any "upload" keyword) is what separates a
                # correct plan from one that wrongly targets a similarly-named but OPTIONAL upload
                # button elsewhere on the page (e.g. "Upload ( Portrait )" custom thumbnails) --
                # which was the actual Web Story failure: an "upload" keyword was present, but it
                # pointed at the wrong widget so the required image was never attached.
                # Pick the MOST distinctive "Upload ..." prompt in the window (most word tokens):
                # bare "Upload" labels on the optional thumbnails must not shadow the real,
                # multi-word drop-zone prompt.
                upload_prompts = re.findall(
                    r'(?:text|paragraph)[^:]*:\s*(Upload[^\n]*)',
                    context_window, flags=re.IGNORECASE,
                )
                distinctive = [p.strip() for p in upload_prompts if len(p.split()) >= 3]
                dropzone_prompt = max(distinctive, key=len) if distinctive else None
                if dropzone_prompt and _is_field_referenced(dropzone_prompt, content):
                    continue  # plan references the exact drop-zone prompt -> satisfied
                # Fall back to a generic upload-shaped check only when no distinctive prompt exists.
                if not dropzone_prompt and re.search(
                    r'set_files|file_chooser|browser_file_upload', content, flags=re.IGNORECASE
                ):
                    continue
                target = dropzone_prompt or label
                missing_required_fields.append(f'{visited} -> "{target}" (required image/file upload)')
                continue
            live_required.append(label)

        for raw_name in dict.fromkeys(live_required):
            # ARIA names often embed icon text like "info-circle"; strip it before matching.
            field_name = re.sub(r'\s*info-circle\s*', ' ', raw_name, flags=re.IGNORECASE).strip()
            if not re.search(r'[A-Za-z]{2,}', field_name):
                continue
            if not _is_field_referenced(field_name, content):
                missing_required_fields.append(f'{visited} -> "{field_name}"')

    has_placeholder = bool(re.search(
        r'\[PLAN VALUE\]|\[ACTUAL TEXT\]|exact-option|\[OBSERVED|\[OPTION|\[YOUR',
        content, flags=re.IGNORECASE
    ))

    # Geography + filter flows stay on the geography entity page and configure the
    # Articles content filter there.
    is_geography_filter_flow = (
        bool(re.search(r'geograph', content, flags=re.IGNORECASE)) and
        bool(re.search(r'\bfilter\b', content, flags=re.IGNORECASE))
    )
    forbidden_for_geography_filter = [
        re.compile(r'/posts/article/create'),
        re.compile(r'/posts/draft\b'),
        re.compile(r'/posts/published(?!/geographies)'),
    ] if is_geography_filter_flow else []
    forbidden_goto_matches = [
        p for p in visited_paths_in_plan
        if any(regex.search(p) for regex in forbidden_for_geography_filter)
    ]

    # Single-content-type edit/delete/topmost/latest flow that visits the bare, unfiltered
    # /posts/published — see CONTENT_TYPE_FILTER_MAP comment for the confirmed regression this guards.
    mentioned_content_types = [
        (label, filter_url) for label, filter_url in CONTENT_TYPE_FILTER_MAP.items()
        if re.search(rf'\b{re.escape(label)}\b', content, flags=re.IGNORECASE)
    ]
    targets_single_item_action = bool(re.search(
        r'topmost|latest|\bedit\b|\bdelet|\bpublish|\brename\b|\bupdate\b',
        content, flags=re.IGNORECASE
    ))
    visits_bare_published_list = '/posts/published' in visited_paths_in_plan
    content_type_bleed = (
        visits_bare_published_list and targets_single_item_action and len(mentioned_content_types) == 1
    )

    # A path passes if it starts with a known prefix OR was visited+snapshotted this session
    visited_url_paths: List[str] = []
    for u in snapshot_cache.keys():
        try:
            visited_url_paths.append(urlparse(u).path)
        except Exception:
            visited_url_paths.append(u)

    unvalidated_paths = [
        p for p in visited_paths_in_plan
        if not (
            any(p.startswith(prefix) for prefix in KNOWN_PATH_PREFIXES) or
            (len(snapshot_cache) > 0 and any(v_path.find(p) != -1 for v_path in visited_url_paths))
        )
    ]

    # Entity pages (geography, food, horoscope) publish in one click. Flag plans that visit a
    # one-click-publish page and use 'Save as Draft' -- unless they also visit a real draft page.
    visits_one_click_publish_page = any(
        PAGE_FACTS.get(p) is not None and
        PAGE_FACTS[p].save_button == 'Publish' and
        len(PAGE_FACTS[p].publish_flow) == 0
        for p in visited_paths_in_plan
    )
    visits_draft_save_page = any(
        PAGE_FACTS.get(p) is not None and
        PAGE_FACTS[p].save_button == 'Save as Draft'
        for p in visited_paths_in_plan
    )
    plan_uses_save_as_draft = bool(re.search(r"""['\"]Save as Draft['\"]""", content))
    wrong_save_button = visits_one_click_publish_page and plan_uses_save_as_draft and not visits_draft_save_page

    # Catches fills targeting fields that don't exist on visited pages -- only when EVERY
    # visited path has PageFacts.
    visited_facts = [PAGE_FACTS[p] for p in visited_paths_in_plan if PAGE_FACTS.get(p) is not None]
    all_visited_have_facts = (
        len(visited_paths_in_plan) > 0 and len(visited_facts) == len(visited_paths_in_plan)
    )
    known_fields_across_pages: Set[str] = set()
    for facts in visited_facts:
        for f in [*facts.required_for_draft, *facts.required_for_publish, *facts.optional_fields]:
            known_fields_across_pages.add(normalize_field_name(f.field))

    # Edit journeys reach a form by CLICKING a row's Edit control, not by a goto URL — that form
    # (/<resource>/edit/<id>) is never in visited_paths_in_plan and never in PAGE_FACTS, so its fields
    # MUST NOT be validated against the list page's (empty) facts. If the plan clicks an Edit control,
    # the fills target a page the validator cannot see; only reject a fill label if it is BOTH absent
    # from facts AND absent from every live snapshot the planner captured.
    reaches_clicked_edit_form = bool(re.search(
        r"(?:get_by_role|getByRole)\(\s*['\"](?:button|link)['\"]\s*,\s*(?:name\s*=\s*|\{\s*name:\s*)['\"]Edit\b",
        content, flags=re.IGNORECASE
    ))
    snapshots_text = '\n'.join(snapshot_cache.values())
    plan_fill_labels = extract_fill_labels(content)
    # A search/filter textbox (e.g. "Search by name, path, or alt text" on /media) is NOT a form field --
    # never validate it against a page's form-field facts, or a delete/search plan is rejected forever.
    unknown_fill_labels = (
        [
            l for l in plan_fill_labels
            if normalize_field_name(l) not in known_fields_across_pages
            and not _is_field_referenced(l, snapshots_text)
            and not re.search(r'\b(search|filter)\b', l, flags=re.IGNORECASE)
        ]
        if (all_visited_have_facts and not reaches_clicked_edit_form) else []
    )

    # A get_by_title() value counts as verified if it appears in a live snapshot, in the system
    # prompt (KNOWN FACTS), OR was filled earlier in this plan.
    all_verified_text = '\n'.join([system_prompt, *snapshot_cache.values()])
    title_matches = [
        m.group(1) for m in re.finditer(
            r"(?:get_by_title|getByTitle)\(\s*['\"]([^'\"]+)['\"]", content
        )
    ]
    fill_values_in_plan = [
        m.group(1) for m in re.finditer(
            r"(?:safe_fill|safe_sequential_fill|safeFill|safeSequentialFill|\.fill)\([^)]*?,\s*['\"]([^'\"]+)['\"]",
            content,
        )
    ]

    def created_in_this_plan(title: str) -> bool:
        return any(v == title or title in v or v in title for v in fill_values_in_plan)

    unverified_titles = (
        [t for t in title_matches if t not in all_verified_text and not created_in_this_plan(t)]
        if len(snapshot_cache) > 0 else []
    )

    # Every submit click MUST be preceded by an enabled-wait on the same button — the button is
    # briefly disabled after the required fields are filled (async validation), so an immediate
    # click is flaky and frequently fails the run.
    submit_buttons = ('Publish', 'Save Changes', 'Save as Draft', 'Save Category')
    missing_enabled_wait: List[str] = []
    for btn in submit_buttons:
        clicks_btn = bool(re.search(rf"[Cc]lick[^\n]*name\s*=\s*['\"]{re.escape(btn)}['\"]", content))
        if not clicks_btn:
            continue
        has_enabled_wait = bool(re.search(
            rf"name\s*=\s*['\"]{re.escape(btn)}['\"][^\n]*to_be_enabled", content
        ))
        if not has_enabled_wait:
            missing_enabled_wait.append(btn)

    # React-controlled fields must use safe_sequential_fill, not safe_fill.
    # .fill() does not fire React onChange — the value never registers and Publish stays disabled.
    seen_rc_plan: Set[str] = set()
    react_controlled_fields_in_plan_scope = []
    for facts in visited_facts:
        for f in [*facts.required_for_draft, *facts.required_for_publish, *facts.optional_fields]:
            if f.react_controlled and f.field not in seen_rc_plan:
                seen_rc_plan.add(f.field)
                react_controlled_fields_in_plan_scope.append(f.field)
    wrong_fill_react_in_plan = [
        label for label in react_controlled_fields_in_plan_scope
        if re.search(
            r'(?<![a-zA-Z_])safe_fill\s*\(\s*page\s*,\s*[\'"]' + re.escape(label) + r'[\'"]',
            content
        )
    ]

    hardcoded_virtualized_titles = find_hardcoded_virtualized_titles(content)

    if (
        not has_flow or not has_scenario or not has_steps or has_errors or
        missing_permalink or len(unvalidated_paths) > 0 or has_placeholder or
        len(unverified_titles) > 0 or len(missing_required_fields) > 0 or
        len(forbidden_goto_matches) > 0 or wrong_save_button or len(unknown_fill_labels) > 0 or
        len(missing_enabled_wait) > 0 or len(hardcoded_virtualized_titles) > 0 or
        content_type_bleed or len(wrong_fill_react_in_plan) > 0
    ):
        issues: List[str] = []
        if not has_flow:
            issues.append('no "## Flow N:" sections')
        if not has_scenario:
            issues.append('no "### Scenario:" sections')
        if not has_steps:
            issues.append('no numbered step lists (1. 2. 3.)')
        if has_errors:
            issues.append('contains error/failure messages instead of real steps')
        if has_placeholder:
            issues.append(
                'plan contains unresolved placeholder text (e.g. "exact-option", "[PLAN VALUE]", "[ACTUAL TEXT]") -- '
                'you MUST click the combobox with browser_click, then call browser_snapshot to see the real option text, '
                'and use that exact text in the plan step. Never copy placeholder text from KNOWN FACTS.'
            )
        if missing_permalink:
            issues.append(
                'article creation flow is missing the required "English Title ( Permalink ) *" step -- '
                'this field is mandatory (along with Title * and Primary Category) or Save as Draft stays permanently disabled. '
                "Add a step: \"Use safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}', delay=50) to fill the permalink field\""
            )
        if len(unvalidated_paths) > 0:
            issues.append(
                f'unverified URL path(s): {", ".join(unvalidated_paths)} -- '
                'these were not visited during this session and do not match any known dashboard route. '
                'Navigate there by clicking: snapshot the sidebar -> browser_click the feature link/Create button -> '
                'snapshot to confirm the URL -> use that URL in the plan.'
            )
        if len(unverified_titles) > 0:
            quoted = ', '.join(f'"{t}"' for t in unverified_titles)
            issues.append(
                f'get_by_title() values not seen in any snapshot: {quoted} -- '
                'these option names were not observed during live browsing and will fail at runtime. '
                'For each flagged value: click the combobox with browser_click, call browser_snapshot to see the actual '
                'dropdown options, then use the EXACT text you saw (never invent or assume option names).'
            )
        if len(forbidden_goto_matches) > 0:
            issues.append(
                f'geography + filter flow MUST stay on the geography entity page, but the plan navigates to: '
                f'{", ".join(forbidden_goto_matches)}. '
                'Do NOT navigate to /posts/article/create, /posts/draft, or /posts/published -- the Articles content '
                'filter on the geography entity page IS the entire flow. '
                'Configure the filter on /posts/entity/geographies/geography/create directly: + Add Filter under '
                'Articles (nth(4)) -> Filter by Field -> Match Type -> Value.'
            )
        if len(missing_required_fields) > 0:
            issues.append(
                f'plan is missing fill steps for required fields: {"; ".join(missing_required_fields)} -- '
                'every required field (listed in the Verified Page Facts section, OR any field whose accessible name '
                'ends in "*" in the live snapshot of the page) MUST appear as a safe_fill / safe_sequential_fill call '
                'in the plan steps. Skipping one means the Save/Publish button stays permanently disabled at runtime '
                'and the test times out. '
                'Common offender: geography create has BOTH "Name in English ( Slug )" AND "Name" -- fill BOTH, not just one.'
            )
        if len(missing_enabled_wait) > 0:
            quoted = ', '.join(f'"{b}"' for b in missing_enabled_wait)
            issues.append(
                f'plan clicks the {quoted} button without first waiting for it to be enabled. '
                'The submit button is briefly DISABLED right after the required fields are filled (async validation), '
                'so clicking immediately is flaky and frequently fails the run. Add an assertion immediately BEFORE the '
                "click on that button: expect(get_by_role('button', name='<button>')).to_be_enabled(timeout=15000)."
            )
        if wrong_save_button:
            offenders = ', '.join(
                p for p in visited_paths_in_plan
                if PAGE_FACTS.get(p) is not None and
                PAGE_FACTS[p].save_button == 'Publish' and
                len(PAGE_FACTS[p].publish_flow) == 0
            )
            issues.append(
                f"plan uses 'Save as Draft' but visits a one-click-publish entity page ({offenders}). "
                'Entity pages (geography, food, horoscope, etc.) have ONLY a "Publish" button -- there is no '
                '"Save as Draft" button and no draft list step. Replace the \'Save as Draft\' step with \'Publish\' '
                'and remove any navigation to /posts/draft and any subsequent Edit + Publish pair. '
                'The correct entity flow is: fill required fields -> click Publish on the create page -> assert URL change.'
            )
        if content_type_bleed:
            label, filter_url = mentioned_content_types[0]
            # Quote the exact offending line(s) so the model can see WHICH occurrence is wrong --
            # a plan can fix the navigation goto() but still fail here because a later step or the
            # Expected section repeats the bare URL, and a generic message looks identical across
            # attempts even when the model did make some edit, making retries look like no-ops.
            offending_lines = [
                line.strip() for line in content.split('\n')
                if re.search(r'/posts/published(?!\?|/geographies)', line)
            ]
            offending_quote = (
                '\nExact line(s) in your plan still containing the bare URL:\n' +
                '\n'.join(f'  "{line}"' for line in offending_lines)
                if offending_lines else ''
            )
            issues.append(
                f'plan targets a single "{label}" item (edit/delete/publish/topmost/latest) but navigates to the '
                'bare, unfiltered /posts/published, which interleaves EVERY content type sorted by recency -- '
                '"topmost"/"latest" there means topmost-of-ANY-type, not topmost of the type you want. This exact '
                'pattern previously caused a "topmost video" plan to silently edit a Live Blog instead. This is a '
                'one-line TEXT FIX, not something to re-browse for: change the goto to the exact filtered URL below '
                f"and call planner_save_plan again. Replace page.goto('/posts/published') with "
                f"page.goto('{filter_url}') so the row you act on is guaranteed to be a \"{label}\"."
                f'{offending_quote}'
            )
        if len(hardcoded_virtualized_titles) > 0:
            quoted = ', '.join(f'{name} -> "{title}"' for name, title in hardcoded_virtualized_titles)
            issues.append(
                f'plan hardcodes a get_by_title() option for a virtualized, per-publisher combobox: {quoted}. '
                'Even though this option was visible when you browsed it live, the list is virtualized (only ~9 of '
                '65+ options render at once) and the option set changes per publisher and over time, so a hardcoded '
                'title will time out on a later run even though it passed live verification just now. Replace with '
                "the dynamic pattern: click the combobox, then page.locator('.ant-select-dropdown').last"
                ".locator('.ant-select-item-option').first.wait_for(state='visible') and .click() -- or, if a "
                "specific option is required, cb.fill('<name>') to filter first, then click the first "
                '.ant-select-item-option match. Never use get_by_title() for this combobox.'
            )
        if len(wrong_fill_react_in_plan) > 0:
            quoted = ', '.join(f'"{l}"' for l in wrong_fill_react_in_plan)
            issues.append(
                f'plan uses safe_fill() on React-controlled field(s): {quoted}. '
                'React-controlled inputs do not fire onChange on .fill() — the value does not '
                'register and the Publish/Save button stays permanently disabled. '
                "Replace every flagged call with safe_sequential_fill(page, '<field>', value, delay=50)."
            )
        if len(unknown_fill_labels) > 0:
            valid_per_page_parts: List[str] = []
            for p in visited_paths_in_plan:
                f = PAGE_FACTS.get(p)
                if f is None:
                    continue
                labels = [f'"{field.field}"' for field in [*f.required_for_draft, *f.required_for_publish, *f.optional_fields]]
                if len(labels) > 0:
                    valid_per_page_parts.append(f'  {p} -> valid fill labels: {", ".join(labels)}')
            valid_per_page = '\n'.join(valid_per_page_parts)
            quoted_labels = ', '.join(f'"{l}"' for l in unknown_fill_labels)
            issues.append(
                f'plan fills field(s) that do not exist on any visited page: {quoted_labels}. '
                f'The ONLY valid fill labels for the visited URL(s) are:\n{valid_per_page}\n'
                'Rewrite the plan using ONLY these labels. Remove every fill step for any other field -- '
                'including "Title *", "Meta Description", "Banner Description", "Focus Keyphrase", and '
                '"English Title ( Permalink )" if you added them (those exist on /posts/article/create only, NOT on entity pages).'
            )
        return '; '.join(issues)

    return None
