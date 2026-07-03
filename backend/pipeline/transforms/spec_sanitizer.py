import re


def sanitize_spec(code: str, scenario_name: str) -> str:
    out = code

    def _to_have_url_repl(m: re.Match) -> str:
        url_path = m.group(2)
        escaped = re.escape(url_path)
        return f".to_have_url(re.compile(r'{escaped}'))"

    out = re.sub(
        r"\.to_have_url\(\s*(['\"])([^'\"]+)\1\s*\)",
        _to_have_url_repl,
        out,
    )

    # A to_have_url() path pattern must NOT end in a literal trailing slash. Dashboard list URLs append
    # a query string directly after the path segment ('/posts/published?page_type=...'), so a pattern
    # like re.compile(r'/posts/published/') can NEVER match — re.search wants a '/' exactly where the URL
    # has '?'. This is a recurring planner slip: dashboard_facts writes URL patterns in JS-regex-delimiter
    # style ('URL matches /\/posts\/published/') and the closing '/' delimiter gets copied as a literal
    # path slash. Strip a single trailing '/' (or '\/') from every to_have_url regex so it matches the
    # path as a query-/trailing-slash-tolerant substring, exactly like the passing specs.
    def _strip_trailing_slash(m: re.Match) -> str:
        return m.group(1) + re.sub(r'\\?/\Z', '', m.group(2)) + m.group(3)

    for quote in ("'", '"'):
        out = re.sub(
            r"(\.to_have_url\(\s*re\.compile\(\s*r?" + quote + r")"
            r"((?:[^" + quote + r"\\]|\\.)*)"
            r"(" + quote + r"\s*\))",
            _strip_trailing_slash,
            out,
        )

    # Strip absolute dashboard base URL from goto() -> relative path.
    def _strip_base_url(m: re.Match) -> str:
        q = m.group(1)
        rel_path = m.group(2)
        return f'page.goto({q}{rel_path}{q}'

    out = re.sub(
        r"page\.goto\(\s*(['\"])https?://[^'\"]+/v2(/[^'\"]*)\1",
        _strip_base_url,
        out,
    )

    # Ant Design portal options — .last avoids strict-mode violations
    def _option_to_title(m: re.Match) -> str:
        q = m.group(1)
        name = m.group(2)
        return f"get_by_title({q}{name}{q}, exact=True).last"

    out = re.sub(
        r"get_by_role\(\s*['\"]option['\"]\s*,\s*name=(['\"])([^'\"]+)\1\s*\)",
        _option_to_title,
        out,
    )

    def _title_click_last(m: re.Match) -> str:
        q = m.group(1)
        name = m.group(2)
        return f".get_by_title({q}{name}{q}, exact=True).last.click()"

    out = re.sub(
        r"\.get_by_title\((['\"])([^'\"]+)\1\)\.click\(\)",
        _title_click_last,
        out,
    )

    # Row action-kebab (.published-action-dropdown) -> append .first to avoid strict-mode.
    # On lists whose actions column is fixed/sticky (e.g. the LiveBlog published list), Ant Design
    # renders the row's action cell twice -- once in the main table and once in the fixed-column
    # overlay -- so row.locator('.published-action-dropdown') resolves to TWO buttons and .click()
    # fails strict mode. Narrow to .first. Skipped when already qualified with .first/.last/.nth.
    out = re.sub(
        r"(\.locator\(\s*(['\"])\.published-action-dropdown\2\s*\))(?!\s*\.(?:first|last|nth))(\s*\.click\(\))",
        r"\1.first\3",
        out,
    )

    # get_by_label doesn't work -- labels are <div>, not <label>.
    def _label_to_textbox(m: re.Match) -> str:
        q = m.group(1)
        label = m.group(2)
        return f"get_by_role('textbox', name={q}{label}{q})"

    out = re.sub(
        r"get_by_label\(\s*(['\"])([^'\"]+)\1\s*\)",
        _label_to_textbox,
        out,
    )

    escaped_name = scenario_name.replace("'", "\\'")
    out = re.sub(
        r"def\s+test_\[Scenario\]",
        f"def test_{re.sub(r'[^a-z0-9]+', '_', escaped_name.lower()).strip('_')}",
        out,
    )

    # Server round-trips need a timeout.
    out = out.replace('.to_be_visible()', '.to_be_visible(timeout=15000)')
    out = out.replace('.to_be_enabled()', '.to_be_enabled(timeout=15000)')
    out = out.replace('.to_be_disabled()', '.to_be_disabled(timeout=15000)')

    if not re.search(r'ts\s*=\s*int\(time\.time\(\)', out):
        out = re.sub(
            r'(def\s+test_\w+\(page\):\s*\n)',
            r'\1    ts = int(time.time() * 1000)\n',
            out,
        )

    if 'time.time()' in out and 'import time' not in out:
        out = f'import time\n{out}'

    if 're.compile' in out and 'import re' not in out:
        out = f'import re\n{out}'

    if re.search(r'(safe_fill|safe_sequential_fill)', out) and 'from helpers import' not in out:
        helpers_needed = []
        if 'safe_fill' in out:
            helpers_needed.append('safe_fill')
        if 'safe_sequential_fill' in out:
            helpers_needed.append('safe_sequential_fill')
        import_line = f"from helpers import {', '.join(helpers_needed)}"
        if 'from playwright' in out:
            out = re.sub(
                r"(from playwright[^\n]+\n)",
                rf"\1{import_line}\n",
                out,
                count=1,
            )
        else:
            out = f'{import_line}\n{out}'

    # Raw multi-line press_sequentially pattern -> safe_sequential_fill
    def _sequential_to_helper(m: re.Match) -> str:
        label = m.group(3)
        value = m.group(4)
        delay_match = re.search(r'delay=(\d+)', m.group(5) if m.lastindex >= 5 else '')
        delay_arg = f', delay={delay_match.group(1)}' if delay_match else ''
        return f"safe_sequential_fill(page, '{label}', {value}{delay_arg})"

    out = re.sub(
        r"(\w+)\s*=\s*page\.get_by_role\('textbox',\s*name=(['\"])([^'\"]+)\2\)\s*\n\s*\1\.wait_for\(state='visible'\)\s*\n\s*\1\.click\(\)\s*\n\s*\1\.press_sequentially\(([^,)]+)(?:,\s*([^)]*))?\)",
        _sequential_to_helper,
        out,
    )

    def _fill_to_safe_fill(m: re.Match) -> str:
        label = m.group(2)
        value = m.group(3)
        return f"safe_fill(page, '{label}', {value})"

    out = re.sub(
        r"page\.get_by_role\('textbox',\s*name=(['\"])([^'\"]+)\1\)\.fill\(([^)]+)\)",
        _fill_to_safe_fill,
        out,
    )

    # Article and Custom Content forms both require 'English Title ( Permalink ) *'
    if (
        (re.search(r"goto\(['\"]\/posts\/article\/create['\"]\)", out) or
         re.search(r"goto\(['\"]\/posts\/custom-page\/create['\"]\)", out)) and
        re.search(r'Save as Draft', out) and
        not re.search(r'English Title', out)
    ):
        out = re.sub(
            r"(safe_sequential_fill\(page,\s*['\"]Title \*['\"][^\n]+\n)",
            r"\1    safe_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}')\n",
            out,
        )

    # Fixed/sticky-column lists (e.g. the LiveBlog published list) render each logical <tr> TWICE
    # (main table + fixed-column overlay, same data-row-key), so page.locator('tr').filter(has_text=X)
    # matches 2 elements and any single-element op on it (.wait_for/.get_by_*/.click, or an
    # expect(...).to_be_visible) throws strict mode. Narrow single-row uses to .first -- but NEVER the
    # multiplicity idioms (.count()/.nth()/.all()/to_have_count) that delete/bulk flows rely on.
    out = _narrow_single_row_tr_filters(out)

    # Whenever a Title fill is immediately followed by a Permalink fill, the Title field's debounced
    # auto-slug generation can fire mid-keystroke on Permalink and corrupt the value, leaving Publish/Save
    # permanently disabled with no visible error. This is a property of the Title->Permalink pair, NOT of any
    # one page (gallery, live-blog, video, web-story all share it), so key the rule on the fields, not the URL:
    # if both fills exist in order with no wait between them, insert the debounce settle wait.
    out = _insert_permalink_debounce_wait(out)

    return out


