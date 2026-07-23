import glob
import os
import random
import re

from playwright.sync_api import Locator, expect


def click_nav(page, name, timeout=15000):
    """Click a sidebar / Configuration-hub navigation link by a SUBSTRING of its accessible name.

    Nav-link names often carry trailing description text (e.g. the Site Timezone link's real name is
    'Site Timezone Set timezone') and vary, so an EXACT match is fragile and intermittently matches
    nothing — a substring match + .first is robust. This is an HONEST click (scroll into view +
    normal click, NO force): if the link genuinely cannot be clicked, it fails loudly with
    Playwright's own reason, which is the correct signal that the user journey is broken — we never
    force or fall back to a goto to paper over a real navigation bug."""
    link = page.get_by_role('link', name=name).first
    link.scroll_into_view_if_needed(timeout=timeout)
    link.click(timeout=timeout)


def open_ant_select(page, name, exact=False, timeout=15000):
    """Open an Ant Design <Select> (role=combobox) reliably — including a PRE-FILLED one.

    A pre-filled select renders its chosen value in a `.ant-select-selection-item` span that
    OVERLAYS the combobox input, so a normal .click() is intercepted ('intercepts pointer events')
    and times out. A forced click dispatches anyway and bubbles to the selector, opening the
    dropdown. Harmless on an empty select. Returns the combobox Locator; waits for the panel.
    (All behaviours here were confirmed live against the Site Timezone select.)
    """
    cb = page.get_by_role('combobox', name=name, exact=exact)
    cb.wait_for(state='visible', timeout=timeout)
    cb.click(force=True)
    page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').last.wait_for(
        state='visible', timeout=timeout
    )
    return cb


def select_ant_option(page, name, option_text, exact=False, timeout=15000):
    """Change a (possibly pre-filled) Ant Select to `option_text`. Does NOT type-to-filter: on many
    of these selects the search input is readonly, so .fill() raises 'element is not editable'.
    Instead match the option by its visible text; the list is VIRTUALIZED (only ~11 render at once),
    so if the target is not in the DOM yet, scroll the rc-virtual-list holder until it renders, then
    click. Uses the sanctioned .ant-select-item-option pattern — no hardcoded get_by_title."""
    open_ant_select(page, name, exact=exact, timeout=timeout)
    panel = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').last
    option = panel.locator('.ant-select-item-option').filter(has_text=option_text)
    holder = panel.locator('.rc-virtual-list-holder')
    for _ in range(30):
        if option.count() > 0:
            break
        if holder.count() == 0:
            break
        holder.first.evaluate('(el) => el.scrollBy(0, el.clientHeight)')
        page.wait_for_timeout(120)
    option.first.wait_for(state='visible', timeout=timeout)
    option.first.click()


def save_setting(page, button_name='Save', timeout=15000):
    """Click a settings Save button and WAIT for its persist request to finish before returning.

    Critical for /configurations settings: the Save fires an async PATCH (e.g. PATCH /api/publisher/).
    If the test reloads to verify BEFORE that request completes, the reload CANCELS the in-flight
    PATCH and the change never commits (confirmed live — this was the real cause of the flaky
    'value reverted after reload' failure). Waiting for the response makes the save deterministic."""
    try:
        with page.expect_response(
            lambda r: r.request.method in ('PATCH', 'PUT', 'POST')
            and '/api/' in r.url and 'clarity' not in r.url and 'analytics' not in r.url,
            timeout=timeout,
        ):
            page.get_by_role('button', name=button_name).click()
    except Exception:
        # Response not observed (e.g. a client-only save) — the click already fired above; just
        # give any in-flight request a moment to settle before the caller reloads.
        page.wait_for_timeout(2000)


def current_ant_select_value(page, name, exact=False, timeout=15000):
    """Return the value an Ant Select currently shows (its `.ant-select-selection-item` title), for
    capturing a shared setting's original value before a change so it can be restored. '' if unset."""
    cb = page.get_by_role('combobox', name=name, exact=exact)
    cb.wait_for(state='visible', timeout=timeout)
    item = cb.locator(
        'xpath=ancestor::div[contains(@class,"ant-select-selector")][1]'
    ).locator('.ant-select-selection-item')
    if item.count() == 0:
        return ''
    return item.first.get_attribute('title') or ''


