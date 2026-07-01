# Publive Dashboard — Known Failure Patterns

These rules encode hard-won knowledge about this dashboard. Every rule was derived from real failures in generated tests. You MUST follow each imperative ("Always..." / "Never...") — they override any assumption from general Playwright knowledge.

All examples are Python (pytest-playwright, sync API): snake_case methods, keyword args
(`name=`, `exact=`), `.first` / `.last` as properties (no `()`), `re.compile(r'...')` for regex
names, and f-strings (`f'qa-{ts}'`) for test data. Never use TypeScript syntax.

---

## Navigation & Sidebar

**Never** use `get_by_role('navigation')`. The sidebar is a custom `<div>` — there is no `<nav>` element and no `role="navigation"` anywhere in the page. This locator always times out.

**Always** use `exact=True` on sidebar link locators. Without it, `'Posts'` matches `'Featured Posts'` and triggers a strict-mode violation:
```python
get_by_role('link', name='Posts', exact=True)
```

**Never** use `get_by_label()`. Form labels are custom `<div>` elements, not `<label>` tags. `get_by_label()` always times out on this dashboard. Use `get_by_role('textbox', name='...')` instead.

---

## Ant Design Select Dropdowns

Ant Design renders dropdown portals at the very end of `<body>`, after all other DOM content — including sidebar links that may share the same title text (e.g., `'Article'` appears as both a sidebar link and a Content Type option).

When clicking a dropdown option **by name**, always use `.last` with `exact=True`:
```python
page.get_by_title('Matches', exact=True).last.click()
```

**Never** use `get_by_role('option', name='...')`. Ant Design option elements are hidden native `<option>` nodes — this locator always times out.

**Never** call `get_by_title('X')` without both `exact=True` and `.last`. Sidebar links share titles with common option names, so omitting either causes a strict-mode violation.

### Ant Upload buttons resolve to TWO elements — always use `.last`

Ant Design's `<Upload>` wraps its trigger in a hidden `<span class="ant-upload" role="button">` that exposes the **same accessible name** as the real styled `<button class="ant-btn-primary">` next to it. So `get_by_role('button', name='Upload Media').click()` is a strict-mode violation ("resolved to 2 elements"). Always select the real button with `.last`:
```python
page.get_by_role('button', name='Upload Media').last.click()
```
The `ant-upload` span is always element 1; the real button is element 2 (`.last`). This applies to any "Upload …" button on the dashboard, not just Media Library.

### "Upload Media" opens a NATIVE FILE CHOOSER, not a modal — and the submit "Upload" button doesn't exist until a file is picked

Clicking "Upload Media" on `/media` fires the OS-level file picker directly — there is no intermediate dialog. If a test clicks it without intercepting the chooser, the page never advances and stays on the original media grid, where **"Upload" is a substring of "Upload Media"** — so a later `get_by_role('button', name='Upload').click()` re-resolves to the same two `ant-upload`/"Upload Media" elements from the heuristic above, producing the exact same strict-mode violation one step later. Always intercept the chooser first:
```python
with page.expect_file_chooser() as fc_info:
    page.get_by_role('button', name='Upload Media').last.click()
fc_info.value.set_files(random_desktop_png())
```
Only once `set_files()` runs does the grid get replaced by the "Upload Files" panel (`File name *`, `Alt text *`, `Caption`, `Source`), which is the first point at which `get_by_role('button', name='Upload')` is unique. `random_desktop_png()` (in `helpers.py`) picks a real `.png` at random from the Desktop folder — never pass a fake or empty path, the chooser silently no-ops on one.

### Web Story's required image is a Media-Library modal on a NAMELESS drop-zone — not the "Upload (Portrait/Landscape)" buttons

On `/posts/web-story/create` the required image (marked by the `Web Story *` asterisk) is the single biggest cause of a "Publish stays disabled" timeout, because the page shows **two visually similar upload widgets** and the obvious one is the wrong one:

