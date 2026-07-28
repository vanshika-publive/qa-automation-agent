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
        # made the content-type-bleed check reject a valid plan forever.
        for m in re.finditer(r"(?<![:\w])(\/[a-zA-Z][\w\-/]*(?:\?[^\s'\"`)]*)?)", line):
            paths.append(m.group(1))
    return list(dict.fromkeys(paths))  # unique, preserving order


# Ant help/status icons (an <img> whose glyph name is its accessible name) sit INSIDE a field label,
# so the icon name bleeds into the field's accessible name — the redirect form's textbox is literally
# "Old URL question-circle *". These glyph names are never meaningful label text. Worse, a hyphenated
# token like "question-circle" is stripped to "questioncircle" below, but the generated code keeps the
# hyphen, so `\bquestioncircle\b` can NEVER match → _is_field_referenced became permanently
# unsatisfiable and the generator was rejected on every iteration ("Add Redirect" produced no spec at
# all). Dropping these noise tokens fixes the impossibility and lets the field be located by its clean
# leading substring ("Old URL"), which safe_*_fill (exact=False) matches at runtime.
_ICON_NOISE_TOKEN = re.compile(r'(?:circle|outlined|filled|twotone)$', re.IGNORECASE)


def _is_icon_noise(token: str) -> bool:
    return bool(_ICON_NOISE_TOKEN.search(token))


def _field_distinctive_tokens(field_name: str) -> List[str]:
    """Length filter (>=3, or >=4 inside parens) skips connector words; Ant icon-glyph names
    (question-circle, info-circle, …) are dropped as noise."""
    cleaned = field_name.replace('*', '').strip()
    paren_match = re.search(r'\(\s*([^)]+?)\s*\)', cleaned)
    if paren_match:
        before = cleaned[:cleaned.index('(')].strip()
        inside = paren_match.group(1).strip()
        tokens = before.split() + inside.split()
        return [t for w in tokens
                if len(t := re.sub(r'[^A-Za-z0-9]', '', w)) >= 4 and not _is_icon_noise(t)]
    tokens = cleaned.split()
    return [t for w in tokens
            if len(t := re.sub(r'[^A-Za-z0-9]', '', w)) >= 3 and not _is_icon_noise(t)]


def _is_field_referenced(field_name: str, content: str) -> bool:
    tokens = _field_distinctive_tokens(field_name)
    if len(tokens) == 0:
        return True
    return all(re.search(rf'\b{re.escape(tok)}\b', content, flags=re.IGNORECASE) for tok in tokens)


_COMBOBOX_PLACEHOLDERS = ('select', 'choose', 'please', 'search', 'info-circle', 'none', '-')


def _prefilled_combobox_names(snap: str) -> set:
    """Names of comboboxes that ALREADY show a selected value in the snapshot (pre-filled defaults
    like Response Type -> 'HTML', or Credits -> the logged-in user). In the accessibility tree such
    a select renders as a `combobox "Name *"` line immediately followed by a `generic "<value>"`
    node carrying the chosen value. These are already satisfied and must not be treated as required
    (clicking them hangs the run). Returns normalized names."""
    names = set()
    lines = (snap or '').split('\n')
    for i, line in enumerate(lines):
        m = re.search(r'combobox\s+"([^"]+)"', line)
        if not m:
            continue
        name = m.group(1)
        for nxt in lines[i + 1:i + 3]:
            vm = re.search(r'\bgeneric\s+"([^"]+)"', nxt)
            if not vm:
                continue
            value = vm.group(1).strip()
            low = value.lower()
            if value and re.search(r'[A-Za-z0-9]{2,}', value) and not any(p in low for p in _COMBOBOX_PLACEHOLDERS):
                names.add(normalize_field_name(name))
            break
    return names


