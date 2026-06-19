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
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill, not safe_fill'),
        FieldConstraint(field='English Title ( Permalink ) *', note="fill() works; common slug format: f'qa-{ts}'"),
    ],
    required_for_publish=[
        FieldConstraint(field='Summary', min=140, note='JS-enforced minimum 140 chars to enable Publish on the edit page'),
        FieldConstraint(field='Meta Description', min=140, max=170, note='JS-enforced range 140–170 chars to enable Publish on the edit page'),
    ],
    optional_fields=[
        FieldConstraint(field='Banner Description'),
        FieldConstraint(field='Focus Keyphrase', max=60),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, note='Options vary per publisher and change over time. Planner MUST click this combobox and snapshot to discover live options — never assume names.'),
        ComboboxFacts(aria_name='Tags'),
        ComboboxFacts(aria_name='Credits'),
        ComboboxFacts(aria_name='Additional Category'),
    ],
    save_button='Save as Draft',
    after_save_url_pattern='/posts/draft',
    publish_flow=[
        PublishStep(kind='click_button', button='Save as Draft'),
        PublishStep(kind='expect_url', pattern='/posts/draft'),
        PublishStep(kind='click_row_action', row_matcher='title', action='Edit'),
        PublishStep(kind='expect_url', pattern=r'/posts/article/\d+'),
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published',
    draft_list_path='/posts/draft',
)

CUSTOM_PAGE_CREATE = PageFacts(
    path='/posts/custom-page/create',
    title='Custom Content Template Page',
    required_for_draft=[
        FieldConstraint(field='Title *', react_controlled=True, note='React-controlled — MUST use safe_sequential_fill'),
        FieldConstraint(field='English Title ( Permalink ) *', max=250),
    ],
    required_for_publish=[
        FieldConstraint(field='Summary', min=140, note='JS-enforced minimum 140 chars to enable Publish on the edit page'),
        FieldConstraint(field='Meta Description', min=140, max=170, note='JS-enforced range 140–170 chars to enable Publish on the edit page'),
    ],
    optional_fields=[
        FieldConstraint(field='Banner Description'),
    ],
    comboboxes=[
        ComboboxFacts(aria_name='Primary Category', required=True, note='Options vary per publisher and change over time. Planner MUST click and snapshot to discover live options.'),
    ],
    save_button='Save as Draft',
    after_save_url_pattern='/posts/draft',
    publish_flow=[
        PublishStep(kind='click_button', button='Save as Draft'),
        PublishStep(kind='expect_url', pattern='/posts/draft'),
        PublishStep(kind='click_row_action', row_matcher='title', action='Edit'),
        PublishStep(kind='expect_url', pattern=r'/posts/custom-page/\d+'),
        PublishStep(kind='click_button', button='Publish'),
        PublishStep(kind='expect_url', pattern='/posts/published'),
    ],
    published_list_path='/posts/published',
    draft_list_path='/posts/draft',
)

DRAFT_LIST = PageFacts(
    path='/posts/draft',
    title='Draft List',
    save_button='',
    after_save_url_pattern='/posts/draft',
    note='Table header: "Title Content Type Created By Updated By Timeline Actions". Row actions: link "Edit", link "Preview", button "Discard". Discard dialog: get_by_role("dialog", name="Discard Article") with button "Discard".',
)

PUBLISHED_LIST = PageFacts(
    path='/posts/published',
    title='Published List',
    save_button='',
    after_save_url_pattern='/posts/published',
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
        lines.append('- PUBLISH flow (multi-stage — publish is NOT one click on the create page):')
        for i, step in enumerate(facts.publish_flow, 1):
            if step.kind == 'click_button':
                lines.append(f'    {i}. Click button "{step.button}"')
            elif step.kind == 'expect_url':
                escaped = step.pattern.replace('/', '\\/')
                lines.append(f'    {i}. Expect URL /{escaped}/')
            elif step.kind == 'click_row_action':
                lines.append(f'    {i}. In the row matching the {step.row_matcher}, click "{step.action}"')
            elif step.kind == 'navigate':
                lines.append(f'    {i}. Navigate to {step.path_pattern}')
    return '\n'.join(lines)


def facts_for_prompt(prompt):
    intent = detect_intent(prompt)
    pages = []

    if intent:
        pages.append(intent['page'])
        if intent['verb'] in ('publish', 'draft'):
            draft_path = intent['page'].draft_list_path
            if draft_path and draft_path in PAGE_FACTS:
                pages.append(PAGE_FACTS[draft_path])
        if intent['verb'] == 'publish':
            pub_path = intent['page'].published_list_path
            if pub_path and pub_path in PAGE_FACTS:
                pages.append(PAGE_FACTS[pub_path])
        if intent['verb'] in ('discard', 'delete'):
            draft_path = intent['page'].draft_list_path
            if draft_path and draft_path in PAGE_FACTS:
                pages.append(PAGE_FACTS[draft_path])

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

    if not is_geography_filter_flow and re.search(r'draft|save.*as.*draft|publish', lower):
        push(DRAFT_LIST)

    if not matched:
        return ''
    return '\n\n'.join(format_page_facts(p) for p in matched)