# Operations that act on (or drill into) a SINGLE element. When any of these is applied to a table-row
# locator that can match multiple <tr> (fixed/sticky-column lists render each row twice), strict mode
# throws. Narrowing the row to .first is always the intended single-row behavior. Chainers like
# get_by_*/locator are included: narrowing the row first, then drilling in, targets the first row's child.
_SINGLE_ELEMENT_OPS = (
    'wait_for|click|dblclick|hover|tap|focus|blur|fill|clear|type|press|press_sequentially|'
    'check|uncheck|set_checked|select_option|select_text|set_input_files|scroll_into_view_if_needed|'
    'drag_to|screenshot|bounding_box|inner_text|inner_html|text_content|get_attribute|input_value|'
    'is_visible|is_hidden|is_enabled|is_disabled|is_checked|is_editable|'
    'get_by_role|get_by_title|get_by_text|get_by_label|get_by_placeholder|get_by_test_id|get_by_alt_text|'
    'locator'
    # NOTE: filter/first/last/nth are intentionally excluded — .filter refines the multi-row set (must
    # not narrow between two filters), and .first/.last/.nth mean the row is already narrowed.
)
# Single-element expect() assertions — every matcher EXCEPT to_have_count (which is only meaningful on
# the full match set and must never be narrowed).
_SINGLE_ELEMENT_ASSERTS = (
    'to_be_visible|to_be_hidden|to_be_enabled|to_be_disabled|to_be_checked|to_be_editable|'
    'to_be_focused|to_be_empty|to_be_attached|to_be_in_viewport|'
    'to_have_text|to_contain_text|to_have_value|to_have_values|to_have_attribute|to_have_class|'
    'to_have_css|to_have_id|to_have_js_property|to_have_role|to_have_accessible_name'
)


