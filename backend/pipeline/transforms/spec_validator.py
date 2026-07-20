import re
from typing import List, Optional, Set

from pipeline.knowledge.dashboard_facts import PAGE_FACTS
from .plan_validator import (
    extract_fill_labels,
    find_hardcoded_virtualized_titles,
    normalize_field_name,
    _field_distinctive_tokens,
    _is_field_referenced,
    _page_facts_declare_fields,
)


def validate_spec_semantics(code: str) -> Optional[str]:
    issues: List[str] = []

    is_article_or_custom_page_create = bool(
        re.search(r"goto\(['\"]\/posts\/article\/create['\"]\)", code) or
        re.search(r"goto\(['\"]\/posts\/custom-page\/create['\"]\)", code)
    )

    is_article_publish_flow = (
        is_article_or_custom_page_create and
        (bool(re.search(r"get_by_role\('button',\s*name=['\"]Publish['\"]\)", code)) or
         bool(re.search(r'to_have_url\(.*\/posts\/published\b', code)))
    )

    if is_article_publish_flow:
        if not re.search(r"'Summary'", code):
            issues.append(
                'publish flow is missing a Summary fill step -- Summary must have at least 140 characters. '
                "Add: safe_fill(page, 'Summary', f'QA summary {ts} -- this is a long enough summary for "
                "the publish validation check to pass on the PubLive dashboard.')"
            )
        if not re.search(r"'Meta Description'", code):
            issues.append(
                'publish flow is missing a Meta Description fill step -- Meta Description must be 140-170 characters. '
                "Add: safe_fill(page, 'Meta Description', f'QA meta description {ts} -- written for the "
                "publish validation check, between 140 and 170 chars total length')"
            )

    is_create_flow = bool(
        re.search(r"goto\(['\"]\/posts\/article\/create['\"]\)", code) or
        re.search(r"goto\(['\"]\/posts\/custom-page\/create['\"]\)", code)
    )

    if is_create_flow and not re.search(r'English Title', code) and re.search(r'Save as Draft', code):
        issues.append(
            "create flow is missing 'English Title ( Permalink ) *' -- without it 'Save as Draft' stays disabled. "
            "Add after safe_sequential_fill(page, 'Title *', ...): "
            "safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}', delay=50)"
        )

    if re.search(r'\.to_have_url\(', code) and not re.search(r'\.to_have_url\(.*timeout', code):
        issues.append(
            'to_have_url() assertions are missing timeout=15000 -- '
            'redirects after form save can take several seconds. '
            'Change all to_have_url(...) -> to_have_url(..., timeout=15000)'
        )

    if re.search(r"page\.locator\(\s*['\"]text=", code):
        issues.append(
            'page.locator("text=...") is forbidden -- text= substring-matches and hits strict-mode violations. '
            'For locating by text: page.get_by_text("exact text", exact=True) or '
            'page.get_by_role("heading", name="..."). '
            'Playwright auto-scrolls on .click() so no separate scroll step is needed.'
        )

    if re.search(r':contains\(', code) or re.search(r':has-text\(', code):
        issues.append(
            'jQuery-style selector detected (":contains()" or ":has-text()") -- these are NOT valid CSS. '
            'Replace with Playwright semantic locators: page.get_by_text("..."), '
            'page.get_by_role("heading", name="..."), or page.locator("h2", has_text="...").'
        )

    # The Media Library (/media) is a card GRID, not a table -- it has zero <tr> elements. A spec that
    # navigates there and uses page.locator('tr') / get_by_role('row') (copied from the table-based list
    # pages) matches nothing and times out.
    navigates_media = bool(re.search(r"goto\(['\"]\/media['\"]\)", code))
    uses_table_row_locator = bool(
        re.search(r"page\.locator\(\s*['\"]tr['\"]", code) or
        re.search(r"get_by_role\(\s*['\"]row['\"]", code)
    )
    # /media's search button is icon-only -- get_by_role('button', name='Search') matches nothing. Use '.pl-search-bar button' or press Enter.
    uses_phantom_search_button = bool(re.search(r"get_by_role\(\s*['\"]button['\"]\s*,\s*name\s*=\s*['\"]Search['\"]", code))
    if navigates_media and (uses_table_row_locator or uses_phantom_search_button):
        issues.append(
            "spec navigates to /media (the Media Library) but uses a table/named-Search-button pattern copied from "
            "the list pages. /media is a card GRID with NO <tr> elements, and its magnifier search button is "
            "ICON-ONLY with no accessible name (get_by_role('button', name='Search') matches nothing). Correct flow: "
            "box = page.get_by_role('textbox', name='Search by name, path, or alt text'); box.fill(filename); "
            "page.locator('.pl-search-bar button').click()  # icon-only search button (or box.press('Enter')). "
            "The filename is NOT rendered as card text, so do not filter by has_text; the search narrows the grid, "
            "so take the sole result: card = page.locator('.media-listing-card').first; "
            "card.wait_for(state='visible', timeout=15000). Delete: card.click(); "
            "page.get_by_role('button', name='Delete', exact=True).click(); "
            "page.get_by_role('dialog').get_by_role('button', name='Delete').click(). "
            "Assert gone against the grid: expect(page.locator('.media-listing-card')).to_have_count(0, timeout=15000)."
        )

    # '.pl-search-bar button' is sanctioned for /media ONLY -- the icon-only search button exists nowhere
    # else. Generators copy this onto list pages where it times out, AND list pages don't auto-apply
    # on fill: press Enter in the box or click the page's own search icon, not '.pl-search-bar button'.
    if re.search(r"locator\(\s*['\"][^'\"]*\.pl-search-bar", code) and not navigates_media:
        issues.append(
            "spec uses '.pl-search-bar button' but does not navigate to /media. That selector is a "
            "/media-ONLY sanctioned CSS exception (the Media Library's icon-only search button) and does "
            "NOT exist on the posts/published list pages, so the click times out. On the published/list "
            "pages the search box also does not auto-apply on fill -- run the search by pressing Enter in "
            "the box: safe_fill(page, '<search label>', term); "
            "page.get_by_role('textbox', name='<search label>').press('Enter'). Remove the "
            "'.pl-search-bar button' click entirely."
        )

    # GENERAL RULE: search/filter boxes never auto-apply on fill -- the typed value only takes effect
    # when Enter is pressed or the search button is clicked. A spec that fills a search box without
    # triggering it silently searches nothing: the list stays unfiltered and row/card locators match
    # the wrong item or time out.
    fills_search_box = bool(
        re.search(r"safe_(?:sequential_)?fill\s*\(\s*page\s*,\s*['\"][^'\"]*(?:[Ss]earch|[Ff]ilter)[^'\"]*['\"]", code) or
        re.search(r"get_by_(?:role\(\s*['\"]textbox['\"]\s*,\s*name\s*=\s*|placeholder\(\s*)['\"][^'\"]*(?:[Ss]earch|[Ff]ilter)[^'\"]*['\"]\s*\)\s*\.fill\(", code)
    )
    has_search_trigger = bool(
        re.search(r"\.press\(\s*['\"]Enter['\"]", code) or
        re.search(r"locator\(\s*['\"][^'\"]*\.pl-search-bar", code) or
        re.search(r"get_by_role\(\s*['\"]button['\"]\s*,\s*name\s*=\s*['\"][^'\"]*[Ss]earch[^'\"]*['\"][^)]*\)\s*\.click", code)
    )
    if fills_search_box and not has_search_trigger:
        issues.append(
            "spec fills a search/filter box but never RUNS the search. On this dashboard a search box does "
            "NOT auto-apply on fill -- the typed value only takes effect when you press Enter in the box or "
            "click the page's search button. Filling without triggering searches nothing, so the list stays "
            "unfiltered and the row/card locator matches the wrong item or times out. Add a trigger right "
            "after the fill: page.get_by_role('textbox', name='<search label>').press('Enter') (works on "
            "every page). On /media you may instead click the icon-only search button: "
            "page.locator('.pl-search-bar button').click()."
        )

    # [^)]* ensures name= is inside the get_by_role() parens, not in a chained method call
    if re.search(r"get_by_role\(['\"]row['\"][^)]*\bname\s*=", code):
        issues.append(
            "get_by_role('row', name=...) detected — Ant Design tr elements have NO accessible name. "
            "This locator always times out on the live dashboard. "
            "Replace with: row = page.locator('tr').filter(has_text=title) then row.wait_for(state='visible', timeout=15000)"
        )

    # page.locator('tr').nth(N) (no .filter in between) indexes raw <tr> elements, but Ant Design
    # renders a hidden aria-hidden="true" "ant-table-measure-row" as the literal first <tr> in <tbody>
    # (plus the header <tr>), so .nth(1) resolves to that invisible measure row and wait_for(visible)
    # times out. Use the accessibility tree, which skips aria-hidden rows.
    if re.search(r"\.locator\(\s*['\"]tr['\"]\s*\)\s*\.nth\(", code):
        issues.append(
            "page.locator('tr').nth(N) detected — Ant Design renders a hidden aria-hidden='true' "
            "'ant-table-measure-row' as the first <tr> in <tbody>, so .nth(1) hits that invisible row and "
            "wait_for(state='visible') times out. Use get_by_role('row').nth(N) for positional access "
            "(the a11y tree skips aria-hidden rows, so nth(0) is the header and nth(1) is the first real "
            "data row), or page.locator('tr').filter(has_text=title).first to target a row by content."
        )

    # Ban get_by_role('dialog', name=...) because POST content-type dialog titles vary by type.
    # EXCEPTION: a few dialog names are verified-live-stable across every context and are the
    # documented way to wait for that dialog — e.g. the Content-Type-Builder field-add dialog,
    # whose name is identical for all field types. Allowlist those so specs can follow the facts.
    _STABLE_DIALOG_NAMES = {'add a field in your content type'}
    _dialog_names = re.findall(
        r"get_by_role\(['\"]dialog['\"][^)]*\bname\s*=\s*['\"]([^'\"]+)['\"]", code
    )
    if any(n.strip().lower() not in _STABLE_DIALOG_NAMES for n in _dialog_names):
        issues.append(
            "get_by_role('dialog', name=...) detected — dialog titles vary by content type and are unreliable. "
            "This locator will fail on any content type other than the one it was written for. "
            "Replace with: page.get_by_role('dialog').get_by_role('button', name='Delete').click()"
        )

    if re.search(r'page\.evaluate\([^)]*document\.querySelector', code):
        issues.append(
            'page.evaluate(() => document.querySelector(...)) detected -- this pattern is forbidden. '
            'Use Playwright locators instead: locator.scroll_into_view_if_needed() for scrolling, '
            "page.get_by_text(...) for finding text. Raw DOM access bypasses Playwright's auto-waiting."
        )

    one_click_publish_paths = [
        p for p, f in PAGE_FACTS.items()
        if f.save_button == 'Publish' and len(f.publish_flow) == 0
    ]
    navigates_to_one_click_publish = any(
        re.search(r"goto\(['\"]" + re.escape(p) + r"['\"]\)", code)
        for p in one_click_publish_paths
    )
    uses_save_as_draft_in_spec = bool(re.search(r"""['"]Save as Draft['"]""", code))
    if navigates_to_one_click_publish and uses_save_as_draft_in_spec and not is_article_or_custom_page_create:
        issues.append(
            "spec uses 'Save as Draft' but navigates to a one-click-publish entity page. "
            'These entity pages have ONLY a "Publish" button -- there is no "Save as Draft" button. '
            "Replace get_by_role('button', name='Save as Draft').click() with "
            "get_by_role('button', name='Publish').click(), remove any page.goto('/posts/draft') step, "
            'and assert the URL changes directly to the published list path.'
        )

    navigated_paths = [p for p in (
        m.group(1) for m in re.finditer(r"page\.goto\(['\"]([^'\"]+)['\"]\)", code)
    ) if p.startswith('/')]
    navigated_facts = [PAGE_FACTS[p] for p in navigated_paths if PAGE_FACTS.get(p) is not None]
    # A page counts as "having field facts" only if it declares fields. Stub entries exist in PAGE_FACTS
    # with empty field lists (e.g. /posts/live-blog/create); treating them as fully specced makes the
    # unknown-fill-labels check conclude NO label is valid and reject every fill. Shares the same
    # "declares fields?" predicate with plan_validator via the canonical _page_facts_declare_fields helper.
    all_navigated_have_facts = (
        len(navigated_paths) > 0 and
        all(
            PAGE_FACTS.get(p) is not None and _page_facts_declare_fields(PAGE_FACTS[p])
            for p in navigated_paths
        )
    )
    known_fields_in_spec: Set[str] = set()
    for facts in navigated_facts:
        for f in [*facts.required_for_draft, *facts.required_for_publish, *facts.optional_fields]:
            known_fields_in_spec.add(normalize_field_name(f.field))

    # A search/filter textbox (e.g. "Search by name, path, or alt text" on /media) is NOT a form field --
    # it must never be validated against a page's form-field facts. Otherwise a delete/search flow gets
    # rejected forever because the search box isn't in PAGE_FACTS' upload/create field list.
    def _is_search_or_filter_box(label: str) -> bool:
        return bool(re.search(r'\b(search|filter)\b', label, flags=re.IGNORECASE))

    spec_fill_labels = extract_fill_labels(code)
    unknown_fill_labels = (
        [
            l for l in spec_fill_labels
            if normalize_field_name(l) not in known_fields_in_spec and not _is_search_or_filter_box(l)
        ]
        if all_navigated_have_facts else []
    )
    if len(unknown_fill_labels) > 0:
        valid_per_page_parts: List[str] = []
        for p in navigated_paths:
            f = PAGE_FACTS.get(p)
            if f is None:
                continue
            labels = [
                f'"{field.field}"'
                for field in [*f.required_for_draft, *f.required_for_publish, *f.optional_fields]
            ]
            if len(labels) > 0:
                valid_per_page_parts.append(f'  {p} -> valid fill labels: {", ".join(labels)}')
        valid_per_page = '\n'.join(valid_per_page_parts)
        quoted_labels = ', '.join(f'"{l}"' for l in unknown_fill_labels)
        issues.append(
            f'spec fills field(s) that do not exist on any navigated page: {quoted_labels}. '
            f'The ONLY valid fill labels for the navigated URL(s) are:\n{valid_per_page}\n'
            'Rewrite the spec using ONLY these labels. Remove every safe_fill/safe_sequential_fill call for any '
            'other field.'
        )

    # Detect false-positive URL traps: the spec navigates to a /XYZ/new page and then asserts
    # to_have_url with r'/XYZ/' — which matches the creation URL itself, so the assertion passes
    # even if the save fails and the page never leaves /XYZ/new.
    new_url_match = re.search(r"page\.goto\(['\"]([^'\"]+/new)['\"]", code)
    if new_url_match:
        base = new_url_match.group(1).rsplit('/new', 1)[0]
        prefix_with_slash = re.escape(base + '/')
        if re.search(r"to_have_url\(re\.compile\(r'" + prefix_with_slash + r"'\)", code):
            issues.append(
                f"to_have_url assertion r'{base}/' matches the creation URL '{base}/new' itself — "
                "the assertion passes even when the save fails and the page stays on /new. "
                f"Use a negative lookahead anchored after the path base: re.compile(r'{base}(?!/new)') "
                f"(NOT r'{base}/(?!new)' — that form requires a trailing slash and fails when the redirect goes to {base} without one)"
            )

    # Vacuous-emptiness false pass: locator.count() does NOT auto-wait, and to_have_count(0) is
    # satisfied the instant nothing matches. Dashboard rows render asynchronously after page.goto(),
    # so a delete loop guarded by `while rows.count() > 0` passes vacuously during the render gap --
    # the body never runs and the emptiness assertion is trivially true. Require a positive existence
    # wait before the count guard so count==0 means "removed", not "never loaded".
    uses_count_guard = bool(re.search(r"\b(?:while|if)\b[^\n:]*\.count\(\)", code))
    asserts_empty = bool(re.search(r"\.to_have_count\(\s*0\b", code))
    if uses_count_guard or asserts_empty:
        proves_rows_rendered = bool(
            re.search(r"\.wait_for\(\s*state\s*=\s*['\"](?:visible|attached)['\"]", code) or
            re.search(r"\.to_have_count\(\s*[1-9][0-9]*\b", code) or
            re.search(r"\.to_be_visible\(", code)
        )
        if not proves_rows_rendered:
            issues.append(
                'spec relies on locator.count() as a loop guard and/or asserts deletion success with '
                'to_have_count(0), but never first proves the target rows rendered. locator.count() does NOT '
                'auto-wait, and to_have_count(0) is satisfied the instant the locator matches nothing, so during '
                'the async list-render gap right after page.goto() the count is 0: the delete loop body never runs '
                '(nothing is deleted) and the emptiness assertion passes vacuously — a green test that deletes '
                'nothing. Before the loop / assertion, wait for the '
                "list to actually render: rows = page.locator('tr').filter(has_text=title); "
                "rows.first.wait_for(state='visible', timeout=15000). Then keep the delete loop guarded by "
                'rows.count() AFTER that wait, and the final expect(rows).to_have_count(0, timeout=15000) is '
                'meaningful (0 == removed, not 0 == never loaded).'
            )

    if re.search(
        r'details\s+(omitted|not\s+specified)|omitted\s+(as|because)'
        r'|assuming\s+(?:there\s+are\s+)?(?:other|additional|more)\s+(?:required\s+)?fields?'
        r'|fill\s+(?:them|it|the\s+(?:rest|other\s+fields?))\s+here'
        r'|other\s+required\s+field'
        r'|<[a-z ]*required[a-z ]*>',
        code,
        flags=re.IGNORECASE,
    ):
        issues.append(
            'spec contains a placeholder comment (e.g. "details omitted", "assuming there are other '
            'required fields", "fill them here"), indicating one or more '
            'plan steps were dropped instead of translated to code. EVERY step in the plan must produce code. '
            'For value comboboxes with "first available option", use '
            "page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first.click()."
        )

    # React-controlled fields fire no onChange on .fill() — the value never registers and
    # the Publish/Save button stays permanently disabled. Enforce safe_sequential_fill for every
    # field marked react_controlled=True in PAGE_FACTS for the pages this spec navigates to.
    seen_rc: Set[str] = set()
    react_controlled_fields_in_scope = []
    for facts in navigated_facts:
        for f in [*facts.required_for_draft, *facts.required_for_publish, *facts.optional_fields]:
            if f.react_controlled and f.field not in seen_rc:
                seen_rc.add(f.field)
                react_controlled_fields_in_scope.append(f.field)
    wrong_fill_react = [
        label for label in react_controlled_fields_in_scope
        if re.search(
            r'(?<![a-zA-Z_])safe_fill\s*\(\s*page\s*,\s*[\'"]' + re.escape(label) + r'[\'"]',
            code
        )
    ]
    if wrong_fill_react:
        quoted = ', '.join(f'"{l}"' for l in wrong_fill_react)
        issues.append(
            f'spec uses safe_fill() on React-controlled field(s): {quoted}. '
            'React-controlled inputs do not fire onChange on .fill() — the value does not register '
            'and the Publish/Save button stays permanently disabled. '
            "Replace every flagged call with safe_sequential_fill(page, '<field>', value, delay=50)."
        )

    # Permalink is React-controlled on every create page -- safe_fill() leaves Publish permanently
    # disabled. Per-page enforcement above only fires for pages with hand-verified PAGE_FACTS; this
    # catches the rest by label regardless of facts coverage.
    permalink_safe_fill = [
        label
        for label in extract_fill_labels(code)
        if 'permalink' in label.lower()
        and label not in wrong_fill_react
        and re.search(
            r'(?<![a-zA-Z_])safe_fill\s*\(\s*page\s*,\s*[\'"]' + re.escape(label) + r'[\'"]',
            code
        )
    ]
    if permalink_safe_fill:
        quoted = ', '.join(f'"{l}"' for l in permalink_safe_fill)
        issues.append(
            f'spec uses safe_fill() on the React-controlled Permalink field: {quoted}. '
            'The permalink-uniqueness check only reacts to real keystroke events, so safe_fill() '
            'leaves Publish/Save permanently disabled even with a valid unique value. '
            "Replace every flagged call with safe_sequential_fill(page, '<field>', value, delay=50)."
        )

    # NOTE: the Title->Permalink debounce wait (page.wait_for_timeout(500) between the two fills) is no
    # longer validated/rejected here. It is inserted deterministically for EVERY flow by
    # spec_sanitizer._insert_permalink_debounce_wait whenever a 'Title *' fill is followed by a Permalink
    # fill, so there is nothing for the generator to get wrong and no reason to burn a retry over it.

    hardcoded_virtualized_titles = find_hardcoded_virtualized_titles(code)
    if len(hardcoded_virtualized_titles) > 0:
        quoted = ', '.join(f'{name} -> "{title}"' for name, title in hardcoded_virtualized_titles)
        issues.append(
            f'spec hardcodes a get_by_title() option for a virtualized, per-publisher combobox: {quoted}. '
            'The option list is virtualized (only ~9 of 65+ options render at once) and the option set changes '
            'per publisher and over time, so a hardcoded title that exists now can time out on a later run. '
            "Replace with: page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first"
            ".wait_for(state='visible') then .click() -- or, if a specific option is required, "
            "cb.fill('<name>') to filter first, then click the first .ant-select-item-option match."
        )

    # CTB (Content Type Builder) button-name sanity checks.
    is_ctb_flow = bool(re.search(r"goto\(['\"][^'\"]*configurations/content-type-builder", code))
    if is_ctb_flow:
        m_wrong_create = re.search(
            r"get_by_role\('button',\s*name=['\"](?:Add Custom Component|Add New Component|New Component|Add Component)['\"]",
            code,
        )
        if m_wrong_create:
            issues.append(
                "CTB: wrong create-button name — the button is EXACTLY 'Create New Component'. "
                "Replace: page.get_by_role('button', name='Create New Component').click()"
            )
        if re.search(r"get_by_role\('button',\s*name=['\"]Number['\"]", code):
            issues.append(
                "CTB: number field type button is 'Numbers' (plural), not 'Number'. "
                "Replace with: page.get_by_role('button', name='Numbers').click()"
            )
        if re.search(
            r"get_by_role\('button',\s*name=['\"](?:Date(?! And Time)|DateTime|Date/Time)['\"]", code
        ):
            issues.append(
                "CTB: date field type button is 'Date And Time' (not 'Date', not 'DateTime'). "
                "Replace with: page.get_by_role('button', name='Date And Time').click()"
            )
        # CTB: wrong field type tile click — button name matches 'Text' AND 'Rich Text' (strict mode)
        if re.search(r"get_by_role\('button',\s*name=['\"]Text['\"]\)\.click\(\)", code):
            issues.append(
                "CTB: get_by_role('button', name='Text').click() is ambiguous — it matches both the "
                "'Text' and 'Rich Text' tiles (2 elements → strict mode violation). "
                "Replace with: page.get_by_role('dialog').get_by_role('heading', name='Text', exact=True).click()"
            )
        # CTB: wrong Display Name label in field forms — asterisk not part of accessible name
        display_name_star_count = len(re.findall(
            r"safe_sequential_fill\s*\([^,]+,\s*['\"]Display Name \*['\"]",
            code
        ))
        if display_name_star_count > 1:
            issues.append(
                "CTB: 'Display Name *' (with asterisk) is the label in the Step 1 'Create New Component' "
                "dialog ONLY. The field form (Step 2) textbox accessible name is 'Display Name' without "
                "asterisk — safe_sequential_fill(page, 'Display Name *', ...) finds 0 matches there. "
                "Replace every field-form fill with: safe_sequential_fill(page, 'Display Name', field_name, delay=50)"
            )
        save_clicks = len(re.findall(r"get_by_role\('button',\s*name=['\"]Save['\"]\)", code))
        if bool(re.search(r"Add Another Field", code)) and save_clicks < 2:
            issues.append(
                "CTB: missing main-page Save after field builder. Found only "
                f"{save_clicks} Save click(s) but need at least 2: one scoped to the dialog (closes the "
                "last field), and one scoped to the page header to persist the component. "
                "Last field: page.get_by_role('dialog').get_by_role('button', name='Save').click() "
                "Main page: page.locator('#page-header').get_by_role('button', name='Save').click() "
                "(Scoping to #page-header is REQUIRED — an unscoped page.get_by_role('button', name='Save') "
                "fails in strict mode when a Date And Time field leaves its date-picker popup open with its own Save button.)"
            )
        # NOTE: the unscoped main-page Save (page.get_by_role('button', name='Save')) is NOT gated here.
        # gpt-4o reliably writes it unscoped and cannot self-correct from a rejection message, so it is
        # fixed deterministically in spec_sanitizer (scoped to #page-header) instead of blocking the
        # generator loop. Gating it here caused an unrecoverable reject-loop on every CTB create spec.
        # CTB list: no 'Created By' filter textbox exists — only 'Search' (name filter)
        if re.search(r"get_by_role\(\s*['\"]textbox['\"]\s*,\s*name\s*=\s*['\"]Created By['\"]", code):
            issues.append(
                "CTB: get_by_role('textbox', name='Created By') — no 'Created By' filter exists on the "
                "custom-component list page. The ONLY filter input is textbox 'Search' (filters by component name). "
                "The 'Updated By' column header has no corresponding filter textbox. "
                "Remove the 'Created By' filter step entirely."
            )
        # CTB list: no options/kebab menu — Delete is a direct row button
        if re.search(
            r"(?:options.menu|kebab|\.\.\.|\bmore.options\b|get_by_role\(['\"]button['\"],\s*name=['\"](?:\.\.\.|More|Options)['\"])",
            code, re.IGNORECASE
        ):
            issues.append(
                "CTB: no options/kebab menu exists on the custom-component list. "
                "Delete is a DIRECT button on each row: row.get_by_role('button', name='Delete').click(). "
                "Remove any step that opens an options/kebab menu."
            )

    if len(issues) == 0:
        return None

    return (
        'SPEC REJECTED -- semantic issues found:\n' +
        '\n'.join(f'{n + 1}. {issue}' for n, issue in enumerate(issues)) +
        '\n\nFix all issues above and call generator_write_test again with the corrected spec.'
    )