- **Wrong (optional):** the buttons `plus Upload ( Portrait )` / `plus Upload ( Landscape )` under **"Add Custom Thumbnails (Optional)"**. They have accessible names, so `get_by_role('button', name=...)` finds them easily — but they are optional and filling them does **not** enable Publish.
- **Right (required):** a nameless `<div cursor=pointer>` drop-zone whose only stable handle is its visible text. **Always** target it by text:
```python
page.get_by_text('Upload your Web Story image').click()   # opens the Media Library modal
```

**Never** treat this as a native file chooser — clicking the drop-zone opens an **in-DOM "Media Library" dialog** (verified live 2026-07-01). Pick an existing image and confirm with **Insert Media**:
```python
dialog = page.get_by_role('dialog')
dialog.get_by_role('img').first.click()                    # select an image from the grid
page.get_by_role('button', name='Insert Media').click()    # confirm — modal closes, image attaches
```
The grid reliably holds images from earlier runs. To upload a fresh one instead, the modal's own `Upload Media` button *does* fire the native chooser (intercept it as in the Media Library heuristics above), then click `Insert Media`. The `Upload your Web Story image` placeholder disappearing is the signal the required image is attached and Publish can enable.

### The option list is VIRTUALIZED — never hardcode a category, choose from live options

The Primary Category dropdown (and every long Ant Select) uses `rc-virtual-list`: **only the ~9 options currently scrolled into view exist in the DOM** (verified live — 65+ categories, 9 rendered). So `get_by_title('<name>')` for any option not currently rendered waits the full timeout and the test dies — even when that category genuinely exists. On top of that, the category set is **per-publisher and changes over time** (e.g. Crictoday has `Cricket`, `F1`, `Stadium…` and no `National`; another publisher has `National`, `Sports…`). There is **no safe hardcoded default** — `'National ( national )'` does NOT exist on every publisher.

