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

**Never** treat this as a native file chooser — clicking the drop-zone opens an **in-DOM "Media Library" dialog** (verified live 2026-07-01). Select an existing item **by its checkbox** and confirm with **Insert Media**:
```python
dialog = page.get_by_role('dialog')
dialog.get_by_role('checkbox').first.click()               # SELECT a grid item via its checkbox
page.get_by_role('button', name='Insert Media').click()    # confirm — modal closes, image attaches
```
**Do NOT select with `get_by_role('img').first`** (verified live 2026-07-03): the first `<img>` in the dialog is the upload drop-zone icon — clicking it opens a **native OS file chooser** and the run stalls with no file to give it. Grid items are selected via their **checkbox** (there are ~16 in view). Critically, the **`Insert Media` button does not exist in the DOM until an item is selected** — with nothing selected, `get_by_role('button', name='Insert Media')` matches zero elements and times out (`Locator.click: Timeout exceeded, waiting for get_by_role("button", name="Insert Media")`). Clicking a checkbox is what makes Insert Media appear and enable.

**Always** attach the image by selecting an existing grid item and clicking **Insert Media** (bottom-right of the modal). **Never** click the modal's **Upload Media** button — it fires a native OS file chooser that stalls the run with no file to hand it, so Publish never enables and the test times out. The grid reliably holds images from earlier runs, so `Insert Media` always has something to attach. The `Upload your Web Story image` placeholder disappearing is the signal the required image is attached and Publish can enable.

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

## Video & Web Story Create — Embed/Image BEFORE Title/Permalink

**Always** add the Featured Video (or Web Story image) **before** filling Title or Permalink on video and web story create forms. The Title field's React-controlled Permalink auto-generation fires a debounced update. If `safe_sequential_fill` on Permalink starts immediately after `safe_sequential_fill` on Title, that debounce fires mid-type — during `press_sequentially` — and overwrites the partially-typed slug, leaving Publish permanently disabled with no visible error.

The embed dialog / media library interaction takes several seconds, which is enough for the debounce to settle. After it closes, Title and Permalink are safe to fill.

**Video create** — correct order:
```python
page.get_by_role('button', name='Add Featured Video').click()
safe_fill(page, 'Media URL *', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
page.get_by_role('button', name='Submit').click()
safe_sequential_fill(page, 'Title *', title, delay=50)
safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-video-{ts}', delay=50)
```

**Web story create** — correct order:
```python
page.get_by_text('Upload your Web Story image').click()
dialog = page.get_by_role('dialog')
dialog.get_by_role('checkbox').first.click()   # select via checkbox, NOT get_by_role('img').first (drop-zone → file chooser)
page.get_by_role('button', name='Insert Media').click()
safe_sequential_fill(page, page.get_by_role('textbox', name='Title *').first, title, delay=50)  # .first — see below
safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-web-story-{ts}', delay=50)
```

**Never** fill Title or Permalink before the embed/image step on these two create forms.

### Web Story: the post `Title *` is AMBIGUOUS after the image inserts — target `.first`

Inserting the Web Story image adds a **slide** to the form, and that slide has its **own `Title *` textbox** (`#slide_title`, placeholder "Enter Title"). It shares the exact accessible name `Title *` with the post title (`#title`), so after the image step `get_by_role('textbox', name='Title *')` resolves to **two** elements — a strict-mode violation (`resolved to 2 elements`, verified live 2026-07-03). `exact=True` does **not** help (both names are exactly "Title *"). The POST title is **first in DOM order**, so narrow it with `.first` and hand the Locator to `safe_sequential_fill` (the helper accepts a Locator, not just a name string):
```python
safe_sequential_fill(page, page.get_by_role('textbox', name='Title *').first, title, delay=50)
```
Only the `Title *` field collides — `English Title ( Permalink ) *` (`#english_title`) and `Primary Category` stay unique, so keep passing those as plain name strings. The slide's other fields (`slide_desc`, `slide_cta_text`, `slide_cta_link`) have distinct names too.

---