def expect_ant_select_value(page, name, value, exact=False, reload=False, tries=6, timeout=15000):
    """Assert an Ant Select shows `value`. CRITICAL: the role=combobox is a readonly search input
    whose `value` attribute stays '' — the shown value lives in a sibling `.ant-select-selection-item`
    span (its `title`), so expect(get_by_role('combobox', ...)).to_have_value(value) NEVER passes.
    Assert that span, scoped to THIS select's container.

    reload=True — for verifying a value that was just SAVED. The Save (PATCH) commits reliably, but
    an immediate page.reload() can GET a STALE cached value (read-after-write staleness — confirmed
    live: the change had committed yet the first reload still showed the old value). So reload and
    re-check up to `tries` times until the committed value appears, instead of a single flaky check.
    """
    def _read():
        cb = page.get_by_role('combobox', name=name, exact=exact)
        cb.wait_for(state='visible', timeout=timeout)
        item = cb.locator(
            'xpath=ancestor::div[contains(@class,"ant-select-selector")][1]'
        ).locator('.ant-select-selection-item')
        return item, (item.first.get_attribute('title') if item.count() else None)

    if reload:
        for _ in range(tries):
            page.reload()
            _, actual = _read()
            if actual == value:
                return
            page.wait_for_timeout(1500)
    item, _ = _read()
    expect(item).to_have_attribute('title', value, timeout=timeout)


def random_desktop_png():
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    pngs = glob.glob(os.path.join(desktop, '*.png')) + glob.glob(os.path.join(desktop, '*.PNG'))
    if not pngs:
        raise FileNotFoundError(f'No .png files found on Desktop ({desktop}) — add one to run media upload tests.')
    return random.choice(pngs)


def get_max_limits(page):
    return page.evaluate("""() =>
        Array.from(document.querySelectorAll('input, textarea')).map((el) => {
            return {
                label:
                    el.labels?.[0]?.innerText?.trim() ||
                    el.placeholder || el.name || el.id ||
                    el.getAttribute('aria-label'),
                type: el.type,
                maxLength: el.maxLength > 0 ? el.maxLength : null,
                required: el.required,
            };
        })
    """)


def trigger_and_read_min_limits(page):
    page.evaluate("""() => {
        document.querySelectorAll('input[type="text"], textarea').forEach((el) => {
            if (!el.readOnly && !el.disabled && el.offsetParent !== null) {
                el.focus();
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                setter?.call(el, 'x');
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.blur();
            }
        });
    }""")
    page.wait_for_timeout(800)
    return page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('[role="alert"]').forEach((alert) => {
            const text = alert.textContent?.trim();
            if (text) {
                let el = alert;
                let label = '';
                while (el && !label) {
                    el = el.parentElement;
                    label = el?.querySelector('label, [class*="label"]')?.textContent?.trim() || '';
                }
                results.push({ label, error: text });
            }
        });
        return results;
    }""")


def safe_fill(page, label, text, exact=False):
    if isinstance(label, Locator):
        locator = label            # caller pre-narrowed the field (e.g. .first on an ambiguous name)
    elif isinstance(label, str):
        locator = page.get_by_role('textbox', name=label, exact=exact)
    else:
        locator = page.get_by_role('textbox', name=label)
    max_len = locator.evaluate('(el) => el.maxLength')
    locator.fill(text[:max_len] if max_len > 0 else text)


def safe_sequential_fill(page, label, text, delay=0, exact=False):
    if isinstance(label, Locator):
        locator = label            # caller pre-narrowed the field (e.g. .first on an ambiguous name)
    elif isinstance(label, str):
        locator = page.get_by_role('textbox', name=label, exact=exact)
    else:
        locator = page.get_by_role('textbox', name=label)
    locator.wait_for(state='visible')
    locator.click()
    # Clear any existing value with real key events (React-tracked) so this is a true REPLACE, not an
    # append. fill('') is avoided on purpose — React-controlled inputs ignore it. On empty create-form
    # fields the select-all+delete is a harmless no-op; on pre-filled edit/rename fields it erases first.
    locator.press('ControlOrMeta+a')
    locator.press('Delete')
    max_len = locator.evaluate('(el) => el.maxLength')
    value = text[:max_len] if max_len > 0 else text
    locator.press_sequentially(value, delay=delay)

    # Permalink commit-nudge. The "English Title ( Permalink )" field runs a DEBOUNCED, ASYNC
    # uniqueness check that gates the Publish/Save button. After a fast press_sequentially the check
    # intermittently settles in a "not-yet-valid" state and the button stays disabled FOREVER — no
    # amount of waiting recovers it (verified live on /posts/live-blog/create: Publish stayed disabled
    # through 4s+ of later steps). A single isolated keystroke re-fires the check and it resolves,
    # enabling the button within ~500ms. So we append one throwaway char and delete it: the field
    # value is unchanged, but the trailing edit forces a clean final validation. Harmless on content
    # types where the check already passes on its own.
    if isinstance(label, str) and 'permalink' in label.lower():
        page.wait_for_timeout(400)  # let the initial (Title-driven) debounce settle first
        locator.press('End')
        if max_len <= 0 or len(value) < max_len:
            locator.press('a')          # append throwaway char (skip if already at maxLength)
        else:
            locator.press('Backspace')  # at maxLength: drop last char instead, then restore it below
            locator.press_sequentially(value[-1], delay=delay)
            page.wait_for_timeout(400)
            locator.press('End')
        locator.press('Backspace')      # end on a Backspace — restores the intended value
        page.wait_for_timeout(400)      # give the re-fired uniqueness check time to enable Publish
