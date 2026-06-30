import re
from typing import List, Optional, Set

from pipeline.knowledge.dashboard_facts import PAGE_FACTS
from .plan_validator import extract_fill_labels, normalize_field_name


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
            "safe_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}')"
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

    # [^)]* ensures name= is inside the get_by_role() parens, not in a chained method call
    if re.search(r"get_by_role\(['\"]row['\"][^)]*\bname\s*=", code):
        issues.append(
            "get_by_role('row', name=...) detected — Ant Design tr elements have NO accessible name. "
            "This locator always times out on the live dashboard. "
            "Replace with: row = page.locator('tr').filter(has_text=title) then row.wait_for(state='visible', timeout=15000)"
        )

    if re.search(r"get_by_role\(['\"]dialog['\"][^)]*\bname\s*=", code):
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

    navigated_paths = [m.group(1) for m in re.finditer(r"page\.goto\(['\"](\\/[^'\"\\)]+)['\"]\)", code)]
    navigated_facts = [PAGE_FACTS[p] for p in navigated_paths if PAGE_FACTS.get(p) is not None]
    all_navigated_have_facts = (
        len(navigated_paths) > 0 and len(navigated_facts) == len(navigated_paths)
    )
    known_fields_in_spec: Set[str] = set()
    for facts in navigated_facts:
        for f in [*facts.required_for_draft, *facts.required_for_publish, *facts.optional_fields]:
            known_fields_in_spec.add(normalize_field_name(f.field))

    spec_fill_labels = extract_fill_labels(code)
    unknown_fill_labels = (
        [l for l in spec_fill_labels if normalize_field_name(l) not in known_fields_in_spec]
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

    if re.search(r'details\s+(omitted|not\s+specified)|omitted\s+(as|because)', code, flags=re.IGNORECASE):
        issues.append(
            'spec contains a "details omitted" comment, indicating one or more '
            'plan steps were dropped instead of translated to code. EVERY step in the plan must produce code. '
            'For value comboboxes with "first available option", use '
            "page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first.click()."
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
