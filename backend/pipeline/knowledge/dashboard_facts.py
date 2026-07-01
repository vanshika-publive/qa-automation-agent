import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FieldConstraint:
    field: str
    min: Optional[int] = None
    max: Optional[int] = None
    react_controlled: bool = False
    note: Optional[str] = None


@dataclass
class ComboboxFacts:
    aria_name: str
    required: bool = False
    known_options: list = field(default_factory=list)
    default_option: Optional[str] = None
    note: Optional[str] = None
    # True for Ant Design Selects backed by a long, per-publisher, time-varying option list
    # (rc-virtual-list renders only ~9 options at once). A get_by_title() value that was genuinely
    # visible during planning/generation can still be absent at test-run time, so these fields must
    # always be selected via the dynamic ".ant-select-item-option" pattern, never a hardcoded title.
    virtualized: bool = False


@dataclass
class PublishStep:
    kind: str
    button: Optional[str] = None
    pattern: Optional[str] = None
    path_pattern: Optional[str] = None
    row_matcher: Optional[str] = None
    action: Optional[str] = None


@dataclass
class PageFacts:
    path: str
    title: str
    direct_navigation: bool = True
    required_for_draft: list = field(default_factory=list)
    required_for_publish: list = field(default_factory=list)
    optional_fields: list = field(default_factory=list)
    comboboxes: list = field(default_factory=list)
    save_button: str = ''
    after_save_url_pattern: str = ''
    publish_flow: list = field(default_factory=list)
    published_list_path: Optional[str] = None
    draft_list_path: Optional[str] = None
    note: Optional[str] = None


