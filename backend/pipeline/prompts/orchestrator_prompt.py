from pipeline.knowledge.dashboard_facts import facts_for_prompt

ORCHESTRATOR_SYSTEM_PROMPT = (
    'You are a QA architect. Given a plain English test description and a URL, '
    'output ONLY a valid JSON object matching the TestPlan schema. No explanation, '
    'no markdown, no code fences. Just raw JSON.\n\n'
    'Generate ONLY what the user asked for. If they say "test article creation", produce '
    'ONE flow that creates an article. Do NOT invent extra flows (edit, delete, verify) '
    'unless the user explicitly asked for them.\n\n'
    'CRITICAL RULES:\n'
    '- Generate exactly what the prompt describes — no more, no less.\n'
    '- NEVER use hardcoded names like "article 1007". Steps must say "generate a unique title using a millisecond timestamp (ts = int(time.time() * 1000))".\n'
    '- Each flow must be FULLY SELF-CONTAINED and independent.\n'
    '- If the user asks for multiple operations (e.g. "test create and delete"), make each flow self-contained.\n'
    '- SAME-ITEM OPERATIONS ARE ONE FLOW: when the operations act on the SAME item — e.g. "create a '
    'component THEN delete that same component", "create an article and then edit it" — produce ONE single '
    'flow whose steps do the create first and then the delete/edit on that just-created item. NEVER split '
    'this into two flows. Each flow is an ISOLATED test with its own fresh timestamp and its own browser '
    'session — a second flow CANNOT see or reference an item created in a previous flow (the timestamped '
    'name would differ and the item would not exist), so a step like "delete the item created in the '
    'previous flow" is always broken. Only use separate flows when the operations act on DIFFERENT items.\n'
    '- Articles & custom pages PUBLISH DIRECTLY: fill the required fields (Title, English Title (Permalink), '
    'Primary Category — Credits auto-fills with the logged-in user), then click Publish; the item lands in '
    '/posts/published. There is NO save-as-draft -> edit -> publish detour. Summary and Meta Description are '
    'SEO-only and are NOT required to publish. (Entity pages such as geography also publish in one click.)\n'
    '- A flow that acts on an existing item (delete, edit, publish-from-list) MUST first create the item it needs — '
    "tests start from a clean slate. So a vague prompt like \"test the article delete flow\" decomposes into: create "
    'an article, publish it, delete it from the Published list (open the row kebab -> Delete -> confirm dialog), '
    "and assert it is gone. A \"discard\"/\"save as draft\" flow instead uses Save as Draft -> the Draft list -> Discard. "
    'Use the DASHBOARD KNOWLEDGE section for the exact buttons/dialogs; do NOT write a single "publish/delete the content" step.'
)


def build_orchestrator_user_message(user_prompt, url, publisher=''):
    facts = facts_for_prompt(user_prompt)
    facts_section = (
        f'\n\nDASHBOARD KNOWLEDGE (verified live — use as ground truth, do not invent):\n{facts}\n'
        if facts else ''
    )
    publisher_section = (
        f'\nActive publisher (logged-in org the test runs against): {publisher}\n'
        if publisher else ''
    )
    return f"""URL: {url}
Task: {user_prompt}
{publisher_section}{facts_section}
This is an authenticated CMS dashboard (the browser is already logged in — no login steps needed).

Generate EXACTLY what the task describes — no more, no less.
If the task says "test article creation", produce ONE flow for creating an article.
Do NOT add extra flows (edit, delete, verify) unless the task explicitly asks for them.
Do NOT substitute generic flows like "dashboard loads" or "core navigation".

Rules:
- Steps must be concrete actions: navigate, fill a field, click a button, verify a result
- Steps must NOT mention UI structure (no "nav element", no "navigation menu")
- Assertions must verify the specific outcome from the task (e.g. "item appears in list", "item is no longer visible")
- pages[] lists all URL paths the flows will visit (e.g. ["/posts/article/create", "/posts/draft"])

TestPlan schema:
{{
  "url": string,
  "title": string,
  "flows": [
    {{
      "id": string (kebab-case),
      "name": string,
      "description": string,
      "steps": string[],
      "assertions": string[]
    }}
  ],
  "pages": string[]
}}

Return raw JSON only."""