def validate_spec_data_uniqueness(code: str) -> Optional[str]:
    if re.search(r'time\.time\(\)', code):
        return None

    # Edit- and delete-of-existing-item flows target a pre-existing named item whose exact name the
    # user's prompt supplies (e.g. "rename the category to 'I am not cat'", "delete the tag 'Sports'").
    # Those literals MUST stay literal — appending a timestamp makes the locator unmatchable — so no
    # timestamp is required. Signal: no navigation to a create/new URL, but the spec acts on an
    # existing row via an Edit or Delete control (either get_by_role('button', name=...) or
    # get_by_title(...), since list pages vary in which form the control takes).
    is_edit_or_delete_existing = (
        not re.search(r"page\.goto\(['\"][^'\"]*(?:create|/new|/add)[^'\"]*['\"]\)", code) and
        bool(
            re.search(r"get_by_role\('button',\s*name=['\"](?:Edit|Delete)['\"]\)", code) or
            re.search(r"get_by_title\(['\"](?:Edit|Delete)['\"]", code)
        )
    )
    if is_edit_or_delete_existing:
        placeholder = re.search(
            r"\w*(?:name|title)\w*\s*=\s*['\"]((?:Existing|Sample|Placeholder|Example|Test)\s[^'\"]*|[^'\"]*Replace\s+with[^'\"]*)['\"]",
            code, flags=re.IGNORECASE
        )
        if placeholder:
            return (
                f'SPEC REJECTED -- placeholder value used for a pre-existing item: {placeholder.group(0).strip()}\n'
                'This locator will never match a real row. The plan must name a real, observed item — '
                'do not fabricate a name. If the plan itself lacks a real item name, that is a planner defect: '
                're-request a plan that reads the actual list via browser_snapshot before writing the step.'
            )
        return None

    # Scan a copy with Playwright locator calls stripped out, so that name=/exact= keyword arguments
    # (e.g. get_by_role('button', name='Save Category')) are never mistaken for hardcoded test data.
    scan = re.sub(r"get_by_(?:role|title|text|label|placeholder)\([^)]*\)", '', code)

    m = re.search(
        r"\w*(?:name|title|tag|category|article|slug)\w*\s*=\s*['\"][^'\"]{4,}['\"]",
        scan, flags=re.IGNORECASE
    )
    if m:
        return (
            f'SPEC REJECTED -- hardcoded test data detected: {m.group(0).strip()}\n'
            'Every test data value (names, titles, slugs) MUST use time.time() for uniqueness.\n'
            'Add: ts = int(time.time() * 1000)\n'
            "Then replace the hardcoded string with an f-string, e.g.: "
            "category_name = f'QA Category {ts}'"
        )

    # Catch hardcoded literals passed directly to safe_fill / safe_sequential_fill when the spec
    # is a create flow (navigates to a /new or /create URL). Edit/delete flows that target a
    # pre-existing named item are exempt (they have no /new or /create navigation).
    is_create_url_flow = bool(
        re.search(r"page\.goto\(['\"][^'\"]*(?:/new|/create)[^'\"]*['\"]\)", code)
    )
    if is_create_url_flow:
        m2 = re.search(
            r"safe_(?:sequential_)?fill\s*\(\s*page\s*,\s*[^,]+,\s*'([^']{4,})'",
            code
        )
        if m2:
            return (
                f"SPEC REJECTED -- hardcoded test data passed directly to safe_fill on a create flow: '{m2.group(1)}'\n"
                'Every value created by the test MUST include a millisecond timestamp for uniqueness.\n'
                'Add: ts = int(time.time() * 1000)\n'
                "Then replace the literal with an f-string: f'QA Name {ts}'"
            )

    return None