def _snapshot_is_error_page(snap: str) -> bool:
    """True when a captured snapshot is the dashboard's crash/not-found screen rather than a real
    page. Used to reject plans that page.goto() a guessed URL which only "worked" because the
    navigation happened — landing on an error page, not a usable form/list."""
    low = (snap or '').lower()
    return (
        'something went wrong' in low or
        'page not found' in low or
        'page doesn' in low or            # "page doesn't exist"
        'oops' in low and 'went wrong' in low
    )


def _page_facts_declare_fields(facts) -> bool:
    """True only if this PAGE_FACTS entry actually lists form fields. Entries that exist purely
    for routing/notes (empty field lists) return False so the live-snapshot required-field
    discovery still runs for them instead of being silently skipped."""
    return bool(
        facts.required_for_draft or facts.required_for_publish or facts.optional_fields
    )


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
# A plan for "edit the topmost video" visited the bare /posts/published and picked row.nth(1),
# which matched the topmost LIVE BLOG instead of a video. Enforced here in addition to prompts, since the
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


# A grounded action step names an EXACT element the planner observed live (e.g.
# "Click get_by_role('button', name='Export Logs')"). A hallucinated step instead HEDGES — it
# describes a generic, unobserved control ("select the desired format (e.g. CSV, Excel)", "click
# the confirm button"). This is how the "Export Activity Logs" test failed twice: the real export
# is a single click on "Export Logs" (emailed asynchronously, confirmed by a toast) with NO format
# picker and NO confirm dialog, yet the planner fabricated a "pick CSV -> confirm" tail from generic
# priors, and the generator compiled it into get_by_title('CSV')/button 'Confirm' locators that match
# nothing. These markers detect that hedge language. They are deliberately narrow — "the confirmation
# dialog" (a real delete-flow pattern) is NOT matched; only "the confirm BUTTON" is. Verified by a
# dry run over every plan.md on disk: flags only genuinely fabricated steps, zero false positives.
_SPECULATIVE_STEP_MARKERS = re.compile(
    r'\be\.g\.'                                                            # enumerated guesses: "e.g., CSV, Excel"
    r'|\bthe desired\b'                                                    # "the desired format"
    r'|\bthe appropriate\b'                                                # "the appropriate option"
    r'|\bthe relevant (?:option|button|link|item|format)\b'
    r'|\bthe correct (?:option|button|link|item|format)\b'
    r'|\bthe (?:confirm|ok|submit|continue|proceed|export|save) button\b'  # generic UNNAMED button
    r'|\bif applicable\b'
    r'|\bas needed\b'
    r'|\bassuming\b'
    r'|\bor similar\b',
    re.IGNORECASE,
)
_ACTION_VERB = re.compile(r'\b(click|select|choose|confirm|pick|toggle|press)\b', re.IGNORECASE)
_QUOTED_TOKEN = re.compile(r"""['"]([^'"]{2,})['"]""")


def _speculative_action_steps(content: str, verified_text: str) -> List[str]:
    """Return numbered STEP lines that describe clicking/selecting a control the planner never
    observed — i.e. an action verb + hedge marker, where the step cites no quoted element name that
    actually appears in a captured snapshot / KNOWN FACTS. A step that names an observed element is
    trusted (other checks, e.g. unverified_titles, validate its exact name)."""
    flagged: List[str] = []
    for line in content.splitlines():
        if not re.match(r'\s*\d+\.\s', line):          # numbered step lines only (not Expected bullets)
            continue
        if not _ACTION_VERB.search(line):              # must be an action step
            continue
        if not _SPECULATIVE_STEP_MARKERS.search(line):  # must hedge
            continue
        quoted = _QUOTED_TOKEN.findall(line)
        if any(tok in verified_text for tok in quoted):  # cites an observed element -> trust it
            continue
        flagged.append(line.strip())
    return flagged


