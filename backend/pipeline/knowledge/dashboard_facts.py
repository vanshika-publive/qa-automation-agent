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
        ComboboxFacts(aria_name='Primary Category', required=True, note='REQUIRED. Virtualized + per-publisher — click and snapshot, pick the first live .ant-select-item-option; never hardcode a name.'),
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
    published_list_path='/posts/published',
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
        ComboboxFacts(aria_name='Primary Category', required=True, note='REQUIRED. Virtualized + per-publisher — click and snapshot, pick the first live option; never hardcode.'),
        ComboboxFacts(aria_name='Credits', required=True, note='REQUIRED but auto-filled with the logged-in user — no action needed.'),
    ],
    save_button='Publish',
    after_save_url_pattern='/posts/published',
    publish_flow=[
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published',
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
          'CRITICAL — Ant Design <tr> elements have NO accessible name. NEVER use get_by_role("row", name=...). '
          'Find the row with: row = page.locator("tr").filter(has_text=title) then row.wait_for(state="visible", timeout=15000). '
          'Discard: row.get_by_role("button", name="Discard").click() -> '
          'page.get_by_role("dialog").get_by_role("button", name="Discard").click(). '
          'NEVER use get_by_role("dialog", name="Discard Article") — dialog title varies by content type.'),
)

PUBLISHED_LIST = PageFacts(
    path='/posts/published',
    title='Published List',
    save_button='',
    after_save_url_pattern='/posts/published',
    note=('List of published posts (verified live on OdishaTv - Khabar, 2026-06-22). To see only articles use '
          '/posts/published?page_type=Article&ptype=Article&create=article. Columns: Title, Categories, Credits, '
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
          'NOTE: "Unpublish" is a DIFFERENT menu item (sends back to draft), NOT Delete.'),
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
          'the Posts Published list and does not exist on this page.'),
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

PAGE_FACTS = {
    '/posts/article/create': ARTICLE_CREATE,
    '/posts/custom-page/create': CUSTOM_PAGE_CREATE,
    '/posts/draft': DRAFT_LIST,
    '/posts/published': PUBLISHED_LIST,
    '/tags/create': TAG_CREATE,
    '/tags': TAGS_LIST,
    '/categories/new': CATEGORY_CREATE,
    '/categories': CATEGORIES_LIST,
    '/posts/entity/geographies/geography/create': GEOGRAPHY_CREATE,
}

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
        # "save as draft" and "discard" act on the Draft list; "publish" and "delete"
        # act on the Published list (articles publish directly, then delete from there).
        if verb in ('draft', 'discard'):
            draft_path = intent['page'].draft_list_path
            if draft_path and draft_path in PAGE_FACTS:
                pages.append(PAGE_FACTS[draft_path])
        if verb in ('publish', 'delete'):
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
    if re.search(r'\btag\b|\btags\b', lower):
        push(TAG_CREATE)
    if re.search(r'categor', lower):
        push(CATEGORY_CREATE)
    if re.search(r'geograph', lower):
        push(GEOGRAPHY_CREATE)

    article_or_custom = any(
        p.path in ('/posts/article/create', '/posts/custom-page/create') for p in matched
    )
    # "save as draft" / "discard" surface the Draft list; article/custom-page "publish" and
    # "delete" both go through the Published list (direct publish, then delete from there).
    if not is_geography_filter_flow and re.search(r'\bdraft\b|save.*as.*draft|discard', lower):
        push(DRAFT_LIST)
    if article_or_custom and re.search(r'publish|delet', lower):
        push(PUBLISHED_LIST)

    if not matched:
        return ''
    return '\n\n'.join(format_page_facts(p) for p in matched)