## Title → Permalink Debounce Wait (global, auto-enforced)

**Any time a `'Title *'` fill is immediately followed by a Permalink fill, a `page.wait_for_timeout(500)` must sit between them.** The Title field's React-controlled Permalink auto-generation is debounced; if the Permalink `safe_sequential_fill` starts before that debounce settles, it fires mid-`press_sequentially` and corrupts the slug, leaving Publish/Save **permanently disabled with no visible error** (symptom: intermittent `to_be_enabled` timeout on a `disabled` button). This is a property of the **Title+Permalink field pair**, not of any one page — it applies to gallery, live blog, article, custom page, and every other create form that has both fields back-to-back.

You do **not** need to write this wait by hand. `spec_sanitizer._insert_permalink_debounce_wait` inserts it deterministically after write, for every flow, whenever a `'Title *'` fill precedes a Permalink fill with no wait already between them (idempotent — it never double-inserts). The examples below still show the wait explicitly for clarity, but omitting it is not a defect: the sanitizer adds it. The one thing that would defeat the guard is filling Title with plain `safe_fill` instead of `safe_sequential_fill` — don't (Title is React-controlled; see below).

```python
safe_sequential_fill(page, 'Title *', title, delay=50)
page.wait_for_timeout(500)   # auto-inserted by the sanitizer if omitted
safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}', delay=50)
```

---

## React-Controlled Text Inputs

Some inputs are React-controlled and do not fire `onChange` when filled with `fill()`. Using `fill()` on these fields succeeds silently but leaves the form's save button permanently disabled — the single most common failure mode in generated tests.

**Always** use `safe_sequential_fill(page, field_label, value, delay=50)` for React-controlled fields. Known React-controlled fields on this dashboard:
- `'Title *'` on article create, custom content create, and similar create forms
- `'English Title ( Permalink ) *'` on ALL create forms (article, video, gallery, live blog, custom page, and any other content type with a Permalink field) — the async uniqueness check only reacts to real keystroke events; `safe_fill()` leaves Publish permanently disabled even with a valid unique value
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

## Published List — Edit Pencil vs. Edit Permalink

The published list Actions column has four controls per row (left to right): Edit pencil, View eye, Edit Permalink chain, and the `.published-action-dropdown` kebab. **"Edit" is a direct inline icon — it is NOT a kebab menu item.**

**Always** click the pencil icon directly, scoped to the row, with `exact=True`:
```python
row = page.locator('tr').filter(has_text=title)
row.wait_for(state='visible', timeout=15000)
row.get_by_title('Edit', exact=True).click()
```

**Never** open the kebab and look for menuitem `'Edit'` — it is not there. The kebab only contains: `"Edit Permalink"`, `"Duplicate Page"`, `"Push Notification"`, `"Distribute Post"`, `"Unpublish"`, `"Delete"`.

**Never** omit `exact=True` on the Edit click. `name='Edit'` without `exact=True` is a substring match — it matches `"Edit Permalink"` (the chain icon) first and opens the "Edit Permalink" modal instead of navigating to the edit form. Confirmed failure mode (2026-07-02).

The kebab pattern (`.published-action-dropdown` → `.ant-dropdown:not(.ant-dropdown-hidden)` → menuitem) is **only** for Delete and other kebab-only actions, never for Edit.

---

## Published List — "Set as Featured" is a BULK-BAR button, needs a featured image

Verified live 2026-07-03. Featuring a post is **not** a per-row kebab action. Ticking one or more row checkboxes surfaces a **bulk-action bar** above the table (`"<n> Selected"`) with plain `<button>`s: **Send for Revision · Set as Featured · Distribute Post · More Actions · Clear**.

```python
row = page.locator('tr').filter(has_text=title).first
row.wait_for(state='visible', timeout=15000)
row.get_by_role('checkbox').click()
page.get_by_role('button', name='Set as Featured').click()
```