ARTICLE_CREATE = PageFacts(
    path='/posts/article/create',
    title='Article Create',
    required_for_draft=[
        FieldConstraint(field='Title *', min=10, react_controlled=True, note='React-controlled — MUST use safe_sequential_fill, not safe_fill. Dashboard shows "Title is too short" warning under 10 chars and blocks publish.'),
        FieldConstraint(field='English Title ( Permalink ) *', react_controlled=True, note="MUST use safe_sequential_fill, not safe_fill — the async permalink-uniqueness check only reacts to real keystroke events, so plain fill() leaves Publish permanently disabled even with a valid unique value. Use a UNIQUE slug every run, e.g. f'qa-{ts}' — never reuse a permalink."),
    ],
    # Summary and Meta Description ARE publish gates despite being framed as "SEO" fields —
    # the dashboard blocks Publish until both clear their minimum length.
    required_for_publish=[
        FieldConstraint(field='Summary', min=140, note='Dashboard shows "Summary is too short" warning under 140 chars and blocks publish.'),
        FieldConstraint(field='Meta Description', min=140, max=170, note='Dashboard shows "Description is too short" warning under 140 chars; blocks publish. Keep under 170 too.'),
    ],
    optional_fields=[
        FieldConstraint(field='Banner Description'),
        FieldConstraint(field='Focus Keyphrase', max=60),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, virtualized=True, note='REQUIRED. Virtualized + per-publisher — click and snapshot, pick the first live .ant-select-item-option; never hardcode a name.'),
        ComboboxFacts(aria_name='Credits', required=True, note='REQUIRED but auto-filled with the logged-in user — no action needed.'),
        ComboboxFacts(aria_name='Tags'),
        ComboboxFacts(aria_name='Additional Category'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    publish_flow=[
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published?page_type=Article&ptype=Article&create=article',
    draft_list_path='/posts/draft',
    note=('Articles PUBLISH DIRECTLY from this page. Fill Title (>=10 chars) + English Title (Permalink) + '
          'Primary Category (Credits auto-fills with the logged-in user) + Summary (>=140 chars) + '
          'Meta Description (140-170 chars), then click "Publish" — the article goes straight to '
          '/posts/published. The Publish button is briefly disabled right after the fields are filled (async '
          'permalink validation), so wait for expect(get_by_role("button", name="Publish")).to_be_enabled(timeout=15000) '
          'before clicking — never click immediately. There is NO "Save as Draft -> Edit -> Publish" detour. '
          '"Save as Draft" is a SEPARATE optional action that sends the article to /posts/draft instead of publishing it. '
          'To DELETE a published article, go to the Published list and use the row kebab menu (see Published List facts).'),
)

CUSTOM_PAGE_CREATE = PageFacts(
    path='/posts/custom-page/create',
    title='Custom Content Template Page',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill'),
        FieldConstraint(field='English Title ( Permalink ) *', max=250, note="use a UNIQUE slug every run, e.g. f'qa-custom-{ts}'"),
    ],
    required_for_publish=[],
    optional_fields=[
        FieldConstraint(field='Summary', note='SEO only — NOT required to publish'),
        FieldConstraint(field='Meta Description', note='SEO only — NOT required to publish'),
        FieldConstraint(field='Banner Description'),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, virtualized=True, note='REQUIRED. Virtualized + per-publisher — click and snapshot, pick the first live option; never hardcode.'),
        ComboboxFacts(aria_name='Credits', required=True, note='REQUIRED but auto-filled with the logged-in user — no action needed.'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    publish_flow=[
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published?page_type=CustomPage&ptype=CustomPage&create=custom-page',
    draft_list_path='/posts/draft',
    note=('Same direct-publish flow as Article Create: fill Title + English Title (Permalink) + Primary Category '
          '(Credits auto-fills), wait for the Publish button to be enabled, then click "Publish" -> /posts/published. '
          'No Save-as-Draft -> Edit -> Publish detour. Delete a published item from the Published list row kebab.'),
)

DRAFT_LIST = PageFacts(
    path='/posts/draft',
    title='Draft List',
    save_button='',
    after_save_url_pattern='/posts/draft',
    note=('Table header: "Title Content Type Created By Updated By Timeline Actions". '
          'Row actions: link "Edit", link "Preview", button "Discard". '
          'CRITICAL — Ant Design <tr> elements have NO accessible name. NEVER use get_by_role("row", name=...) '
          '(role WITH a name filter) — it always times out. Find the row with: '
          'row = page.locator("tr").filter(has_text=title) then row.wait_for(state="visible", timeout=15000). '
          'Discard: row.get_by_role("button", name="Discard").click() -> '
          'page.get_by_role("dialog").get_by_role("button", name="Discard").click(). '
          'NEVER use get_by_role("dialog", name="Discard Article") — dialog title varies by content type. '
          'TOPMOST/LATEST-ITEM SCENARIOS (no specific title to filter by): use page.get_by_role("row").nth(1) '
          '(role WITHOUT a name filter is fine — only get_by_role("row", name=...) is banned, per above). '
          'NEVER page.locator("tr").first or page.locator("tbody tr").first — the table header is also a <tr>, '
          'and Ant Design additionally renders a hidden aria-hidden="true" "ant-table-measure-row" as the '
          'literal first <tr> inside <tbody>, so even "tbody tr".first grabs an invisible row, not real data. '
          'get_by_role("row") is the only locator that skips both automatically (aria-hidden rows never get a '
          'role), so nth(0) is the header and nth(1) is the first real data row.'),
)

PUBLISHED_LIST = PageFacts(
    path='/posts/published',
    title='Published List',
    save_button='',
    after_save_url_pattern='/posts/published',
    note=('CRITICAL — CONTENT-TYPE BLEED (confirmed bug, 2026-07-01): the bare /posts/published with NO query '
          'params interleaves EVERY content type (Article, Video, Web Story, Photo Gallery, Live Blog, Custom '
          'Content) in one list sorted by recency. "Topmost"/"latest" on that bare URL means topmost-of-ANY-type, '
          'NOT topmost of the type the scenario asked for. A plan for "edit the topmost video" that did '
          "page.goto('/posts/published') then get_by_role('row').nth(1) silently edited the topmost LIVE BLOG "
          'instead (it happened to be more recently updated than any video) — the test still passed because '
          'nothing asserted the edited row was actually a video. RULE: whenever a flow targets ONE specific '
          'content type (edit/delete/publish/topmost/latest on a video, article, live blog, web story, photo '
          'gallery, or custom content item), you MUST navigate to that type\'s FILTERED published-list URL, '
          'never the bare /posts/published: '
          'Article -> /posts/published?page_type=Article&ptype=Article&create=article ; '
          'Video -> /posts/published?page_type=Video&ptype=Video&create=video ; '
          'Live Blog -> /posts/published?page_type=LiveBlog&ptype=LiveBlog&create=live-blog ; '
          'Web Story -> /posts/published?page_type=Web Story&ptype=Web Story&create=web-story ; '
          'Photo Gallery -> /posts/published?page_type=Gallery&ptype=Gallery&create=gallery ; '
          'Custom Content -> /posts/published?page_type=CustomPage&ptype=CustomPage&create=custom-page. '
          'These exact links are visible live in the left sidebar under the "Content Type" heading — confirm '
          'there if unsure. Only use the bare /posts/published when the scenario genuinely means "any post of '
          'any type" (e.g. a mixed-content smoke check), never as a shortcut for a single-content-type flow. '
          'Columns: Title, Categories, Credits, '
          'Page Views, Word Count, SEO Score, Timeline, Actions. Per-row Actions: link "Edit", link "View", '
          'button "Copy url to clipboard", and a kebab (more-actions) icon button with NO accessible name. '
          'CRITICAL — Ant Design <tr> elements have NO accessible name. NEVER use get_by_role("row", name=...) — '
          'it always times out. ALWAYS find the row with: row = page.locator("tr").filter(has_text=title) '
          'then row.wait_for(state="visible", timeout=15000) before interacting. '
          'Open the kebab: row.locator(".published-action-dropdown").click(). '
          'Kebab menu items: Edit Permalink, Duplicate Page, Push Notification, Distribute Post, Unpublish, Delete. '
          'DELETE flow: row.locator(".published-action-dropdown").click() -> '
          'page.locator(".ant-dropdown:not(.ant-dropdown-hidden)").last.get_by_role("menuitem", name="Delete").click() -> '
          'page.get_by_role("dialog").get_by_role("button", name="Delete").click() -> '
          'assert row gone: expect(page.locator("tr").filter(has_text=title)).to_have_count(0, timeout=15000). '
          'NEVER use get_by_role("dialog", name="Delete Article") — dialog title varies by content type. '
          'NOTE: "Unpublish" is a DIFFERENT menu item (sends back to draft), NOT Delete. '
          'TOPMOST/LATEST-ITEM SCENARIOS (no specific title to filter by): use page.get_by_role("row").nth(1) '
          '— NEVER page.locator("tr").first and NEVER page.locator("tbody tr").first. Both of those are WRONG: '
          'the table header is also a <tr> (so .first / tbody-tr[0] can hit it), AND Ant Design additionally '
          'renders a hidden aria-hidden="true" "ant-table-measure-row" as the literal FIRST <tr> inside <tbody> '
          '(used internally to measure column widths) — so even "tbody tr".first grabs that invisible row, not '
          'real data. get_by_role("row") is the only locator that correctly skips both: it follows the '
          'accessibility tree, which excludes aria-hidden elements automatically, so nth(0) is the header and '
          'nth(1) is the first real data row. The row action is get_by_role("row").nth(1).get_by_role("link", '
          'name="Edit") — Edit is a LINK here, not a button; get_by_role("button", name="Edit") never matches '
          'and times out. Editing an ALREADY-PUBLISHED item also switches its save button from "Publish" to '
          '"Update" as soon as any field is changed — wait for and click get_by_role("button", name="Update"), '
          'not "Publish", when the flow edits an existing published item rather than creating a new one.'),
)

TAG_CREATE = PageFacts(
    path='/tags/create',
    title='Tag Create',
    required_for_draft=[
        FieldConstraint(field='Name *', react_controlled=True),
    ],
    optional_fields=[
        FieldConstraint(field='Meta Title'),
        FieldConstraint(field='Meta Description'),
    ],
    save_button='Save',
    after_save_url_pattern='/tags',
)

TAGS_LIST = PageFacts(
    path='/tags',
    title='Tags List',
    save_button='',
    after_save_url_pattern='/tags',
)

CATEGORY_CREATE = PageFacts(
    path='/categories/new',
    title='Category Create',
    required_for_draft=[
        FieldConstraint(field='Name *', react_controlled=True),
        FieldConstraint(field='Name in English (Permalink) *'),
    ],
    optional_fields=[
        FieldConstraint(field='Meta Title'),
        FieldConstraint(field='Meta Description'),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Content Type', required=True, known_options=['Article', 'Video'], default_option='Article', note='Sidebar also has title="Article" links — get_by_title("Article", exact=True).last is mandatory.'),
        ComboboxFacts(aria_name='Parent Category'),
    ],
    save_button='Save Category',
    after_save_url_pattern='/categories',
)

CATEGORIES_LIST = PageFacts(
    path='/categories',
    title='Categories List',
    save_button='',
    after_save_url_pattern='/categories',
    note=('No kebab/dropdown menu on this list, unlike the Posts Published list. Each row has direct inline '
          'buttons: Edit, Edit Permalink, Delete. To delete: row = page.locator("tr").filter(has_text=name); '
          'row.get_by_title("Delete").click(); then confirm with '
          'page.get_by_role("dialog").get_by_role("button", name="Delete").click() (dialog title "Delete Category"). '
          'NEVER use .published-action-dropdown or an .ant-dropdown menuitem here — that selector is specific to '
          'the Posts Published list and does not exist on this page. '
          'TOPMOST/LATEST-ITEM SCENARIOS (no specific name to filter by): use page.get_by_role("row").nth(1). '
          'NEVER page.locator("tr").first or page.locator("tbody tr").first — the table header is also a <tr>, '
          'and Ant Design additionally renders a hidden aria-hidden="true" "ant-table-measure-row" as the '
          'literal first <tr> inside <tbody>, so even "tbody tr".first grabs an invisible row, not real data. '
          'get_by_role("row") is the only locator that skips both automatically (aria-hidden rows never get a '
          'role), so nth(0) is the header and nth(1) is the first real data row.'),
)

GEOGRAPHY_CREATE = PageFacts(
    path='/posts/entity/geographies/geography/create',
    title='Geography Create',
    required_for_draft=[
        FieldConstraint(field='Name in English ( Slug )', note='ARIA name includes "info-circle" icon text — use regex locator: re.compile(r"Name in English \\( Slug \\)"). fill() works (triggers auto-save).'),
        FieldConstraint(field='Name', note='Under "About" section. No * in UI but BOTH slug and Name must be filled for Publish to enable.'),
    ],
    optional_fields=[
        FieldConstraint(field='Summary'),
    ],
    comboboxes=[
        ComboboxFacts(
            aria_name='Filter by Field info-circle *',
            note='In the Articles content filter section. Click "+ Add Filter" button (nth(4)) first to reveal. After selecting field, Match Type combobox appears, then Value combobox (no ARIA name — use get_by_role("combobox").last).',
            known_options=['Published by', 'Primary Category', 'Categories', 'Tags', 'Contributors', 'Also Read', 'Reporter', 'Geography', 'Custom related links'],
        ),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published/geographies',
    published_list_path='/posts/published/geographies',
)

VIDEO_CREATE = PageFacts(
    path='/posts/video/create',
    title='Video Create',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill, not safe_fill.'),
        FieldConstraint(field='English Title ( Permalink ) *', react_controlled=True, note="MUST use safe_sequential_fill — plain fill() leaves Publish permanently disabled even with a valid unique value. Use a UNIQUE slug every run, e.g. f'qa-video-{ts}'."),
        FieldConstraint(field='Featured Video *', note='NOT a file upload — see NOTE below for the real "Add Featured Video" -> "Embed Media" -> "Media URL *" flow.'),
    ],
    optional_fields=[
        FieldConstraint(field='Summary'),
        FieldConstraint(field='Meta Description'),
        FieldConstraint(field='Focus Keyphrase'),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, virtualized=True, note='REQUIRED. Virtualized + per-publisher — click and snapshot, pick the first live .ant-select-item-option; never hardcode a name.'),
        ComboboxFacts(aria_name='Credits', required=True, note='REQUIRED but auto-filled with the logged-in user — no action needed.'),
        ComboboxFacts(aria_name='Additional Category'),
        ComboboxFacts(aria_name='Tags'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    publish_flow=[
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published?page_type=Video&ptype=Video&create=video',
    note=(
        'There is NO "Upload Video" button and NO native file chooser on this page — never write '
        'page.expect_file_chooser() or get_by_role("button", name="Upload Video") here, both time out. '
        'The "Featured Video *" field is filled by clicking button "Add Featured Video", which opens a dialog '
        'titled "Embed Media" containing a single required field "Media URL *" (placeholder "Enter video URL") '
        'plus "Cancel"/"Submit" buttons. Fill "Media URL *" with a real video URL then click "Submit" to attach '
        'it and close the dialog — video is added by URL embed only, there is no desktop-upload path. '
        '(Verified live 2026-07-01 on OdishaTv - Khabar.) The unrelated "Upload ( 16:9 )" button under '
        '"Custom Thumbnail" uploads a static image thumbnail, not the video, and is optional.'
    ),
)

LIVE_BLOG_CREATE = PageFacts(
    path='/posts/live-blog/create',
    title='Live Blog Create',
    published_list_path='/posts/published?page_type=LiveBlog&ptype=LiveBlog&create=live-blog',
    note=(
        'Live Blog is a DISTINCT content type from Video and Article — confirmed live in the sidebar "Content '
        'Type" section (/posts/live-blog/create to create, /posts/published?page_type=LiveBlog&ptype=LiveBlog&'
        'create=live-blog to see only live blogs). Field-level facts for this create page are NOT yet hand-'
        'verified — treat every asterisk-marked field in the live snapshot as required (see live-discovery '
        'fallback) rather than assuming Article/Video field names apply. NEVER edit or delete a live blog by '
        'landing on the bare /posts/published and picking a row by position — always use the filtered URL above '
        'so the row you act on is actually a live blog.'
    ),
)

MEDIA_LIBRARY = PageFacts(
    path='/media',
    title='Media Library',
    required_for_draft=[
        FieldConstraint(field='File name *', react_controlled=True, note='Pre-filled from the uploaded filename. MUST use safe_sequential_fill, not safe_fill, to actually replace it — plain fill() is ignored on this React-controlled field.'),
        FieldConstraint(field='Alt text *', react_controlled=True, note='Pre-filled from the uploaded filename. MUST use safe_sequential_fill, not safe_fill.'),
    ],
    optional_fields=[
        FieldConstraint(field='Caption'),
        FieldConstraint(field='Source'),
    ],
    save_button='Upload',
    after_save_url_pattern='/media',
    note=(
        'Clicking "Upload Media" (get_by_role("button", name="Upload Media").last — see Ant Upload heuristic) does '
        'NOT open a modal or dialog. It fires a NATIVE OS FILE CHOOSER immediately, which the test MUST intercept '
        'with Playwright\'s file-chooser API before the click resolves:\n'
        '    with page.expect_file_chooser() as fc_info:\n'
        '        page.get_by_role("button", name="Upload Media").last.click()\n'
        '    fc_info.value.set_files(random_desktop_png())\n'
        'random_desktop_png() (import from helpers) picks a real .png at random from the Desktop folder — never '
        'pass a fake/nonexistent path or an empty string.\n'
        'Only AFTER a file is chosen does the page replace the whole media grid with an "Upload Files" panel '
        'containing "File name *", "Alt text *", "Caption", "Source" fields plus "Cancel" and "Upload" buttons. '
        'BEFORE that panel renders, get_by_role("button", name="Upload") is a STRICT-MODE VIOLATION: "Upload" is '
        'a substring of "Upload Media", so it still matches the ant-upload span AND the "Upload Media" button on '
        'the still-visible original page. Only click get_by_role("button", name="Upload") AFTER set_files() and '
        'after filling File name */Alt text *, at which point it uniquely matches the panel\'s submit button. '
        'After a successful upload the panel closes and the new file appears in the media grid.'
    ),
)

PAGE_FACTS = {
    '/posts/article/create': ARTICLE_CREATE,
    '/posts/custom-page/create': CUSTOM_PAGE_CREATE,
    '/posts/draft': DRAFT_LIST,
    '/posts/published': PUBLISHED_LIST,
    # Content-type-filtered variants of the published list share the same row-matching/kebab/Update-button
    # facts as the bare list — registered under their own key so facts_for_prompt/plan_validator recognize
    # them as known pages instead of silently dropping PUBLISHED_LIST guidance for them.
    '/posts/published?page_type=Article&ptype=Article&create=article': PUBLISHED_LIST,
    '/posts/published?page_type=Video&ptype=Video&create=video': PUBLISHED_LIST,
    '/posts/published?page_type=LiveBlog&ptype=LiveBlog&create=live-blog': PUBLISHED_LIST,
    '/posts/published?page_type=CustomPage&ptype=CustomPage&create=custom-page': PUBLISHED_LIST,
    '/tags/create': TAG_CREATE,
    '/tags': TAGS_LIST,
    '/media': MEDIA_LIBRARY,
    '/categories/new': CATEGORY_CREATE,
    '/categories': CATEGORIES_LIST,
    '/posts/entity/geographies/geography/create': GEOGRAPHY_CREATE,
    '/posts/video/create': VIDEO_CREATE,
    '/posts/live-blog/create': LIVE_BLOG_CREATE,
}

# Aria names of comboboxes marked virtualized=True anywhere in PAGE_FACTS. A get_by_title() value
# for one of these is unsafe even when it was genuinely observed live -- the option must instead be
# picked via the dynamic '.ant-select-item-option' pattern. Used by plan_validator/spec_validator to
# enforce the rule structurally instead of relying on prompt text alone.
VIRTUALIZED_COMBOBOX_NAMES = sorted({
    cb.aria_name
    for facts in PAGE_FACTS.values()
    for cb in facts.comboboxes
    if cb.virtualized
})

KNOWN_PATH_PREFIXES = [
    '/posts/', '/categories', '/tags', '/media', '/team',
    '/settings', '/configurations', '/home', '/login',
    '/content-distribution', '/analytics', '/v2/',
]


def detect_intent(prompt):
    lower = prompt.lower()

    page = None
    if re.search(r'custom.?(content|page)', lower):
        page = CUSTOM_PAGE_CREATE
    elif re.search(r'article', lower):
        page = ARTICLE_CREATE
    elif re.search(r'\bvideo\b', lower):
        page = VIDEO_CREATE
    elif re.search(r'live\s*blog', lower):
        page = LIVE_BLOG_CREATE
    elif re.search(r'tag', lower):
        page = TAG_CREATE
    elif re.search(r'categor', lower):
        page = CATEGORY_CREATE
    elif re.search(r'geograph', lower):
        page = GEOGRAPHY_CREATE

    if not page:
        return None

    if re.search(r'publish', lower):
        return {'verb': 'publish', 'page': page}
    if re.search(r'discard', lower):
        return {'verb': 'discard', 'page': page}
    if re.search(r'delet', lower):
        return {'verb': 'delete', 'page': page}
    if re.search(r'edit', lower):
        return {'verb': 'edit', 'page': page}
    if re.search(r'draft|save.*as.*draft', lower):
        return {'verb': 'draft', 'page': page}
    if re.search(r'creat|add|new', lower):
        return {'verb': 'create', 'page': page}

    return None


def expand_preconditions(intent):
    steps = []
    if intent['verb'] == 'publish' and intent['page'].required_for_publish:
        for f in intent['page'].required_for_publish:
            if f.min and f.max:
                range_str = f'{f.min}–{f.max} characters'
            elif f.min:
                range_str = f'at least {f.min} characters'
            elif f.max:
                range_str = f'at most {f.max} characters'
            else:
                range_str = ''
            note_str = f' — {f.note}' if f.note else ''
            steps.append(f'Fill {f.field} with {range_str or "content"} (required to enable Publish{note_str})')
    return steps


def format_page_facts(facts):
    lines = [f'{facts.title} ({facts.path}):']
    if facts.direct_navigation:
        lines.append(f"- Navigate directly with page.goto('{facts.path}')")
    if facts.required_for_draft:
        lines.append('- Required for save/draft:')
        for f in facts.required_for_draft:
            helper = 'safe_sequential_fill' if f.react_controlled else 'safe_fill'
            note = f' ({f.note})' if f.note else ''
            lines.append(f'    • {f.field} — use {helper}{note}')
    if facts.required_for_publish:
        lines.append('- Required for PUBLISH (in addition to draft requirements):')
        for f in facts.required_for_publish:
            if f.min and f.max:
                range_str = f'{f.min}–{f.max} chars'
            elif f.min:
                range_str = f'≥{f.min} chars'
            elif f.max:
                range_str = f'≤{f.max} chars'
            else:
                range_str = ''
            note = f' — {f.note}' if f.note else ''
            lines.append(f'    • {f.field}{f" ({range_str})" if range_str else ""}{note}')
    if facts.comboboxes:
        lines.append('- Comboboxes:')
        for c in facts.comboboxes:
            req = ' [REQUIRED]' if c.required else ''
            default = f' — default: {c.default_option}' if c.default_option else ''
            lines.append(f'    • {c.aria_name}{req}{default}')
            if c.known_options:
                opts = ', '.join(f"'{o}'" for o in c.known_options)
                lines.append(f'        observed options: {opts}')
    if facts.save_button:
        lines.append(f"- Save button: get_by_role('button', name='{facts.save_button}')")
    if facts.after_save_url_pattern:
        escaped = facts.after_save_url_pattern.replace('/', '\\/')
        lines.append(f'- After save: URL matches /{escaped}/ ')
    if facts.publish_flow:
        lines.append('- PUBLISH flow:')
        for i, step in enumerate(facts.publish_flow, 1):
            if step.kind == 'click_button':
                lines.append(f'    {i}. Click button "{step.button}" (wait for to_be_enabled first)')
            elif step.kind == 'expect_url':
                escaped = step.pattern.replace('/', '\\/')
                lines.append(f'    {i}. Expect URL /{escaped}/')
            elif step.kind == 'click_row_action':
                lines.append(f'    {i}. In the row matching the {step.row_matcher}, click "{step.action}"')
            elif step.kind == 'navigate':
                lines.append(f'    {i}. Navigate to {step.path_pattern}')
    if facts.note:
        lines.append(f'- NOTE: {facts.note}')
    return '\n'.join(lines)


def facts_for_prompt(prompt):
    intent = detect_intent(prompt)
    pages = []

    if intent:
        pages.append(intent['page'])
        verb = intent['verb']
        # "save as draft" and "discard" act on the Draft list; "publish", "delete", and "edit"
        # (editing an already-published item) all act on the Published list.
        if verb in ('draft', 'discard'):
            draft_path = intent['page'].draft_list_path
            if draft_path and draft_path in PAGE_FACTS:
                pages.append(PAGE_FACTS[draft_path])
        if verb in ('publish', 'delete', 'edit'):
            pub_path = intent['page'].published_list_path
            if pub_path and pub_path in PAGE_FACTS:
                pages.append(PAGE_FACTS[pub_path])

    if not pages:
        return ''
    return '\n\n'.join(format_page_facts(p) for p in pages)


def facts_for_all_mentioned_pages(prompt):
    lower = prompt.lower()
    matched = []
    seen = set()

    def push(page):
        if page.path not in seen:
            seen.add(page.path)
            matched.append(page)

    is_geography_filter_flow = bool(re.search(r'geograph', lower) and re.search(r'\bfilter\b', lower))

    if re.search(r'custom.?(content|page)', lower):
        push(CUSTOM_PAGE_CREATE)
    if re.search(r'article', lower) and not is_geography_filter_flow:
        push(ARTICLE_CREATE)
    if re.search(r'\bvideo\b', lower):
        push(VIDEO_CREATE)
    if re.search(r'live\s*blog', lower):
        push(LIVE_BLOG_CREATE)
    if re.search(r'\btag\b|\btags\b', lower):
        push(TAG_CREATE)
    if re.search(r'categor', lower):
        push(CATEGORY_CREATE)
    if re.search(r'geograph', lower):
        push(GEOGRAPHY_CREATE)

    has_published_target = any(p.published_list_path for p in matched)
    # "save as draft" / "discard" surface the Draft list. Any content type that publishes to a
    # Published list also needs those facts for "publish", "delete", AND "edit an existing item"
    # scenarios ("edit the topmost X", "rename the latest Y") — editing an already-published item
    # means finding its row in the Published list first, so the row-finding gotchas (header <tr>,
    # hidden measure row, Update-vs-Publish button) apply just as much as to publish/delete.
    if not is_geography_filter_flow and re.search(r'\bdraft\b|save.*as.*draft|discard', lower):
        push(DRAFT_LIST)
    if has_published_target and re.search(r'publish|delet|\bedit\b|topmost|latest|rename|update', lower):
        push(PUBLISHED_LIST)

    if not matched:
        return ''
    return '\n\n'.join(format_page_facts(p) for p in matched)
