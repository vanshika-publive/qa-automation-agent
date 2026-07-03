import glob
import os
import random
import re

from playwright.sync_api import Locator


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