- **Never** look for `get_by_title('More Actions')` on a row, and never open the `.published-action-dropdown` kebab to find "Set as Featured" — the kebab has no featuring option, and "More Actions" is a button in the **bulk bar**, not a per-row control. (This exact mistake — `row...get_by_title('More Actions', exact=True)` — timed out and failed a run, 2026-07-03.)
- **A post can only be featured if it has a featured image.** Clicking "Set as Featured" on an imageless post opens a **"Set as featured"** dialog ("… without a featured image Or are Custom Content … will be excluded", `[Cancel]` / `[Proceed without them]`) and proceeding features **nothing**. So a self-contained featuring test must **create its own article WITH a featured image** (see *Add Featured Image* below), never reuse arbitrary/hardcoded rows. When the post has an image it is featured **directly, with no dialog**.
- **Success indicator:** a featured row shows a `title="Featured Post"` badge in its Title cell. Reload the filtered list, then assert:
  ```python
  expect(page.locator('tr').filter(has_text=title).first.get_by_title('Featured Post')).to_be_visible(timeout=15000)
  ```
  Do **not** assert `get_by_title('Featured')` — the real title is `"Featured Post"`.

---

## Article "Add Featured Image" — Media-Library modal (NO checkboxes, "Insert Image")

Verified live 2026-07-03. The article create form's featured image opens the same Media Library modal as Web Story, **but this variant has NO checkboxes** and its confirm button is **"Insert Image"** (not "Insert Media"):

```python
page.get_by_text('Add Featured Image').click()
dialog = page.get_by_role('dialog')
dialog.locator('.ant-card-body').first.click()          # pick first existing asset (never hardcode a filename)
page.get_by_role('button', name='Insert Image').click()
```

Same drop-zone trap as Web Story: **do NOT** `dialog.get_by_role('img').first.click()` — the first `<img>` is the upload control and opens a native OS file chooser. Select a tile by its `.ant-card-body` card; that enables "Insert Image".

---

## Ant Design Table Row Locators

**Scope:** this whole section applies to the **table**-based list pages (tags, categories, posts/published, drafts). It does **NOT** apply to the **Media Library** (`/media`), which is a card grid with **zero `<tr>` elements** — using `page.locator('tr')` there matches nothing and times out. For anything on `/media`, follow the *Media Library* heuristic below instead.

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

## Media Library (`/media`) is a card grid, NOT a table

The Media Library renders items as **Ant cards** (`div.ant-card.media-listing-card`) inside an infinite-scroll grid (`.media-listing-grid`). There are **no `<tr>` elements on this page at all** — every `page.locator('tr')` / `get_by_role('row')` pattern from the table section above matches nothing here and times out. This is the #1 way a media-flow test silently breaks: the generic table row pattern gets copied onto `/media`.

**Sanctioned CSS exception (like `button.publisher-switcher`):** `.media-listing-grid`, `.media-listing-card`, and `.pl-search-bar button` (the icon-only search button) are approved CSS locators for this page — the grid cards and the search button have no semantic (role/name) locator. Everything *after* opening a card is semantic.

**The search button is an ICON-ONLY button with no accessible name.** There IS a magnifier search button next to the search box, but it has no aria-label/title/text, so `get_by_role('button', name='Search')` matches nothing and times out. Click it via the sanctioned CSS locator `page.locator('.pl-search-bar button')`. (Pressing Enter in the box also triggers search.) Verified live: clicking it issues `GET /api/media/?…&filename=<term>` and narrows the grid to the match.

**The filename is NOT rendered as card text.** A card's visible text is `"Download"` + a long storage hash + the media's **alt text/title** — the human filename you searched for never appears in the DOM text. So `page.locator('.media-listing-card').filter(has_text='qa-media-….png')` matches nothing. Instead, **search first** (which narrows the grid to the matching item), then act on the sole result:
```python
box = page.get_by_role('textbox', name='Search by name, path, or alt text')
box.fill(filename)                              # e.g. 'qa-media-1782883698294.png'
page.locator('.pl-search-bar button').click()  # icon-only search button (no accessible name)
card = page.locator('.media-listing-card').first   # grid narrows to the match (16 -> 1)
card.wait_for(state='visible', timeout=15000)
```

