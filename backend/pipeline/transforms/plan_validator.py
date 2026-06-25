import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from pipeline.knowledge.dashboard_facts import KNOWN_PATH_PREFIXES, PAGE_FACTS


def _extract_goto_paths(content: str) -> List[str]:
    """Extracts paths from both code form (page.goto('/path')) and prose form."""
    paths: List[str] = []
    for m in re.finditer(r"page\.goto\(['\"`](\/[^'\"`\)]+)['\"`]\)", content):
        paths.append(m.group(1))
    for line in content.split('\n'):
        if not re.search(r'page\.goto\s*\(\s*\)', line):
            continue
        for m in re.finditer(r'(?<![:\w])(\/[a-zA-Z][\w\-/]*)', line):
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
    missing_required_fields: List[str] = []
    for visited in visited_paths_in_plan:
        facts = PAGE_FACTS.get(visited)
        if not facts or len(facts.required_for_draft) == 0:
            continue
        for required in facts.required_for_draft:
            if not _is_field_referenced(required.field, content):
                missing_required_fields.append(f'{visited} -> "{required.field}"')

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

    plan_fill_labels = extract_fill_labels(content)
    unknown_fill_labels = (
        [l for l in plan_fill_labels if normalize_field_name(l) not in known_fields_across_pages]
        if all_visited_have_facts else []
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

    if (
        not has_flow or not has_scenario or not has_steps or has_errors or
        missing_permalink or len(unvalidated_paths) > 0 or has_placeholder or
        len(unverified_titles) > 0 or len(missing_required_fields) > 0 or
        len(forbidden_goto_matches) > 0 or wrong_save_button or len(unknown_fill_labels) > 0
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
                "Add a step: \"Use safe_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}') to fill the permalink field\""
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
                'every requiredForDraft field listed for a page in the Verified Page Facts section MUST appear as a '
                'safe_fill / safe_sequential_fill call in the plan steps. Skipping one means the Save/Publish button stays '
                'permanently disabled at runtime and the test times out. '
                'Common offender: geography create has BOTH "Name in English ( Slug )" AND "Name" -- fill BOTH, not just one.'
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