# "Add tab in Navigation" false-negative: a new tab was created + saved, but the plan asserted it was
# visible on the DEFAULT page of a paginated list — and the Navbar tab list appends new rows to the
# END, so the tab landed on page 2 and the page-1 assertion timed out on an item that really exists.
# The reliable, false-positive-free signal for "new item lands on the LAST page" is a list that is
# BOTH paginated AND manually ordered (per-row "Move up"/"Move Down" controls). Newest-first lists
# (published posts, categories) surface a new item on page 1, so they are deliberately NOT matched —
# verified by a dry run over every plan.md (0 current plans flagged; catches the old add-tab plan).
_PAGINATION_CONTROL = re.compile(
    r'listitem "Next Page"|listitem "Previous Page"|ant-pagination|rc-pagination', re.IGNORECASE)
_MANUAL_REORDER = re.compile(
    r'Move this .* up by|"Move Down"|"Move Up"|Move .* position', re.IGNORECASE)
_CREATE_ACTION = re.compile(
    r'\b(?:safe_(?:sequential_)?fill|Create New|Add tab|Add New)\b|click[^\n]*Save', re.IGNORECASE)
_VERIFY_IN_LIST = re.compile(
    r'(?:appears?|present|visible|listed)[^\n]{0,40}(?:list|navigation|table|tab)|to_be_visible',
    re.IGNORECASE)
_PAGES_OR_SEARCHES = re.compile(
    r'Next Page|Previous Page|pagination|last page|Search|filter', re.IGNORECASE)


def _verifies_appended_item_without_paging(content: str, snapshots_text: str) -> bool:
    return bool(
        _PAGINATION_CONTROL.search(snapshots_text)
        and _MANUAL_REORDER.search(snapshots_text)
        and _CREATE_ACTION.search(content)
        and _VERIFY_IN_LIST.search(content)
        and not _PAGES_OR_SEARCHES.search(content)
    )