**Delete affordance — click the card to open its detail panel, then use the named Delete button.** Clicking a card opens an inline detail panel (NOT a modal) with three *named* buttons: `Edit Image Details`, `Copy to clipboard`, and `Delete`. The `Delete` button is page-level (not scoped inside the card), and `get_by_role('button', name='Delete', exact=True)` resolves to exactly one match:
```python
card.click()
page.get_by_role('button', name='Delete', exact=True).click()
```
(There is also a hover-overlay trash icon on each card, but it is icon-only with no accessible name — prefer the card-click → named-button flow above.)

**Confirm** in the Ant modal (a real `role="dialog"`, titled "Delete Media", body "…delete 1 selected media…", buttons "Cancel" / "Delete"):
```python
page.get_by_role('dialog').get_by_role('button', name='Delete').click()
```

**Assert gone** by re-checking the (still-filtered) grid — do NOT assert against filename text, which never rendered:
```python
expect(page.locator('.media-listing-card')).to_have_count(0, timeout=15000)
```

---

## Photo Gallery

**Never** include "Add Slide", image upload, or media library steps in a Photo Gallery creation test. The "Add Slide" button adds an empty placeholder — it does NOT open a file chooser or a media library dialog. Attempting to interact with `Upload Media` after clicking "Add Slide" will leave the Publish button disabled because the upload flow is incomplete.

**Publish is enabled by Title + Permalink + Primary Category alone.** The minimum passing test is:
```python
page.goto('/posts/gallery/create')
safe_sequential_fill(page, 'Title *', title, delay=50)
page.wait_for_timeout(500)   # Title->Permalink debounce wait — auto-inserted by the sanitizer if omitted
safe_sequential_fill(page, 'English Title ( Permalink ) *', f'qa-gallery-{ts}', delay=50)
page.get_by_role('combobox', name='Primary Category').click()
page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first.click()
expect(page.get_by_role('button', name='Publish')).to_be_enabled(timeout=15000)
page.get_by_role('button', name='Publish').click()
```

**Why the `wait_for_timeout(500)` is mandatory here (same debounce race as Video/Web Story, but with no buffer).** The Title field's React-controlled Permalink auto-generation is debounced. On video and web-story forms the embed/image step runs *before* Title and absorbs that debounce. The gallery has **no** pre-Title step (see the "Never include Add Slide/upload" rule above), so Title and Permalink run cold and back-to-back — the debounce fires mid-type during `press_sequentially` on Permalink, corrupts the slug, and leaves Publish **permanently disabled with no visible error**. The 500 ms wait lets the debounce fire and settle into Permalink first; `safe_sequential_fill` then cleanly replaces it (Ctrl+A / Delete / retype) with no pending timer to collide. Symptom without the wait: intermittent `to_be_enabled` timeout on a `disabled` Publish button.

**Editing an already-published gallery saves with `Update`, NOT `Publish` or `Save Changes`.** The create form publishes with a `Publish` button; but once a post is live, its edit form (reached via the published-list Edit pencil, URL `/posts/gallery/<id>`) replaces `Publish` with an `Update` button. Verified live 2026-07-02 — the edit form's action buttons are exactly `Preview`, `Update`, `Save as Draft`; there is **no** `Publish` and **no** `Save Changes` on it. Writing either of those for the edit-save step targets a button that does not exist, so `expect(...).to_be_enabled()` waits out its full timeout and the run is killed. `Update` saves and redirects back to the Gallery published list, so assert the edited row there afterward:
```python
# ...create + publish the gallery first, landing on the Gallery published list...
row = page.locator('tr').filter(has_text=title)
row.wait_for(state='visible', timeout=15000)
row.get_by_title('Edit', exact=True).click()          # pencil icon -> /posts/gallery/<id> edit form
page.get_by_role('textbox', name='Title *').wait_for(timeout=15000)
safe_sequential_fill(page, 'Title *', f'{title}-edited', delay=50)
update = page.get_by_role('button', name='Update')    # NOT 'Publish', NOT 'Save Changes'
expect(update).to_be_enabled(timeout=15000)
update.click()
expect(page.locator('tr').filter(has_text=f'{title}-edited')).to_be_visible(timeout=15000)
```
This `Publish`-on-create / `Update`-on-edit split applies to the other publish-directly content posts too (article, video, web story, custom content) — the edit form of an already-published post uses `Update`.

