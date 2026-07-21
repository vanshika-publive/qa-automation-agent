import re
from dataclasses import dataclass, field
from typing import Optional

from pipeline.knowledge.content_type_builder_facts import CTB_KNOWN_PATH_PREFIXES


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
    # Ant Design Select backed by a per-publisher, time-varying list (~9 options visible at once).
    # A value observed during planning can be absent at test-run time — always pick via
    # ".ant-select-item-option", never a hardcoded title.
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
    # Dialog-launched create flows: the create form is NOT on this landing page — it lives inside
    # a dialog opened by clicking this button (e.g. "Create New Component"). When set, this page is
    # a launcher, not a form: the planner must open the dialog to observe the real required fields.
    # The exact button name (accessible name) that opens the first dialog.
    launch_button: Optional[str] = None


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
          'To DELETE a published article, go to the Published list and use the row kebab menu (see Published List facts). '
          'FEATURED IMAGE (optional to publish, but REQUIRED before an article can be "Set as Featured" on the '
          'Published list — imageless posts are excluded from featuring): click get_by_text("Add Featured Image") '
          'to open the Media Library modal, then pick the first existing asset with '
          'page.get_by_role("dialog").locator(".ant-card-body").first.click() (per-publisher + time-varying — never '
          'hardcode a filename) and click get_by_role("button", name="Insert Image"). This modal has NO checkboxes '
          '(unlike the Web Story "Insert Media" modal) and its confirm button is "Insert Image", not "Insert Media". '
          'Do NOT click get_by_role("img").first inside the modal — the first img is the upload control and opens an '
          'OS file chooser.'),
)