# Non-semantic "list loaded" assertion. Plans that prove a list/table rendered with a raw CSS container
# or row locator — expect(page.locator('table')).to_be_visible() or a BARE expect(page.locator('tr'))
# .to_be_visible() — are wrong two ways: 'table'/'tbody'/'thead' are non-semantic (locators are
# semantic-only on this dashboard), and a bare 'tr' matches EVERY row, so to_be_visible() is a
# strict-mode "multiple elements" failure at runtime (observed: Verify Categories List Visibility,
# 2026-07-28). The sanctioned single-row idioms — page.locator('tr').filter(...)/.first/.last/.nth —
# are deliberately NOT matched (the negative lookahead skips them), and class/id selectors like
# '.pl-search-bar button' / '.media-listing-card' / '#page-header' never contain a bare table/tr tag.
_NONSEMANTIC_LIST_ASSERT = re.compile(
    r"expect\(\s*page\.locator\(\s*['\"](?:table|tbody|thead)['\"]\s*\)\s*\)\s*\.\s*to_be_visible"
    r"|expect\(\s*page\.locator\(\s*['\"]tr['\"]\s*\)(?!\s*\.(?:filter|first|last|nth|count|all)\b)"
    r"\s*\)\s*\.\s*to_be_visible",
    re.IGNORECASE,
)


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

    visited_paths_in_plan = _extract_goto_paths(content)
    plan_clicks_publish = bool(re.search(r"""name\s*=\s*['\"]Publish['\"]""", content))

    # Required-field enforcement only applies to flows that submit a form. Delete/read-only journeys
    # must not be forced to fill required fields they merely visit -- without this gate, a delete flow
    # that opens a media panel hits an unwinnable rejection loop and burns every planner iteration.
    plan_submits_form = bool(re.search(
        r"""[Cc]lick[^\n]*name\s*=\s*['\"](?:Publish|Save Changes|Save as Draft|Save Category|Save|Update|Create|Submit)['\"]""",
        content,
    ))

    missing_required_fields: List[str] = []
    prefilled_combobox_all: Set[str] = set()
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

    # For visited pages with no field declarations in PAGE_FACTS, read asterisk-marked required fields
    # straight from the snapshot. Gate is "declares fields?" not "has entry?" -- stub entries exist
    # in PAGE_FACTS with empty field lists (e.g. /posts/live-blog/create); keying on entry-presence
    # alone caused those pages to skip both branches, letting a required Permalink field go unenforced
    # and leaving Publish permanently disabled.
    for visited in visited_paths_in_plan:
        facts = PAGE_FACTS.get(visited)
        if not plan_submits_form:
            continue
        if facts is not None and _page_facts_declare_fields(facts):
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

        # Some required markers are standalone "*" nodes adjacent to an unlabelled control
        # (e.g. Web Story's image upload). Reconstruct by pairing a standalone asterisk node
        # with the nearest preceding label text.
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
                # Require the drop-zone's OWN distinctive prompt (e.g. "Upload your Web Story image"),
                # not a bare keyword -- bare "upload" also appears on optional thumbnail buttons.
                # Pick the longest multi-word "Upload ..." prompt in the context window: optional
                # thumbnails have shorter labels and must not shadow the required drop-zone.
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

        # A required combobox that ALREADY shows a selected value (a pre-filled default, e.g.
        # "Response Type *" -> "HTML") is already satisfied and must NOT be demanded — clicking such
        # a control times out at runtime (its value span intercepts the click), so forcing the plan
        # to "handle" it produces a guaranteed-failing step. Drop these from the required set.
        prefilled = _prefilled_combobox_names(snap)
        prefilled_combobox_all |= prefilled
        for raw_name in dict.fromkeys(live_required):
            # ARIA names often embed icon text like "info-circle"; strip it before matching.
            field_name = re.sub(r'\s*info-circle\s*', ' ', raw_name, flags=re.IGNORECASE).strip()
            if not re.search(r'[A-Za-z]{2,}', field_name):
                continue
            if normalize_field_name(field_name) in prefilled:
                continue
            if not _is_field_referenced(field_name, content):
                missing_required_fields.append(f'{visited} -> "{field_name}"')

    has_placeholder = bool(re.search(
        r'\[PLAN VALUE\]|\[ACTUAL TEXT\]|exact-option|\[OBSERVED|\[OPTION|\[YOUR',
        content, flags=re.IGNORECASE
    ))

    # Vague catch-all field step (e.g. "Fill in all other required fields with valid data"). It names
    # no concrete field, so the generator can only emit a placeholder comment for it -- which the
    # spec_validator's placeholder guard then rejects on every iteration, deadlocking generation until
    # the iteration cap. A real fill step must name a specific field ("Display Name *"), so reject the
    # catch-all at the plan source. Matches an action verb + a quantifier (all/any/other/remaining) +
    # "field(s)" on one line; a step naming a specific field has no such quantifier and is unaffected.
    vague_field_step = re.search(
        r'(?im)\b(?:fill|complete|enter|provide|populate|input)\b[^\n]{0,60}'
        r'\b(?:all|any|other|remaining|rest of)\b[^\n]{0,25}\bfields?\b',
        content,
    )

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
    # `visited_paths_in_plan` strips query strings (the extracted path doubles as a PAGE_FACTS
    # dict key), so it CANNOT tell a bare /posts/published from a filtered one — both collapse to
    # '/posts/published'. Detecting "bare" from that list therefore false-positives on a correctly
    # filtered URL (…/posts/published?page_type=Article…) and rejects a valid plan forever.
    # Inspect the raw plan text instead: a /posts/published navigation
    # is only "bare" when it lacks the page_type= content-type filter.
    _published_refs = re.findall(r"/posts/published(?!/geographies)(?:\?[^\s'\"`)]*)?", content)
    visits_bare_published_list = any('page_type=' not in ref for ref in _published_refs)
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

    def _was_visited(path: str) -> bool:
        return len(snapshot_cache) > 0 and any(v_path.find(path) != -1 for v_path in visited_url_paths)

    # A create/edit destination (…/create, …/new, …/edit/<id>) must be REACHED AND CONFIRMED live,
    # never accepted just because it matches a known prefix — a guessed URL slips through on prefix
    # alone and 404s at runtime. Grounding create/edit URLs in an actual visit forces the planner
    # to discover the real page via the error-page rescue instead of inventing one.
    def _is_create_like(path: str) -> bool:
        return bool(re.search(r'/(?:create|new)(?:\?|$)|/edit/', path))

    unvalidated_paths = []
    for p in visited_paths_in_plan:
        if _is_create_like(p):
            if not _was_visited(p):
                unvalidated_paths.append(p)
        elif not (any(p.startswith(prefix) for prefix in KNOWN_PATH_PREFIXES) or _was_visited(p)):
            unvalidated_paths.append(p)

    # Error-page goto guard (general, no hardcoding): a plan whose page.goto() lands on the
    # dashboard's crash screen ("Oops, something went wrong") is worthless — yet such a URL slips
    # past the unvalidated-paths check above, because the planner DID navigate there so the URL is
    # "visited". Reject any goto whose captured snapshot is an error page — this forces the
    # planner to discover the real create page by clicking through the UI instead of inventing a URL.
    error_page_goto_paths: List[str] = []
    for visited in visited_paths_in_plan:
        for url, snapshot in snapshot_cache.items():
            try:
                snap_path = urlparse(url).path
            except Exception:
                snap_path = url
            if visited and snap_path.find(visited) != -1:
                if _snapshot_is_error_page(snapshot):
                    error_page_goto_paths.append(visited)
                break

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

    # Edit journeys reach a form by clicking a row's Edit control -- that form URL is never in
    # visited_paths_in_plan or PAGE_FACTS. Only reject a fill label if it is absent from both
    # known facts AND every live snapshot the planner captured.
    reaches_clicked_edit_form = bool(re.search(
        r"(?:get_by_role|getByRole)\(\s*['\"](?:button|link)['\"]\s*,\s*(?:name\s*=\s*|\{\s*name:\s*)['\"]Edit\b",
        content, flags=re.IGNORECASE
    ))
    # Dialog-launched flows (launch_button set) fill fields that live INSIDE a dialog/wizard, not on
    # the landing page. The read-only planner cannot reliably snapshot those fields (opening the
    # dialog is flaky under the MCP browser), so they appear neither in PageFacts' flat field lists
    # nor in any captured snapshot -- and unknown_fill_labels would reject every real dialog field
    # ("Display Name *") forever. The fields are documented in the page's note and the runner (real
    # pytest, not read-only) exercises them for real, so exempt these flows from the fill-label
    # existence check rather than deadlocking the planner on an unverifiable requirement.
    visits_dialog_launcher = any(
        PAGE_FACTS.get(p) is not None and getattr(PAGE_FACTS[p], 'launch_button', None)
        for p in visited_paths_in_plan
    )
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
        if (all_visited_have_facts and not reaches_clicked_edit_form
            and not visits_dialog_launcher) else []
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
        # Plans are written in PROSE, so the enabled-wait step reads either as code
        # ("expect(get_by_role('button', name='Publish')).to_be_enabled(...)") or as prose
        # ("Expect get_by_role('button', name='Publish') to be enabled with timeout=15000").
        # Accept BOTH the underscore code form and the spaced prose form on the button's line —
        # requiring only the underscore literal rejected valid prose plans forever.
        has_enabled_wait = bool(re.search(
            rf"name\s*=\s*['\"]{re.escape(btn)}['\"][^\n]*(?:to_be_enabled|to\s+be\s+enabled|be\s+enabled)",
            content, flags=re.IGNORECASE
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

    # A plan step that CLICKS a pre-filled combobox (already showing a default value) will hang at
    # runtime — the selected-value span intercepts the click. Such a control needs no interaction.
    # Flag any get_by_role('combobox', name='<prefilled>') the plan clicks so it gets removed.
    prefilled_combobox_interactions: List[str] = []
    for cb_name in prefilled_combobox_all:
        for m in re.finditer(r"get_by_role\(\s*['\"]combobox['\"]\s*,\s*name\s*=\s*['\"]([^'\"]+)['\"]", content):
            if normalize_field_name(m.group(1)) == cb_name:
                prefilled_combobox_interactions.append(m.group(1))
                break

    # Vacuous-emptiness false pass (see spec_validator.py for the full mechanism): locator.count()
    # does NOT auto-wait and to_have_count(0) is satisfied the instant a locator matches nothing, so a
    # deletion plan that guards its loop with .count() or asserts success with to_have_count(0) —
    # without first proving the rows rendered — becomes a green test that deletes nothing.
    # The endorsed delete pattern already waits for
    # the row (dashboard_facts: row.wait_for(state='visible')), so correct plans are not flagged.
    plan_asserts_empty = (
        bool(re.search(r"\.to_have_count\(\s*0\b", content)) or
        bool(re.search(r"\b(?:while|for each|for every)\b[^\n]*\.count\(\)", content, flags=re.IGNORECASE))
    )
    plan_proves_rows_rendered = bool(
        re.search(r"\.wait_for\(\s*state\s*=\s*['\"](?:visible|attached)['\"]", content) or
        re.search(r"\.to_have_count\(\s*[1-9][0-9]*\b", content) or
        re.search(r"\.to_be_visible\(", content)
    )
    emptiness_without_existence = plan_asserts_empty and not plan_proves_rows_rendered

    is_ctb_plan = bool(re.search(r'configurations/content-type-builder', content))
    ctb_created_by_filter = is_ctb_plan and bool(
        re.search(r"[Cc]reated [Bb]y", content) and
        re.search(r"(?:filter|safe_sequential_fill|textbox|search)", content, re.IGNORECASE)
    )

    # Reject action steps that click/select a control the planner never observed (hedge language,
    # no observed element named). all_verified_text = system prompt (KNOWN FACTS) + every captured
    # snapshot, so a step naming a real element is trusted.
    speculative_action_steps = _speculative_action_steps(content, all_verified_text)

    # Reject a create-then-verify plan that asserts the new item on the default page of a paginated,
    # manually-ordered (append-to-end) list — the item lands on the LAST page (see add-tab in nav).
    verifies_appended_without_paging = _verifies_appended_item_without_paging(content, snapshots_text)

    # Reject "list loaded" proofs that assert a bare CSS table/row locator (non-semantic + bare 'tr'
    # is a strict-mode multi-match). The spec sanitizer also narrows a bare 'tr' to .first as a
    # runtime safety net; this steers the planner to a semantic, singular assertion up front.
    nonsemantic_list_assert = bool(_NONSEMANTIC_LIST_ASSERT.search(content))

    if (
        not has_flow or not has_scenario or not has_steps or has_errors or
        missing_permalink or len(unvalidated_paths) > 0 or len(error_page_goto_paths) > 0 or
        has_placeholder or vague_field_step or
        len(unverified_titles) > 0 or len(missing_required_fields) > 0 or
        len(forbidden_goto_matches) > 0 or wrong_save_button or len(unknown_fill_labels) > 0 or
        len(missing_enabled_wait) > 0 or len(hardcoded_virtualized_titles) > 0 or
        content_type_bleed or len(wrong_fill_react_in_plan) > 0 or emptiness_without_existence or
        len(prefilled_combobox_interactions) > 0 or ctb_created_by_filter or
        len(speculative_action_steps) > 0 or verifies_appended_without_paging or
        nonsemantic_list_assert
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
        if vague_field_step:
            issues.append(
                f'plan contains a vague catch-all field step ("{vague_field_step.group(0).strip()}") that '
                'names no specific field. The generator cannot turn "all/other/remaining required fields" into '
                'real code -- it emits a placeholder comment, which is rejected every iteration until generation '
                'deadlocks. Either name each field explicitly as its own step (e.g. safe_sequential_fill(page, '
                '"Display Name *", ...)), or DELETE the step if there are no other required fields. Use ONLY the '
                'fields you observed in the live snapshot -- do not invent fields from the test title.'
            )
        if missing_permalink:
            issues.append(
                'article creation flow is missing the required "English Title ( Permalink ) *" step -- '
                'this field is mandatory (along with Title * and Primary Category) or Save as Draft stays permanently disabled. '
                "Add a step: \"Use safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}', delay=50) to fill the permalink field\""
            )
        if len(unvalidated_paths) > 0:
            # Surface exact create/edit URLs already in snapshot_cache so the model can paste the
            # correct one instead of re-guessing, which is what actually unblocks the loop.
            visited_create_urls = [
                u for u in snapshot_cache.keys()
                if re.search(r'/(?:create|new)(?:\?|$)|/edit/', urlparse(u).path if '://' in u else u)
            ]
            visited_hint = (
                '\nYou DID visit these real create/edit pages this session — use one of these EXACT '
                f'URLs in page.goto() instead of guessing: {", ".join(visited_create_urls)}'
                if visited_create_urls else ''
            )
            issues.append(
                f'unverified URL path(s): {", ".join(unvalidated_paths)} -- '
                'these were not visited during this session and do not match any known dashboard route. '
                'A create/edit URL must be one you actually reached and snapshotted — do NOT invent a '
                'plausible-looking path. Navigate there by clicking: snapshot the sidebar -> browser_click '
                'the feature link/Create button -> snapshot to confirm the URL -> use that URL in the plan.'
                f'{visited_hint}'
            )
        if len(error_page_goto_paths) > 0:
            issues.append(
                f'page.goto() target(s) that landed on the "Oops, something went wrong" error page: '
                f'{", ".join(error_page_goto_paths)} -- this is a GUESSED URL that does not exist, not a '
                'real page. Do NOT write a plan on top of an error page. Discover the real create page by '
                'driving the UI: navigate to /posts/published, find the content type in the left "Content '
                'Type" list, click its "+" Create button to open the "Choose a … Type" popover, then click '
                'the option you want. Read the "- Page URL:" from the resulting snapshot and use THAT exact '
                'URL in your page.goto() step. Never invent a URL like /canvas/create.'
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
        if emptiness_without_existence:
            issues.append(
                'plan asserts deletion success with to_have_count(0) (and/or loops on locator.count()) but never '
                'first proves the target rows rendered. locator.count() does NOT auto-wait, and to_have_count(0) is '
                'satisfied the instant the locator matches nothing, so during the async list-render gap right after '
                'page.goto() the count is 0: the delete loop is skipped (nothing is deleted) and the emptiness '
                'assertion passes vacuously — a green test that deletes nothing (confirmed "delete all QA galleries" '
                'false pass). Add a step BEFORE the loop/assertion that waits for the list to actually render: '
                "\"Wait for the list to load using rows = page.locator('tr').filter(has_text=title); "
                "rows.first.wait_for(state='visible', timeout=15000)\". Then the delete loop guarded by rows.count() "
                'and the final expect(rows).to_have_count(0, timeout=15000) become meaningful (0 == removed, not '
                '0 == never loaded).'
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
        if len(prefilled_combobox_interactions) > 0:
            quoted = ', '.join(f'"{n}"' for n in prefilled_combobox_interactions)
            issues.append(
                f'plan clicks/opens combobox(es) that are ALREADY pre-filled with a default value: '
                f'{quoted}. An Ant Design select that already shows a value renders that value on top '
                'of the control, so clicking it TIMES OUT and kills the run. These fields are already '
                'satisfied — REMOVE the click/select step(s) for them entirely (do not open them, do '
                'not pick an option). If you want to note them, add a plain note like "Response Type '
                'is pre-set to its default — no action needed" instead of an interaction step.'
            )
        if re.search(
            r"(?:safe_(?:sequential_)?fill\s*\([^)]*?"
            r"|get_by_role\(\s*['\"]textbox['\"]\s*,\s*name\s*=\s*)['\"]Featured Video \*['\"]",
            content,
        ):
            issues.append(
                'plan fills/locates "Featured Video *" directly, but that is a LABEL, not a textbox -- '
                'the video is attached through a dialog, not by filling this field, so this step matches '
                'nothing and times out at runtime. Rewrite the step as: '
                "(1) click get_by_role('button', name='Add Featured Video') to open the Embed Media dialog, "
                "(2) safe_fill(page, 'Media URL *', '<real embeddable video URL>'), "
                "(3) click get_by_role('button', name='Submit'). Do this BEFORE filling Title/Permalink. "
                'Remove the direct "Featured Video *" fill step entirely.'
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
        if len(speculative_action_steps) > 0:
            quoted = '; '.join(f'"{s}"' for s in speculative_action_steps)
            issues.append(
                f'plan contains speculative action step(s) that click/select a control you never '
                f'observed: {quoted}. These hedge ("the desired…", "e.g. …", "the confirm button") '
                'instead of naming an exact element from a snapshot you captured — the generator then '
                'invents a locator (get_by_title(\'CSV\'), button \'Confirm\', …) that matches nothing '
                'and times out. This is exactly how the Export Activity Logs flow failed: it is a '
                'SINGLE click on "Export Logs" (the export is emailed; a toast "We will email you the '
                'exported data once done." confirms it) with NO format picker and NO confirm dialog. '
                'For each flagged step: either name the EXACT element you saw in the live snapshot '
                "(e.g. Click get_by_role('button', name='<observed name>')), or DELETE the step if the "
                'flow already ended — then assert the observed result (a toast/URL change/visible text) '
                'instead of inventing follow-up actions. Never guess a format-selection or confirm step.'
            )
        if verifies_appended_without_paging:
            issues.append(
                'plan verifies a newly created item is visible in a list that is BOTH paginated (an '
                'Ant pagination control is in the live snapshot) AND manually ordered (per-row '
                '"Move up"/"Move Down" buttons), so new rows are APPENDED TO THE END and the item lands '
                'on the LAST page. Asserting visibility on the default page is a FALSE NEGATIVE — the '
                '"Add tab in Navigation" test failed exactly this way (tab created on page 2, assertion '
                'checked page 1). Add a step BEFORE the assertion that advances to the last page: '
                "next = get_by_role('listitem', name='Next Page'); click its button repeatedly until it "
                'is disabled (or count()==0), THEN assert get_by_text(<value>, exact=True).to_be_visible(). '
                'Do NOT add paging for newest-first lists (published posts, categories) where a new item '
                'appears on page 1 — this rule only applies to manually-ordered append-to-end lists.'
            )
        if nonsemantic_list_assert:
            issues.append(
                'plan proves a list/table loaded with a NON-SEMANTIC CSS locator — '
                'expect(page.locator("table")).to_be_visible() or a bare '
                'expect(page.locator("tr")).to_be_visible(). "table"/"tbody"/"thead" are banned '
                '(locators are semantic-only on this dashboard), and a bare "tr" matches EVERY row, so '
                'to_be_visible() is a strict-mode "multiple elements" failure at runtime (this is exactly '
                'how Verify Categories List Visibility failed). Assert a SPECIFIC visible element instead: '
                'a known row via rows = page.locator("tr").filter(has_text="<unique cell text>"); '
                'expect(rows.first).to_be_visible(timeout=15000), or a real cell/header via '
                'get_by_role("cell"/"columnheader", name="...") / get_by_text("<header>", exact=True). '
                '(The sanctioned page.locator("tr").filter(...)/.first/.nth idioms are fine.)'
            )
        if ctb_created_by_filter:
            issues.append(
                'CTB plan uses a "Created By" filter — no such filter input exists on the '
                'custom-component list page. The ONLY filter is textbox "Search" (filters by name). '
                'The "Updated By" column header has NO corresponding filter input. '
                'Remove the "Created By" step entirely and filter only by component name using Search.'
            )
        return '; '.join(issues)

    return None