def _extract_plan_fill_targets(plan_steps: List[str]) -> List[str]:
    """Field labels the plan explicitly prescribes filling or selecting, all of which gate the
    Publish/Save/Update button. Reuses extract_fill_labels for safe_fill/safe_sequential_fill +
    textbox targets (it already handles every fill syntax and filters placeholders), and adds
    comboboxes (Primary Category, etc.) — which extract_fill_labels does not cover but which
    equally block submit when omitted."""
    text = '\n'.join(plan_steps)
    labels: List[str] = list(extract_fill_labels(text))
    for m in re.finditer(
        r"get_by_role\(\s*['\"]combobox['\"]\s*,\s*name\s*=\s*(['\"])([^'\"]+)\1", text
    ):
        labels.append(m.group(2))
    return list(dict.fromkeys(labels))


def validate_spec_matches_plan(code: str, plan_steps: List[str]) -> Optional[str]:
    """Reject a spec that silently drops a field the plan told it to fill/select.

    validate_spec_semantics can only enforce required fields for pages with hand-verified
    PAGE_FACTS; pages with empty facts (e.g. /posts/live-blog/create) fall through it entirely.
    This check is facts-independent: it trusts the PLAN as the source of truth. Whatever field the
    plan names, the spec must reference — on ANY page, verified or not. This closes the hole where
    the generator wrote only 'Title *' and a "assuming there are other required fields" comment,
    dropping the Permalink and Primary Category the plan prescribed, so Publish stayed disabled.
    """
    if not plan_steps:
        return None
    plan_targets = _extract_plan_fill_targets(plan_steps)
    if not plan_targets:
        return None
    # Only fields with distinctive tokens can be reliably checked; skip label-less/ambiguous ones
    # to avoid false-positive rejection loops.
    missing = [
        lbl for lbl in plan_targets
        if _field_distinctive_tokens(lbl) and not _is_field_referenced(lbl, code)
    ]
    if not missing:
        return None
    quoted = ', '.join(f'"{l}"' for l in missing)
    return (
        f'The plan prescribes filling/selecting these field(s) that the generated spec never '
        f'implements: {quoted}. The generator dropped required plan steps (often replaced with a '
        f'placeholder comment). EVERY field the plan names must be implemented with real code — a '
        f'single omitted required field leaves the Publish/Save/Update button permanently disabled '
        f'and the test times out. For each missing field: use '
        f"safe_sequential_fill(page, '<label>', <value>, delay=50) for text/permalink fields, or for a "
        f"combobox click get_by_role('combobox', name='<label>') then "
        f"page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first.click()."
    )