BLANK_PAGE_CREATE = PageFacts(
    path='/posts/custom-page/blank-page/create',
    title='Blank Canvas Create',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill'),
        FieldConstraint(field='English Title ( Permalink ) *', max=250, react_controlled=True, note="MUST use safe_sequential_fill — the async permalink-uniqueness check only reacts to real keystroke events. Use a UNIQUE slug every run, e.g. f'qa-blank-canvas-{ts}'."),
    ],
    required_for_publish=[],
    optional_fields=[],
    comboboxes=[
        ComboboxFacts(aria_name='Response Type *', required=False, default_option='HTML', note='Defaults to HTML on page load — already selected, no action needed unless a different response type is required. NOT virtualized.'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    publish_flow=[
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published?page_type=CustomPage&ptype=CustomPage&create=custom-page',
    draft_list_path='/posts/draft',
    note=(
        'Blank Canvas has NO Primary Category and NO Credits fields — the form only contains Title *, '
        'English Title (Permalink) *, a Response Type combobox (defaults to HTML, no action needed), '
        'and a Content code editor (optional). Fill Title + Permalink with safe_sequential_fill, then wait '
        'for expect(get_by_role("button", name="Publish")).to_be_enabled(timeout=15000) and click Publish. '
        'Direct-publish flow — no draft step. The published list is filtered by CustomPage type.'
    ),
)

CUSTOM_PAGE_CREATE = PageFacts(
    path='/posts/custom-page/create',
    title='Custom Content Template Page',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill'),
        FieldConstraint(field='English Title ( Permalink ) *', max=250, react_controlled=True, note="MUST use safe_sequential_fill — the async permalink-uniqueness check only reacts to real keystroke events, so plain fill() leaves Publish permanently disabled. Use a UNIQUE slug every run, e.g. f'qa-custom-{ts}'."),
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
    note=('CRITICAL — CONTENT-TYPE BLEED : the bare /posts/published with NO query '
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
          'BULK ACTIONS / SET AS FEATURED: ticking one or more row checkboxes '
          '(row.get_by_role("checkbox").click()) reveals a bulk-action bar above the table reading '
          '"<n> Selected" with plain buttons: "Send for Revision", "Set as Featured", "Distribute Post", '
          '"More Actions", "Clear". These are get_by_role("button", name=...) buttons — "More Actions" here is a '
          'BULK-BAR BUTTON, not a per-row control. There is NO per-row "Set as Featured" and NO per-row control '
          'named "More Actions": the row kebab (.published-action-dropdown) menu is only Edit Permalink / Duplicate '
          'Page / Push Notification / Distribute Post / Unpublish / Delete (no featuring). To feature a post: tick '
          'its checkbox, then page.get_by_role("button", name="Set as Featured").click(). '
          'CRITICAL — a post can only be featured if it HAS a featured image: clicking "Set as Featured" when any '
          'selected post lacks a featured image (or is Custom Content) opens a "Set as featured" dialog listing the '
          'excluded posts with [Cancel] / [Proceed without them], and proceeding features NOTHING. So the post you '
          'intend to feature MUST be created WITH a featured image (see Article Create facts). When the selected '
          'post HAS an image it is featured DIRECTLY with no dialog. '
          'SUCCESS INDICATOR: a featured row shows a title="Featured Post" badge in its Title cell — assert with '
          'expect(row.get_by_title("Featured Post")).to_be_visible(timeout=15000) (reload the filtered list first '
          'so the badge renders). Do NOT assert get_by_title("Featured") — the real title is "Featured Post". '
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

TEAM_MEMBERS = PageFacts(
    path='/team-members',
    title='Team Members',
    save_button='',
    after_save_url_pattern='/team-members',
    note=(
        'Search: get_by_role("textbox", name="Search here..."). '
        'Add member: get_by_role("button", name="Add Team Member"). '
        'Navigate directly with page.goto("/team-members").'
    ),
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
    note=(
        'ARTICLES CONTENT FILTER — when the plan includes an Articles filter row (the "+ Add Filter" step), '
        'the plan MUST specify ALL THREE sub-steps with concrete locators and named options — never leave any as '
        '"select the first available option" or the generator will omit that sub-step and Publish stays disabled. '
        'Required pattern: (1) Filter by Field — click the combobox and name the option (e.g. "Primary Category"); '
        '(2) Match Type — name the option (e.g. "Matches"); (3) Value — click get_by_role("combobox").last, then '
        'click page.locator(".ant-select-dropdown").last.locator(".ant-select-item-option").first. '
        'All three sub-steps on the SAME filter row; once all three are selected Publish becomes enabled.'
    ),
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
        FieldConstraint(field='Media URL *', note='NOT a field on the page itself — it lives inside the "Embed Media" dialog opened by clicking "Add Featured Video" (see NOTE). Declared here only so plan validation recognizes it as a legitimate fill label; the actual requirement is covered by "Featured Video *".'),
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
        'ORDERING RULE — ALWAYS add the Featured Video BEFORE filling Title or Permalink. '
        'Title\'s React-controlled Permalink auto-generation is debounced; filling Permalink immediately '
        'after Title fires that debounce mid-type during press_sequentially and corrupts the slug, leaving '
        'Publish permanently disabled with no visible error. Correct order: '
        '(1) click "Add Featured Video" → fill "Media URL *" → click "Submit", '
        '(2) safe_sequential_fill Title, (3) safe_sequential_fill Permalink, (4) select Primary Category. '
        'There is NO "Upload Video" button and NO native file chooser on this page — never write '
        'page.expect_file_chooser() or get_by_role("button", name="Upload Video") here, both time out. '
        'The "Featured Video *" field is filled by clicking button "Add Featured Video", which opens a dialog '
        'titled "Embed Media" containing a single required field "Media URL *" (placeholder "Enter video URL") '
        'plus "Cancel"/"Submit" buttons. Fill "Media URL *" with a real embeddable video URL then click "Submit" '
        'to attach it and close the dialog — video is added by URL embed only, there is no desktop-upload path. '
        'The unrelated "Upload ( 16:9 )" button under '
        '"Custom Thumbnail" uploads a static image thumbnail, not the video, and is optional.'
    ),
)

GALLERY_CREATE = PageFacts(
    path='/posts/gallery/create',
    title='Photo Gallery Create',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill, not safe_fill.'),
        FieldConstraint(field='English Title ( Permalink ) *', react_controlled=True, note="EXACT label — spaces inside parens are mandatory: 'English Title ( Permalink ) *'. MUST use safe_sequential_fill. Use a UNIQUE slug every run, e.g. f'qa-gallery-{ts}'."),
    ],
    required_for_publish=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill.'),
        FieldConstraint(field='English Title ( Permalink ) *', react_controlled=True, note='MUST use safe_sequential_fill. Unique slug every run.'),
        FieldConstraint(field='Primary Category', react_controlled=False, note='Combobox — pick first live .ant-select-item-option.'),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, virtualized=True, note='REQUIRED. Virtualized + per-publisher — pick the first live .ant-select-item-option; never hardcode a name.'),
        ComboboxFacts(aria_name='Credits *', required=True, note='REQUIRED but auto-fills with the logged-in user — no action needed.'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    published_list_path='/posts/published?page_type=Gallery&ptype=Gallery&create=gallery',
    note=(
        'The Permalink field ARIA name has spaces inside the parens: '
        '"English Title ( Permalink ) *" — not "(Permalink)". The generator has been observed to drop the spaces, '
        'producing a locator that matches nothing and times out. Always use the exact string above. '
        'DEBOUNCE RACE — MANDATORY page.wait_for_timeout(500) BETWEEN Title and Permalink: Title\'s '
        'React-controlled Permalink auto-generation is debounced. Unlike video/web-story (whose embed/image step '
        'runs before Title and absorbs the debounce), the gallery has NO pre-Title step, so Title and Permalink '
        'run cold and back-to-back. Filling Permalink immediately after Title fires the debounce mid-type, '
        'corrupts the slug, and leaves Publish permanently disabled with no error. Order: (1) safe_sequential_fill '
        'Title, (2) page.wait_for_timeout(500), (3) safe_sequential_fill Permalink, (4) select Primary Category. '
        'PUBLISH IS ENABLED BY: Title + Permalink + Primary Category ONLY. No image upload required. '
        'The "Add Slide" button adds an empty placeholder — it does NOT open a file chooser or media library. '
        'DO NOT include any "Add Slide", "Upload Media", file upload, or image steps in the test — '
        'they are not required and will leave Publish disabled if the upload flow is incomplete. '
        'EDIT FLOW (editing an already-published gallery): open the gallery from the published-list Edit icon '
        '(navigates to /posts/gallery/<id>), which reuses this create form\'s field labels BUT the save button is '
        "'Update' — NOT 'Publish' and NOT 'Save Changes'. The edit form\'s buttons are "
        "'Preview', 'Update', 'Save as Draft' — there is no 'Publish' on an already-published post.) Clicking "
        "'Update' saves and redirects back to the Gallery published list, so assert the edited row there afterward."
    ),
)

WEB_STORY_CREATE = PageFacts(
    path='/posts/web-story/create',
    title='Web Story Create',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note="React-controlled — MUST use safe_sequential_fill, not safe_fill. AMBIGUOUS after the image step: inserting the Web Story image adds a SLIDE with its own 'Title *' textbox (#slide_title), so the name 'Title *' then matches TWO textboxes. The POST title (#title) is the FIRST in DOM order — target it with page.get_by_role('textbox', name='Title *').first and pass that Locator to safe_sequential_fill (the helper accepts a Locator). exact=True does NOT disambiguate (both names are exactly 'Title *')."),
        FieldConstraint(field='English Title ( Permalink ) *', react_controlled=True, note="EXACT label — spaces inside parens are mandatory. MUST use safe_sequential_fill — the async permalink-uniqueness check only reacts to real keystrokes, so plain fill() leaves Publish permanently disabled. Use a UNIQUE slug every run, e.g. f'qa-web-story-{ts}'. Only ONE Permalink field exists (no slide collision)."),
    ],
    required_for_publish=[
        FieldConstraint(field='Web Story image *', note="REQUIRED. NOT a native file chooser and NOT the optional 'Upload ( Portrait/Landscape )' thumbnail buttons. Click the nameless drop-zone by its text — page.get_by_text('Upload your Web Story image').click() — which opens an in-DOM 'Media Library' dialog. SELECT an existing grid item via its CHECKBOX: page.get_by_role('dialog').get_by_role('checkbox').first.click() — do NOT use get_by_role('img').first (that is the upload drop-zone icon and opens a native file chooser). The 'Insert Media' button does NOT exist until an item is selected; after selecting, page.get_by_role('button', name='Insert Media').click() attaches the image and closes the dialog."),
        FieldConstraint(field='Primary Category', note='Combobox — pick first live .ant-select-item-option; never hardcode.'),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, virtualized=True, note='REQUIRED. Virtualized + per-publisher — click and snapshot, pick the first live .ant-select-item-option; never hardcode a name.'),
        ComboboxFacts(aria_name='Credits', required=True, note="Renders with an asterisk and aria-required=true, BUT auto-fills with the logged-in user and Publish ENABLES WITHOUT touching it. It is a COMBOBOX, not a textbox — NEVER safe_fill('Credits *', ...). Take NO action on Credits."),
        ComboboxFacts(aria_name='Additional Category'),
        ComboboxFacts(aria_name='Tags'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    publish_flow=[
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published?page_type=Web Story&ptype=Web Story&create=web-story',
    note=(
        'Web Story PUBLISHES DIRECTLY from this page. '
        'PUBLISH IS ENABLED BY EXACTLY: the Web Story image + Title * + English Title ( Permalink ) * + '
        'Primary Category. Credits is aria-required but auto-fills and is NOT a gate — do not fill it. '
        'ORDERING RULE — attach the image FIRST, before filling Title or Permalink: the image (media-library) '
        'interaction absorbs the Title→Permalink debounce. Correct order: (1) image via media library, '
        '(2) Title (use .first — see below), (3) Permalink, (4) Primary Category, (5) wait for Publish enabled, click. '
        'IMAGE STEP: page.get_by_text(\'Upload your Web Story image\').click() opens an in-DOM Media Library dialog '
        '(NOT a native chooser). Select an existing item by its CHECKBOX — '
        'page.get_by_role(\'dialog\').get_by_role(\'checkbox\').first.click() — NOT get_by_role(\'img\').first (the '
        'first <img> is the upload drop-zone icon → opens a native file chooser and the run stalls). The '
        '"Insert Media" button does NOT exist in the DOM until an item is selected, so selecting the checkbox is '
        'what makes it appear; then page.get_by_role(\'button\', name=\'Insert Media\').click() attaches the image. '
        'TITLE COLLISION: inserting the image adds a slide with its own \'Title *\' textbox, so after the image step '
        '\'Title *\' matches two textboxes — fill the POST title with '
        'page.get_by_role(\'textbox\', name=\'Title *\').first (exact=True does NOT help; both names are exactly '
        '\'Title *\'). Only Title collides — Permalink and Primary Category stay unique.'
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
        'After a successful upload the panel closes and the new file appears in the media grid.\n'
        'DELETE FLOW (grid, NOT a table): items are Ant cards `div.ant-card.media-listing-card` in an '
        'infinite-scroll grid `.media-listing-grid` -- there are NO <tr> elements, so page.locator("tr") / '
        'get_by_role("row") match NOTHING here. The filename is not rendered as card text (card text is '
        '"Download" + a storage hash + the alt text), so .filter(has_text=<filename>) fails. To delete: '
        'search by filename first. The magnifier search button is ICON-ONLY with no accessible name, so '
        'get_by_role("button", name="Search") matches nothing -- click it via the sanctioned CSS locator '
        '.pl-search-bar button (or press Enter in the box): '
        'box = get_by_role("textbox", name="Search by name, path, or alt text"); box.fill(name); '
        'page.locator(".pl-search-bar button").click(), which filters the grid server-side to the match; then '
        'card = page.locator(".media-listing-card").first; card.wait_for(state="visible", timeout=15000); '
        'card.click() to open its inline detail panel (NOT a modal), which has three NAMED buttons: '
        '"Edit Image Details", "Copy to clipboard", "Delete". Click the page-level named Delete button: '
        'page.get_by_role("button", name="Delete", exact=True).click() (resolves to exactly one match). '
        'Then confirm in the Ant modal (role="dialog", title "Delete Media", body "...delete 1 selected media..."): '
        'page.get_by_role("dialog").get_by_role("button", name="Delete").click(). Assert gone against the grid, '
        'never filename text: expect(page.locator(".media-listing-card")).to_have_count(0, timeout=15000). '
        '`.media-listing-grid` / `.media-listing-card` are sanctioned CSS locators for this page (like '
        'button.publisher-switcher) because the grid cards have no semantic locator; everything after card.click() '
        'is semantic.'
    ),
)

PAGE_FACTS = {
    '/posts/article/create': ARTICLE_CREATE,
    '/posts/custom-page/blank-page/create': BLANK_PAGE_CREATE,
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
    '/team-members': TEAM_MEMBERS,
    '/posts/entity/geographies/geography/create': GEOGRAPHY_CREATE,
    '/posts/video/create': VIDEO_CREATE,
    '/posts/gallery/create': GALLERY_CREATE,
    '/posts/published?page_type=Gallery&ptype=Gallery&create=gallery': PUBLISHED_LIST,
    '/posts/web-story/create': WEB_STORY_CREATE,
    '/posts/published?page_type=Web Story&ptype=Web Story&create=web-story': PUBLISHED_LIST,
    '/posts/live-blog/create': LIVE_BLOG_CREATE,
}

CUSTOM_COMPONENT_LIST = PageFacts(
    path='/configurations/content-type-builder/custom-component',
    title='Custom Components',
    save_button='Save',
    launch_button='Create New Component',
    note=(
        'URL confirmed live 2026-07-16. Navigate directly — do NOT guess from /configurations.\n'
        'CREATE FLOW — 2 steps:\n'
        'STEP 1: Click button "Create New Component" → dialog "Create New Component" opens.\n'
        '  The dialog has EXACTLY these fields (verified live 2026-07-21) — do NOT add any others:\n'
        '    Required: get_by_role("textbox", name="Display Name *") — React-controlled, safe_sequential_fill.\n'
        '    Optional: get_by_role("textbox", name="Description"); an "Avatar" upload button (skip it).\n'
        '  There is NO "Template" field/dropdown and NO other required fields here. Do NOT invent a\n'
        '  "Template" step or a "fill all other required fields" step from the test title — the ONLY\n'
        '  field to fill in this dialog is "Display Name *".\n'
        '  Click button "Continue" → URL becomes /configurations/content-type-builder/custom-component/<id>?flow=1.\n'
        'STEP 2 — field builder (URL contains ?flow=1):\n'
        '  Dialog "Add a field in your Content Type" auto-opens with field type tile buttons.\n'
        '  Types: Text, Media, Email, Rich Text, Date And Time, Numbers, List, Boolean, JSON,\n'
        '    Relation, Dynamic List, Links, Embed, Component.\n'
        '  Per field: (a) click type tile, (b) safe_sequential_fill Display Name * for field name,\n'
        '  (c) click "Add Another Field" if more fields remain, or "Save" (in dialog) on the last.\n'
        '  After all fields: click button "Save" on the main page header.\n'
        'LIST columns: Name, Fields, Updated By, Created At, Updated At, Actions.\n'
        'Row actions: DIRECT buttons (no kebab) — edit pencil, "Duplicate", "Delete".\n'
        'Row locator: page.locator("tr").filter(has_text=component_name).first\n'
        'NOTE: "Display Name *" appears in two separate contexts:\n'
        '  Step 1 dialog → component name. Step 2 field config dialog → field name.\n'
        'These are different inputs in different dialogs.'
    ),
)
PAGE_FACTS['/configurations/content-type-builder/custom-component'] = CUSTOM_COMPONENT_LIST

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
    '/settings', '/home', '/login',
    '/content-distribution', '/analytics', '/v2/',
] + CTB_KNOWN_PATH_PREFIXES


def detect_intent(prompt):
    lower = prompt.lower()

    page = None
    if re.search(r'blank.?(canvas|page)', lower):
        page = BLANK_PAGE_CREATE
    elif re.search(r'custom.?(content|page)', lower):
        page = CUSTOM_PAGE_CREATE
    elif re.search(r'web\s*stor', lower):
        page = WEB_STORY_CREATE
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


def matched_pages_for_prompt(prompt):
    """Return the list of PageFacts objects a prompt references (same detection as
    facts_for_all_mentioned_pages, but returns the objects rather than formatted text so
    callers can read .path/.title). Order = detection order."""
    lower = prompt.lower()
    matched = []
    seen = set()

    def push(page):
        if page.path not in seen:
            seen.add(page.path)
            matched.append(page)

    is_geography_filter_flow = bool(re.search(r'geograph', lower) and re.search(r'\bfilter\b', lower))

    if re.search(r'custom.?component|content.?type.?builder', lower):
        push(CUSTOM_COMPONENT_LIST)
    if re.search(r'blank.?(canvas|page)', lower):
        push(BLANK_PAGE_CREATE)
    elif re.search(r'custom.?(content|page)', lower):
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

    # URL-path fallback: keyword regexes above miss hyphenated forms ("web-story", "live-blog")
    # and Gallery (no keyword regex). Every plan with page.goto() has the real path — detection
    # by path is unambiguous. Skip query-string variants and PUBLISHED_LIST / DRAFT_LIST
    # (context-sensitive, gated on verb presence below to avoid false injections).
    _url_path_skip = {PUBLISHED_LIST.path, DRAFT_LIST.path}
    for _path, _page_facts in PAGE_FACTS.items():
        if '?' not in _path and _path not in _url_path_skip and _path in lower:
            push(_page_facts)

    has_published_target = any(p.published_list_path for p in matched)
    # "draft"/"discard" inject Draft list facts; "publish"/"delete"/"edit" inject Published list
    # facts — editing a published item requires finding it by row there first.
    if not is_geography_filter_flow and re.search(r'\bdraft\b|save.*as.*draft|discard', lower):
        push(DRAFT_LIST)
    if has_published_target and re.search(r'publish|delet|\bedit\b|topmost|latest|rename|update', lower):
        push(PUBLISHED_LIST)

    return matched


def facts_for_all_mentioned_pages(prompt):
    matched = matched_pages_for_prompt(prompt)
    if not matched:
        return ''
    return '\n\n'.join(format_page_facts(p) for p in matched)