---

## Deletion Confirmation Dialogs

**Never** match a deletion confirmation dialog by title (`get_by_role('dialog', name='Delete Article')`). The dialog title varies by content type (`'Delete Tag'`, `'Delete Article'`, `'Delete Category'`, etc.) and is frequently wrong when the LLM guesses it.

**Always** locate the dialog by role only and find the confirm button inside it:
```python
page.get_by_role('dialog').get_by_role('button', name='Delete').click()
```

---

## Bulk-Delete / "Delete All" Flows (Vacuous-Pass Trap)

**Never** write a delete-all loop where the emptiness assertion fires immediately after `page.goto()`. `locator.count()` does NOT auto-wait, so `to_have_count(0)` passes vacuously during the async render gap — the loop never runs and the test still passes while deleting nothing.

**Always** wait for the list to render before any count-based loop or emptiness assertion:
```python
rows = page.locator('tr').filter(has_text=title)
rows.first.wait_for(state='visible', timeout=15000)
remaining = rows.count()
```

**Then** loop with a count-drop wait after every delete:
```python
while remaining > 0:
    rows.first.get_by_role('button', name='Delete').click()
    page.get_by_role('dialog').get_by_role('button', name='Delete').click()
    remaining -= 1
    expect(rows).to_have_count(remaining, timeout=15000)
expect(rows).to_have_count(0, timeout=15000)
```

**Never** wait for `rows.first` to detach or become visible again between deletes. After a deletion the rows shift up — `rows.first` re-resolves immediately to a different still-attached row, so a detach/visible wait either hangs or races. The count-drop wait is the only shift-safe signal.

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

---

## Editing a Persisted Setting (Configurations, Singleton Values)

Applies to any test that edits an existing server-persisted value rather than creating a fresh timestamped entity — everything under `/configurations` (Site title, Site description, Timezone, Navigation, Theme, Branding, …) and any other singleton setting.

Three requirements are **mandatory**, in this order:

**1 — Use `safe_sequential_fill`, never `safe_fill`.**  These fields are React-controlled and pre-filled with the current saved value. `safe_fill` uses `.fill()`, which sets the DOM value WITHOUT firing React's `onChange`, so Save persists the OLD value while the box still shows the new text. The test passes while nothing was saved. `safe_sequential_fill` types real keys (select-all + delete + keystrokes) so React tracks the change and Save submits the new value.

**2 — Verify after a page reload.**  After clicking Save, call `page.reload()`, re-locate the field, then `expect(field).to_have_value(new_value, timeout=15000)`. Asserting on the same field without reloading only echoes back what you typed — it passes even when the save silently failed. The reload is what proves the value round-tripped through the server.

**3 — Capture the original value and restore it in a `finally` block.**  These are shared, publisher-wide config values, not throwaway timestamped data. The test must leave them exactly as found.

Canonical shape:
```python
field = page.get_by_role('textbox', name='Site description')
field.wait_for(state='visible')
original_value = field.input_value()
try:
    safe_sequential_fill(page, 'Site description', f'QA Description {ts}')
    page.get_by_role('button', name='Save').click()
    page.reload()
    field = page.get_by_role('textbox', name='Site description')
    field.wait_for(state='visible')
    expect(field).to_have_value(f'QA Description {ts}', timeout=15000)
finally:
    field = page.get_by_role('textbox', name='Site description')
    field.wait_for(state='visible')
    safe_sequential_fill(page, 'Site description', original_value)
    page.get_by_role('button', name='Save').click()
    expect(field).to_have_value(original_value, timeout=15000)
```

This does **not** apply to create flows (article/tag/category/etc.) — those make fresh timestamped entities that need no restore, and their post-create URL-change check already proves the save.