def _narrow_single_row_tr_filters(out: str) -> str:
    """Permanent, class-level fix for strict-mode violations on table-row locators.

    Fixed/sticky-column published lists render each logical <tr> TWICE (same data-row-key), so
    page.locator('tr').filter(...) resolves to 2 elements and ANY single-element op on it throws
    strict mode. Rather than patch one call site at a time, narrow EVERY single-row use of a
    tr-filter to .first, while never touching the multiplicity idioms (.count()/.nth()/.all()/
    to_have_count) that delete and bulk flows depend on.
    """
    # page.locator('tr').filter(...) — filter arg may contain one level of nested parens
    # (e.g. filter(has=page.get_by_role('button', name='Edit', exact=True))).
    tr_filter = r"page\.locator\(\s*['\"]tr['\"]\s*\)\.filter\((?:[^()]|\([^()]*\))*\)"

    # 1) Inline chained single-element op directly on a tr-filter:
    #    page.locator('tr').filter(...).wait_for(...) / .get_by_title(...).click() / etc.
    #    Insert .first between the filter(...) and the op. The lookahead leaves the op in place, and
    #    a tr-filter already followed by .first/.last/.nth is skipped (those are in the op list, so the
    #    lookahead would match — guard against double-narrowing by excluding them from THIS insertion).
    out = re.sub(
        r"(?P<loc>" + tr_filter + r")(?=\.(?:" + _SINGLE_ELEMENT_OPS + r")\b)",
        lambda m: m.group('loc') + '.first',
        out,
    )

    # 2) Inline single-element expect() assertion: expect(<tr filter>).to_be_visible / to_have_text / ...
    #    Narrow the locator argument. to_have_count is deliberately excluded above.
    def _inline_expect(m: re.Match) -> str:
        loc = m.group('loc')
        return m.group(0).replace(loc, loc + '.first', 1)

    out = re.sub(
        r"expect\(\s*(?P<loc>" + tr_filter + r")\s*\)\.(?:" + _SINGLE_ELEMENT_ASSERTS + r")",
        _inline_expect,
        out,
    )

    # 3) Row-variable assignment: VAR = <tr filter>. Append .first UNLESS VAR is used anywhere with a
    #    multiplicity op (.count()/.nth()/.all() or expect(VAR).to_have_count) -- those need every match.
    #    TR_FILTER stops at the filter(...) close paren, so a line already ending in .first/.nth/.last
    #    won't match `$` and is left untouched (no double .first).
    def _assign(m: re.Match) -> str:
        indent, var, rhs = m.group('indent'), m.group('var'), m.group('rhs')
        if (
            re.search(rf'\b{re.escape(var)}\.(?:count|nth|all)\b', out)
            or re.search(rf'expect\(\s*{re.escape(var)}\s*\)\.to_have_count', out)
        ):
            return m.group(0)
        return f'{indent}{var} = {rhs.rstrip()}.first'

    out = re.sub(
        r"(?P<indent>^[ \t]*)(?P<var>\w+)\s*=\s*(?P<rhs>" + tr_filter + r")[ \t]*$",
        _assign,
        out,
        flags=re.MULTILINE,
    )
    return out


def _insert_permalink_debounce_wait(out: str) -> str:
    # The Title fill may be written two ways: the plain string form
    # safe_sequential_fill(page, 'Title *', ...) OR — on Web Story, where an inserted-image slide adds a
    # second 'Title *' textbox — the disambiguated Locator form
    # safe_sequential_fill(page, page.get_by_role('textbox', name='Title *').first, ...). Both contain the
    # literal "Title *", so match on that substring anywhere in the call's arguments. The Permalink label
    # ('English Title ( Permalink ) *') never contains the literal "Title *" (it reads "Title ( Permalink )"),
    # so this cannot collide with the Permalink fill; that one is matched by its 'Permalink' token.
    title_m = re.search(r"safe_sequential_fill\(\s*page\s*,[^\n]*Title \*[^\n]*\n", out)
    permalink_m = re.search(
        r"safe_sequential_fill\(\s*page\s*,\s*['\"][^'\"]*Permalink[^'\"]*['\"]", out
    )
    if not (title_m and permalink_m and title_m.end() <= permalink_m.start()):
        return out
    between = out[title_m.end():permalink_m.start()]
    if 'wait_for_timeout' in between:
        return out
    # Preserve the Title fill's own indentation for the inserted line.
    indent_m = re.search(r'\n([ \t]*)safe_sequential_fill\(\s*page\s*,[^\n]*Title \*', out[:title_m.end()])
    indent = indent_m.group(1) if indent_m else '    '
    return (
        out[:title_m.end()] +
        f"{indent}page.wait_for_timeout(500)  # let the Title->Permalink auto-slug debounce settle\n" +
        out[title_m.end():]
    )