**Default — when the prompt does NOT name a specific category, pick the first available option dynamically** (works regardless of what the publisher's categories are):
```python
page.get_by_role('combobox', name='Primary Category').click()
option = page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first
option.wait_for(state='visible')
option.click()
```

**When the prompt names a specific category, type to filter** (this renders the matching option into the virtualized DOM so it becomes clickable), then click the first match:
```python
cb = page.get_by_role('combobox', name='Primary Category')
cb.click()
cb.fill('Cricket')   # filters the virtual list; the match now exists in the DOM
option = page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first
option.wait_for(state='visible')
option.click()
```

The title format is always `'Name ( slug )'`. **Never** copy a category title from these examples or from CLAUDE.md verbatim — either pick the first live option or type-to-filter the requested name. If the prompt requests a category and typing it surfaces no option, pick the first available option instead — never invent a category title and never fall back to a hardcoded name.

---

## React-Controlled Text Inputs

Some inputs are React-controlled and do not fire `onChange` when filled with `fill()`. Using `fill()` on these fields succeeds silently but leaves the form's save button permanently disabled — the single most common failure mode in generated tests.

**Always** use `safe_sequential_fill(page, field_label, value, delay=50)` for React-controlled fields. Known React-controlled fields on this dashboard:
- `'Title *'` on article create, custom content create, and similar create forms
- `'Name *'` on tag create and category create

**Never** use raw `fill()` on React-controlled fields.

**Always** use `safe_fill(page, field_label, value)` for all other text inputs — it reads `maxLength` from the DOM at runtime and truncates automatically, preventing over-length failures.

**Never** call `page.get_by_role('textbox', ...).fill(value)` directly — always route through `safe_fill` or `safe_sequential_fill`.

### Disambiguating short field labels (avoid strict-mode violations)

Both helpers accept a `str` or `re.Pattern` label and an `exact` bool keyword. The default is substring + case-insensitive — same as raw `get_by_role`. A short label like `'Name'` will silently match multiple fields on pages that also have `'Name in English ( Slug )'`, `'Name in English (Permalink)'`, etc., producing a strict-mode violation at runtime.

**Always** pass `exact=True` (or a regex) when the field's accessible name is a common substring of another field on the same page. Known collision points:
- `'Name'` on geography create — also matches `'Name in English ( Slug )'`
- Any standalone `'Title'`, `'Summary'`, `'Description'` next to a longer-named sibling

```python
# Geography display name — MUST disambiguate
safe_fill(page, 'Name', f'QA Geography {ts}', exact=True)

# Geography slug — ARIA name has trailing icon text, use regex
safe_fill(page, re.compile(r'Name in English \( Slug \)'), f'qa-geo-{ts}')

# Article title — full ARIA name is 'Title *', no collision, no exact needed
safe_sequential_fill(page, 'Title *', title, delay=50)
```

---

## Ant Design Table Row Locators

**Never** use `get_by_role('row', name=...)` to locate a specific row in an Ant Design table. Ant Design `<tr>` elements do not have an accessible name derived from cell text — this locator always resolves to nothing and times out.

**Always** use `locator('tr').filter(has_text='...')` to find a row by its content:
```python
row = page.locator('tr').filter(has_text=tag_name)
row.wait_for(state='visible', timeout=15000)
row.locator('.published-action-dropdown').click()
```

**Never** select a row by index (`page.locator('tr').first`, `.nth(1)`, etc.). Ant Design tables contain **two non-data `<tr>`s**: the header row (column titles) and a hidden `<tr class="ant-table-measure-row" aria-hidden="true">` used for column measurement. So `tr.first` is the header and `tr.nth(1)` is the (invisible) measure row — both have no action controls and time out. For "the most recent / first / latest item" with no known name, select the first row that actually contains the action control you need (only real data rows do), then capture its name from the row text so the post-action assertion can re-query by name:
```python
row = page.locator('tr').filter(has=page.get_by_title('Delete')).first
row.wait_for(state='visible', timeout=15000)
name = row.inner_text().strip().split('\n')[0].strip()
# ...delete/edit via row...
expect(page.locator('tr').filter(has_text=name)).to_have_count(0, timeout=15000)
```
**Never** assert deletion against an index handle (`tr.first`/`.nth(...)`) — those indices always re-resolve to a surviving row (header + measure row always exist), so the count is never 0. Re-query by the captured `name`.

**EDIT forms are NOT create forms — the dashboard_facts only describe `/.../new` create pages.** When a scenario edits an existing item, clicking the row's Edit control routes to `/<resource>/edit/<id>` (a dynamic id, e.g. `/categories/edit/156951`), which is a *different page* with different button labels from the create page. Specifically: the **category edit form saves with `get_by_role('button', name='Save Changes')`** — NOT `'Save Category'` (that label only exists on `/categories/new`). The KNOWN DASHBOARD FACTS injected for a "category" scenario describe the CREATE page; do not copy its `Save Category` button onto an edit flow. The `Name *` field label is the same on both. When in doubt about an edit-page control, browse the edit page (`generator_setup_page` + `browser_snapshot`) rather than reusing create-page facts.

**Row action buttons are icon buttons whose accessible name comes from their `title` — and `name=` is a SUBSTRING match.** A category/tag row has several inline icon buttons (`Edit`, `Edit Permalink`, `Delete`, …). `get_by_role('button', name='Edit')` matches **both** `Edit` and `Edit Permalink` → strict-mode violation. **Always** pass `exact=True` for short row-action names, in both the row filter and the click:
```python
row = page.locator('tr').filter(has=page.get_by_role('button', name='Edit', exact=True)).first
row.get_by_role('button', name='Edit', exact=True).click()
```

**Categories list specifically has NO kebab menu** — the per-row Delete control is an icon with `title="Delete"`, not a kebab dropdown and not a `<button>` with accessible name "Delete". Click it **scoped to the row** (one match, so `exact`/`.last` are unnecessary):
```python
row.get_by_title('Delete').click()
```
**Never** use `get_by_role('button', name='Delete')` or `.published-action-dropdown` for category rows — the former matches nothing (it is a titled icon, not a named button) and the latter is the *tags* list's affordance.

---

## Deletion Confirmation Dialogs

**Never** match a deletion confirmation dialog by title (`get_by_role('dialog', name='Delete Article')`). The dialog title varies by content type (`'Delete Tag'`, `'Delete Article'`, `'Delete Category'`, etc.) and is frequently wrong when the LLM guesses it.

**Always** locate the dialog by role only and find the confirm button inside it:
```python
page.get_by_role('dialog').get_by_role('button', name='Delete').click()
```

---

## Locator Strategy

**Only** use semantic locators: `get_by_role()`, `get_by_text()`, `get_by_title()`.

**Never** use CSS selectors, XPath, or `locator()` for interactive elements. The sole exception is `button.publisher-switcher` (it has no unique ARIA label).

---

## Test Data Uniqueness

**Always** append a millisecond timestamp to every test data string that the test itself creates:
```python
ts = int(time.time() * 1000)
title = f'QA Article {ts}'
```

**Never** use hardcoded strings for names, titles, or slugs that the test creates — they cause cross-run conflicts when tests are re-run.

**Exception — operating on pre-existing named items:** When the user's prompt explicitly targets a specific item that already exists in the dashboard (e.g. "delete the tag named 'I am tag'", "edit the category called 'Sports'"), use the exact name as given — do NOT append a timestamp. The timestamp rule is for test-created data only. A delete/edit flow targeting a pre-existing item must use the literal name; appending a timestamp makes the locator unmatchable.

---

## Category & Tag Create Pages

**Never** assert `to_have_url(re.compile(r'/categories/'))` after saving on `/categories/new`. The pattern `/categories/` is a substring of the creation URL `/categories/new` itself — if the save fails and the page stays on `/categories/new`, the assertion still passes (false positive).

**Always** use a negative lookahead anchored directly after `/categories` (NOT after the slash):
```python
expect(page).to_have_url(re.compile(r'/categories(?!/new)'), timeout=15000)
```
This matches `/categories` and `/categories/` but NOT `/categories/new`. Do NOT write `r'/categories/(?!new)'` (with the slash before the lookahead) — that requires a trailing slash in the URL and will fail when the redirect goes to `/categories` without one.

**Always** verify the created category appears in the table after save. After the redirect, navigate to the categories list and assert the name row is visible:
```python
page.goto('/categories/')
row = page.locator('tr').filter(has_text=category_name)
row.wait_for(state='visible', timeout=15000)
```

The same false-positive trap applies to tags: `/tags/create` → assert `r'/tags(?!/create)'` (not `r'/tags/'`).

**Never** hardcode a category name as a literal string directly in a `safe_sequential_fill` call. Even if the user's prompt names a specific category to create (e.g. "create a category called cat/dog"), always use a timestamp suffix so cross-run conflicts and silent validation failures are detectable:
```python
ts = int(time.time() * 1000)
category_name = f'cat-dog-{ts}'   # derive from the requested name, slug-safe, timestamp-suffixed
safe_sequential_fill(page, 'Name *', category_name, delay=50)
```

---

## Assertions

**Always** use regex form in `to_have_url()`:
```python
expect(page).to_have_url(re.compile(r'/posts/draft'), timeout=15000)
```

**Never** use exact string form: `to_have_url('/posts/draft')`.

**Always** add `timeout=15000` to `to_be_visible()`, `to_have_url()`, `to_be_enabled()`, and `to_be_disabled()` — server round-trips after saves take several seconds.

---

## Entity Pages (geography, food, horoscope, etc.)

Entity types (geography, food, horoscope, etc.) live at a different URL pattern from
standard content types. 
**Never** guess `/geography` or `/food` — those are 404s.

**Create URL pattern**: `/posts/entity/<plural>/<singular>/create`
- Geography: `/posts/entity/geographies/geography/create`
- Food: `/posts/entity/foods/food/create`
- Horoscope: `/posts/entity/horoscopes/horoscope/create`

**List URL pattern**: `/posts/published/<plural>?page_type=<singular>&create=<singular>`

**Never** look for an "Add New Geography" or similar button. Navigate directly to the create URL with `page.goto()`.

**Geography create fields** (verified live 2026-06-11):
- `get_by_role('textbox', name=re.compile(r'Name in English \( Slug \)'))` — slug, use regex substring match (ARIA name includes icon text)
- `get_by_role('textbox', name='Name', exact=True)` — display name under "About" section
- **Both** fields must be filled for the Publish button to become enabled
- Save button: `get_by_role('button', name='Publish')` — wait for `to_be_enabled` before clicking
- After save: URL -> `/posts/published/geographies`

**Phrase mapping — "filter by geography" / "filter articles by geography" / "Articles filter" / "create an article in it" / "add article(s)" (in context of a geography flow):**
These phrases ALWAYS refer to the Articles content-filter UI on the **geography entity create/edit page** itself. The geography entity page has a Content section with subsections (Live Blogs, Videos, Galleries, Web Stories, Articles); the **"Articles" subsection is not for creating an article — it's a filter that associates existing articles with this geography**. So when the user prompt says "create an article in it" or "add articles in the geography" or "filter articles by geography", you do ALL of the following on a single page:

1. Stay on `/posts/entity/geographies/geography/create` for the ENTIRE flow.
2. Fill the geography fields (slug, name, optionally description).
3. Click `+ Add Filter` under the Articles subsection (`nth(4)` — Live Blogs(0), Videos(1), Galleries(2), Web Stories(3), Articles(4)).
4. Configure the filter row (Filter by Field, Match Type, Value).

**Never** navigate to `/posts/article/create`, `/posts/draft`, or `/posts/published` for these flows. The draft and published list pages do NOT expose a geography filter; the Articles content filter on the geography entity page IS the entire "filter by geography" feature. Do NOT add a separate article-creation step to the plan even if the prompt mentions "article" — the Articles content filter section IS the article-related step.

**Picking a dynamic value from the Articles filter Value combobox**:
The Value combobox (no ARIA name; the last combobox on the form once the filter row exists) lists every published geography. Values change as geographies are added/removed. When the prompt says "whichever value is available" or doesn't name a specific geography, open the combobox and pick the first option from the **last** `.ant-select-dropdown` in DOM order:
```python
page.get_by_role('combobox').last.click()
value_dropdown = page.locator('.ant-select-dropdown').last
value_dropdown.locator('.ant-select-item-option').first.wait_for(state='visible')
value_dropdown.locator('.ant-select-item-option').first.click()
```
Why `.last` on the dropdown, not `:visible` or `:not(.ant-select-dropdown-hidden)`: Ant Design keeps closed dropdowns in the DOM and during the Match-Type dropdown's close-animation BOTH dropdowns are briefly "visible" by Playwright's check, so `.ant-select-item-option:visible` resolves to "Matches" instead of the value. The most-recently-opened dropdown is always the last `.ant-select-dropdown` in DOM order — that selector is stable. This is the documented exception to the "no CSS selectors" rule (Ant Design dropdown options are ARIA-hidden, so `get_by_role('option')` always times out and `get_by_title()` requires a name you don't know in advance).

```python
page.goto('/posts/entity/geographies/geography/create')
safe_fill(page, re.compile(r'Name in English \( Slug \)'), f'qa-geo-{ts}')
safe_fill(page, 'Name', f'QA Geography {ts}', exact=True)
expect(page.get_by_role('button', name='Publish')).to_be_enabled(timeout=5000)
page.get_by_role('button', name='Publish').click()
expect(page).to_have_url(re.compile(r'/posts/published/geographies'), timeout=15000)
```