---

## Verifying an item's presence in a list is pagination-sensitive

Lists render **only the current page** (Ant tables/pagination — off-page rows are not in the DOM), so `expect(get_by_text(value)).to_be_visible()` only inspects the visible page.

- **Newest-first lists** (published posts, categories, tags): a newly created item appears at the **TOP → page 1**. Assert directly; no paging needed.
- **Manually-ordered append-to-end lists** — those with per-row **"Move up"/"Move Down"** controls (e.g. the Navigation Navbar/Footer tab tables): a new item is appended to the **END → LAST page**. You MUST page to the last page before asserting, or it is a **false negative** on an item that really was created. Confirmed failure: "Add tab in Navigation" — tab created on page 2, assertion checked page 1.

Reach the last page (safe whether or not the list actually paginates), then assert:
```python
next_page = page.get_by_role('listitem', name='Next Page')
for _ in range(20):
    if next_page.count() == 0:
        break
    btn = next_page.get_by_role('button')
    if btn.count() == 0 or btn.is_disabled():
        break
    btn.click()
    page.wait_for_timeout(300)
expect(page.get_by_text(f'QA Tab {ts}', exact=True)).to_be_visible(timeout=15000)
```
If the list has a search box, prefer searching/filtering for the item instead.

---

## Redirects form (Configuration → Redirects → "Add Redirect") — URL rules + pre-filled type

Verified live on the Add Redirect dialog:

- **Old URL / New URL must be FULL URLs on the publication's OWN site domain.** A bare path (e.g. `/foo`) is rejected inline with "Incorrect Domain"; an external New URL raises an external-URL warning. The button may look enabled either way, but Save does not persist while an error is showing. Derive the domain from the sidebar **"View Website"** link — never hardcode it (it is per-publisher). The form domain-trims the value, so the saved row shows just the path.
  ```python
  site = page.get_by_role('link', name='View Website').get_attribute('href').rstrip('/')
  safe_sequential_fill(page, 'Old URL', f'{site}/test-redirect-{ts}', delay=50)
  safe_sequential_fill(page, 'New URL', f'{site}/home', delay=50)
  ```
- **"Select Redirect Type *" is a PRE-FILLED combobox** (defaults to "Permanently Redirect"). Do NOT click or select it — its `.ant-select-selection-item` overlays the input and intercepts the click (hangs the run). Leave it at its default.
- The URL field labels carry a help-icon glyph ("Old URL question-circle *"); locate by the clean **leading substring** ('Old URL' / 'New URL') — `safe_sequential_fill` uses `exact=False`.
- Verify by the domain-trimmed path in the **newest-first** list, using ONLY the **unique** Old URL path: `expect(page.get_by_text(f'/test-redirect-{ts}', exact=True)).to_be_visible(timeout=15000)`. Do NOT also assert the destination (e.g. `/home`) — shared destinations match many rows and raise a strict-mode violation. The unique source path alone proves the redirect was created.
- **Deleting a redirect:** the per-row Actions buttons are UNNAMED lucide icon buttons (`aria-hidden` SVGs, class `action-button`) — pencil = Edit, trash = Delete — so `get_by_role('button', name='Delete')` matches NOTHING. Delete is the **last** action button in the row. Search first (the Search box needs an explicit `Enter`), then per matching row: `row.get_by_role('button').last.click()` (the Actions column is off-screen right, but Playwright auto-scrolls on click), then confirm in the dialog which DOES have a named button: `page.get_by_role('dialog').get_by_role('button', name='Delete').click()`.
  ```python
  rows = page.locator('tr').filter(has_text=f'/test-redirect-{prefix}')
  rows.first.wait_for(state='visible', timeout=15000)   # prove rows rendered (avoid vacuous count=0)
  remaining = rows.count()
  while remaining > 0:
      rows.first.get_by_role('button').last.click()
      page.get_by_role('dialog').get_by_role('button', name='Delete').click()
      remaining -= 1
      expect(rows).to_have_count(remaining, timeout=15000)
  ```
