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

    # Dashboard list URLs append a query string after the path ('/posts/published?page_type=...'), so
    # a trailing slash in re.compile(r'/posts/published/') never matches. Planner slip: dashboard_facts
    # uses JS-regex delimiters and the closing '/' gets copied as a path slash. Strip a trailing '/'
    # (or '\/') from every to_have_url regex to match as a query-tolerant substring.
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

    # The dashboard top bar carries a "Quick Create" button, and name= is a SUBSTRING match, so
    # get_by_role('button', name='Create') resolves to 2 elements -- the page's own Create button plus
    # Quick Create -- and dies on a strict-mode violation before any work happens (confirmed live
    # 2026-07-30 on Configuration -> Reader: 'resolved to 2 elements: <button aria-label="Create"
    # class="... create-redirect popover"> / <button title="Quick Create">').
    # No page's real create button is named exactly "Create" AND meant to be substring-matched, so add
    # exact=True unconditionally. The pattern requires the closing ')' right after the name string, so
    # a call that already passes exact= (or any other kwarg) does not match and is left untouched.
    out = re.sub(
        r"get_by_role\(\s*(['\"])button\1\s*,\s*name\s*=\s*(['\"])Create\2\s*\)",
        lambda m: f"get_by_role({m.group(1)}button{m.group(1)}, "
                  f"name={m.group(2)}Create{m.group(2)}, exact=True)",
        out,
    )

    # Fixed/sticky-column lists (e.g. LiveBlog) render each action cell twice, so
    # .locator('.published-action-dropdown') resolves to two buttons and fails strict mode.
    # Append .first. Skipped when already qualified with .first/.last/.nth.
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

    # Navigation link clicks -> click_nav (deterministic robustness). gpt-4o intermittently writes a
    # sidebar/hub nav-link click with exact=True (e.g. get_by_role('link', name='Site Timezone', exact=True)),
    # which times out because those link names carry trailing description text ('Site Timezone Set timezone')
    # and vary. Rewrite any TOP-LEVEL page.get_by_role('link', name=..).click() to click_nav(page, ..),
    # which matches by substring + .first and clicks honestly (fails loudly if genuinely unclickable).
    # Only page.get_by_role(...) (not row-scoped ...locator('tr')...get_by_role) is rewritten.
    out = re.sub(
        r"page\.get_by_role\(\s*['\"]link['\"]\s*,\s*name\s*=\s*(['\"])([^'\"]+)\1[^)]*\)\.click\(\)",
        lambda m: f"click_nav(page, {m.group(1)}{m.group(2)}{m.group(1)})",
        out,
    )
    if 'click_nav(' in out:
        _imp = re.search(r'^from helpers import (.+)$', out, flags=re.MULTILINE)
        if _imp and 'click_nav' not in _imp.group(1):
            out = out[:_imp.start()] + f"from helpers import {_imp.group(1).strip()}, click_nav" + out[_imp.end():]
        elif not _imp:
            line = 'from helpers import click_nav'
            out = (re.sub(r"(from playwright[^\n]+\n)", rf"\1{line}\n", out, count=1)
                   if 'from playwright' in out else f'{line}\n{out}')

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

    # Fixed/sticky-column lists render each <tr> twice; narrow single-row tr-filter uses to .first.
    out = _narrow_single_row_tr_filters(out)

    # Title->Permalink: debounced auto-slug can corrupt Permalink mid-keystroke, leaving Publish permanently
    # disabled. Shared across all content types -- insert the settle wait whenever both fills appear in order.
    out = _insert_permalink_debounce_wait(out)

    # CTB (Content Type Builder) Save scoping. The create flow always ends with two Saves in order:
    # (1) a DIALOG-scoped Save that closes the last field's "Add a field" modal, then (2) a page-HEADER
    # Save that persists the component. gpt-4o reliably writes BOTH unscoped as
    # page.get_by_role('button', name='Save') and cannot self-correct, so an unscoped header Save clicked
    # while the field modal is still open is intercepted by the modal and times out. Fix deterministically:
    # scope the LAST unscoped Save to the page header and every earlier unscoped Save to the dialog.
    # (An already dialog-scoped Save — page.get_by_role('dialog').get_by_role('button', ...) — does not
    # match this pattern and is left untouched.)
    if re.search(r'content-type-builder', out):
        _save_pat = re.compile(
            r"page\.get_by_role\(\s*['\"]button['\"]\s*,\s*name\s*=\s*['\"]Save['\"]\s*\)"
        )
        _hits = list(_save_pat.finditer(out))
        if _hits:
            _last_start = _hits[-1].start()

            def _scope_save(m: re.Match) -> str:
                if m.start() == _last_start:
                    return "page.locator('#page-header').get_by_role('button', name='Save')"
                return "page.get_by_role('dialog').get_by_role('button', name='Save')"

            out = _save_pat.sub(_scope_save, out)

    # List-membership visibility checks on a SHARED cell value throw strict mode. When verifying a
    # newly created row, the generator reliably asserts the UNIQUE (ts-stamped) value AND — despite the
    # heuristic telling it not to — an extra assertion on a shared value (e.g. a redirect destination
    # '/home' that many rows point to), which resolves to N elements. Narrow every get_by_text() that is
    # the direct target of a to_be_visible() assertion to .first: a no-op when the value is unique (the
    # ts path matches one element), and it removes the strict-mode violation when it is shared. Skipped
    # when already qualified (.first/.last/.nth) — the trailing ')' after get_by_text(...) won't match then.
    out = re.sub(
        r"expect\(\s*(page\.get_by_text\([^)]*\))\s*\)\s*\.\s*to_be_visible",
        lambda m: f'expect({m.group(1)}.first).to_be_visible',
        out,
    )

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

    # A BARE page.locator('tr') (no .filter/.first/.last/.nth) matches EVERY row, so using it directly
    # in a single-element op or assertion — e.g. expect(page.locator('tr')).to_be_visible() to check a
    # list "loaded" — is a strict-mode "multiple elements" failure (observed: Verify Categories List
    # Visibility, 2026-07-28, where the generator asserted a raw row locator for table visibility).
    # Narrow INLINE uses to .first: DOM order puts the VISIBLE header <tr> first, so this dodges the
    # aria-hidden ant-table-measure-row that .nth(1) would hit. The negative lookahead skips the
    # multiplicity/already-narrowed idioms; a bare tr assigned to a variable is left alone (usually an
    # intentional multi-row set), mirroring the tr-filter assignment rule's caution above.
    tr_bare = r"page\.locator\(\s*['\"]tr['\"]\s*\)(?!\s*\.(?:filter|first|last|nth|count|all)\b)"
    out = re.sub(
        r"(?P<loc>" + tr_bare + r")(?=\.(?:" + _SINGLE_ELEMENT_OPS + r")\b)",
        lambda m: m.group('loc') + '.first',
        out,
    )
    out = re.sub(
        r"expect\(\s*(?P<loc>" + tr_bare + r")\s*\)\.(?:" + _SINGLE_ELEMENT_ASSERTS + r")",
        _inline_expect,
        out,
    )
    return out


def _insert_permalink_debounce_wait(out: str) -> str:
    # Match Title fill by the substring "Title *" anywhere in the call's arguments -- covers both the
    # plain-string form and the disambiguated Locator form (Web Story inserts a second 'Title *' textbox).
    # 'English Title ( Permalink ) *' never contains the literal "Title *", so it can't collide;
    # the Permalink fill is matched by its 'Permalink' token instead.
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
