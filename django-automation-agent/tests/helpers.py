import re


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
    if isinstance(label, str):
        locator = page.get_by_role('textbox', name=label, exact=exact)
    else:
        locator = page.get_by_role('textbox', name=label)
    max_len = locator.evaluate('(el) => el.maxLength')
    locator.fill(text[:max_len] if max_len > 0 else text)


def safe_sequential_fill(page, label, text, delay=0, exact=False):
    if isinstance(label, str):
        locator = page.get_by_role('textbox', name=label, exact=exact)
    else:
        locator = page.get_by_role('textbox', name=label)
    locator.wait_for(state='visible')
    locator.click()
    max_len = locator.evaluate('(el) => el.maxLength')
    value = text[:max_len] if max_len > 0 else text
    locator.press_sequentially(value, delay=delay)
