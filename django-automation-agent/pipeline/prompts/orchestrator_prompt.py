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
    '- PUBLISH flows are multi-stage: save-as-draft -> navigate to draft list -> click row Edit -> click Publish. '
    'Decompose "publish X" into these concrete steps. Do NOT write a single "publish the content" step.\n'
    '- When a publish flow targets a page with character-minimum fields (Summary, Meta Description), '
    'include explicit steps to fill each one with content of the required length. '
    'The "Required for PUBLISH" section in DASHBOARD KNOWLEDGE lists exact minimums per page.'
)


def build_orchestrator_user_message(user_prompt, url):
    facts = facts_for_prompt(user_prompt)
    facts_section = (
        f'\n\nDASHBOARD KNOWLEDGE (verified live — use as ground truth, do not invent):\n{facts}\n'
        if facts else ''
    )
    return f"""URL: {url}
Task: {user_prompt}
{facts_section}
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
