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

    return out
