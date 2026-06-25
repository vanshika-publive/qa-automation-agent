# QA Automation Agent — Codebase Overview

> Generated as a standalone briefing document so an LLM with no repo access (e.g. Claude
> on claude.ai) can understand this project well enough to write further documentation
> about it. Everything below was verified directly against the source in this repo.

GitHub: `ThePublive/qa-automation-agent` (private). Repo root directory name on disk:
`automation-agent-2`.

---

## 1. What this project is

An internal QA tool for **PubLive** (also branded "ThePublive"), a multi-tenant
publishing/CMS dashboard product (`betadashboard.thepublive.com/v2`,
`dashboard.thepublive.com/v2`). Each "publisher" (e.g. *OdishaTv - Khabar*, *Crictoday*)
is a tenant org with its own categories, tags, reporters, etc.

The tool lets a QA user type a **plain-English test description** ("test creating an
article and verify it appears in the published list") plus a target URL. An AI pipeline
then:

1. Turns that prompt into a structured test plan (LLM).
2. **Browses the live dashboard** with a real headless browser to discover the actual
   UI (URLs, field labels, button names, dropdown options) — because the dashboard's
   structure is undocumented, per-publisher, and changes over time.
3. Writes a runnable **Playwright + pytest** test file in Python, grounded in what it
   actually observed.
4. Executes that test and reports pass/fail with HTML + JSON reports.

A React dashboard (the "Test Manager" UI) lets a QA user organize tests into
collections, trigger runs, watch the 4-stage pipeline live, browse/edit generated test
code, and compare past executions.

This is a **test-generation meta-tool**: the "AI-Powered Automation" it builds is itself
QA automation for a separate product (PubLive). It is not customer-facing.

---

## 2. Tech stack

| Layer | Stack |
|---|---|
| Frontend | React 18 + TypeScript + Vite, TanStack React Query v5, react-router-dom v6, Tailwind CSS, lucide-react / Material Symbols icons |
| Backend API | Django 5 + Django REST Framework, django-cors-headers, PostgreSQL (psycopg2) |
| AI pipeline | OpenAI API (`gpt-4o`, via `openai` Python SDK), `@playwright/mcp` (Playwright's Model Context Protocol server, Node) bridged into Python over JSON-RPC/stdio |
| Generated tests | Python, `pytest` + `pytest-playwright` + `pytest-json-report` + `pytest-html` + `pytest-timeout` |
| Observability | New Relic Python agent (APM) |
| Package managers | `pip`/`requirements.txt` (backend Python), `npm` (backend Node deps for the MCP CLI, and separately the frontend) |

Backend was **migrated from a Node/TypeScript implementation to Django/Python**
(commit "Add Django/Python automation-agent (TS→Python migration)"); the TS version no
longer exists in this repo. `backend/package.json` is *not* the app — it only pulls in
`@playwright/mcp` and `@playwright/test` as Node-side dependencies the Python pipeline
shells out to.

---

## 3. Repository layout

```
automation-agent-2/
├── CLAUDE.md              # team coding-standard doc (see §8.1) — canonical ref: production-code-docs.vercel.app
├── README.md              # just the project name, no content
├── frontend/              # React + Vite + TS dashboard ("Test Manager" UI)
│   └── src/
│       ├── api/client.ts        # fetch wrapper
│       ├── services/            # Layer 1 — pure API calls
│       ├── hooks/               # Layer 2 — React Query + derived state
│       ├── pages/                # Layer 3 — route components
│       ├── components/           # shared/modal/slide-over components
│       ├── utils/                 # formatters, status-color maps
│       ├── constants/            # editor colors, layout sizes, SSE URL builder
│       └── types.ts              # shared TS types
├── backend/                # Django + DRF API server + AI pipeline
│   ├── config/             # Django project (settings, urls, wsgi/asgi)
│   ├── core/               # CRUD app: Collection/Test/Environment/Execution models + views
│   ├── pipeline/           # the AI agent pipeline (orchestrator/planner/generator/runner) — NO db models
│   ├── utils/              # tiny shared helpers (slug, json, markdown, errors)
│   ├── capture_session.py  # one-off script: manually clear MFA, save reusable browser session
│   ├── manage.py
│   ├── requirements.txt
│   ├── package.json        # Node deps for @playwright/mcp CLI only
│   └── newrelic.ini
└── data/                    # runtime artifacts, gitignored except .gitkeep-style dirs
    ├── .auth/session.json   # the single stored dashboard login session (storage_state)
    ├── specs/<collection-slug>/<test-id>/plan.md      # AI-authored markdown test plan
    ├── tests/<collection-slug>/test_<name>.py         # generated Playwright spec files
    │   ├── conftest.py      # pytest fixtures (session reuse, browser args, timeouts)
    │   ├── helpers.py       # safe_fill / safe_sequential_fill / DOM-limit readers
    │   └── pytest.ini
    └── reports/<collection-slug>/<execution-id>/      # results.json + html/index.html per run
```

`backend/config/settings.py` defines two important root paths:
- `BACKEND_ROOT` — the `backend/` dir (where `node_modules/@playwright/mcp` lives).
- `PLAYWRIGHT_PROJECT_ROOT` — the `data/` dir (overridable via env var; where all
  generated/runtime artifacts live). Both are passed into subprocesses (pytest runs,
  the MCP CLI) as env vars so they don't need to guess paths.

---

## 4. Domain model (Postgres, via Django ORM)

All tables use **soft delete** (`deleted_at` timestamp column; default manager
`SoftDeleteManager` filters it out, `all_objects` manager sees everything including
soft-deleted rows — used internally by the pipeline so a run isn't blocked by a delete
race). IDs are `TextField` UUIDs (`default=uuid.uuid4`), not Django's integer PKs.
Timestamps are stored as ISO-8601 strings, not native datetimes.

```
Environment                 Collection
  id, name, base_url           id, name, created_at
  login_email, login_password  └─< Test (FK collection, RESTRICT)
  publisher  ←─ detected from        id, name, prompt, status ('active'|'deleted')
               session, never        environment_ids (JSON array, stored as text)
               user-set              └─< Execution (FK test + FK environment, RESTRICT)
  is_active, description                id, status, started_at/completed_at, duration_ms
                                          pass_count/fail_count/total_count, report_dir
                                          └─< ExecutionStep (FK execution, RESTRICT)
                                                id, step_name ('orchestrator'|'planner'
                                                |'generator'|'runner'), status, log,
                                                started_at/completed_at
```

Key relationships / business rules:
- A **Test** belongs to one **Collection** and carries the user's free-text `prompt` —
  this prompt is what the orchestrator stage consumes.
- A **Test** also stores `environment_ids` (which environments it's allowed to run
  against) but the actual run always takes an explicit `environmentId` argument.
- An **Execution** is one pipeline run of one Test against one Environment. Its 4
  `ExecutionStep` rows correspond 1:1 to the pipeline stages.
- `Execution.report_dir` (`"<collection-slug>/<execution-id>"`) is the join key into the
  `data/reports/` tree on disk; pass/fail counts and per-test results are *not* fully
  duplicated into Postgres — `results.json` on disk is the source of truth for
  per-test detail (parsed on demand by `core/views/executions.py`).
- **Environment.publisher** is never set by the user — `pipeline/publisher.py` reads it
  live from the dashboard's own `GET /api/user/` (using the stored session cookies) and
  the backend caches the detected name onto the row. The system deliberately **never
  switches publisher**; it only reports which one the current session is on.

`backend/core/apps.py` (`CoreConfig.ready()`) runs on every Django startup:
marks any `Execution` stuck in `status='running'` as `'failed'` (crash recovery for
ungraceful restarts), and seeds two default `Environment` rows ("Beta" →
`betadashboard.thepublive.com/v2`, "Production" → `dashboard.thepublive.com/v2`) if the
table is empty.

There is no real Django test suite — `core/tests.py` and `pipeline/tests.py` are both
just the unmodified `./manage.py startapp` boilerplate.

---

## 5. Backend REST API

Base path `/api/` (`backend/config/urls.py` → `core/urls.py`). All responses are
wrapped in a DRF custom renderer (`core/renderers.py: EnvelopeRenderer`) into a uniform
envelope: **`{ data: T | null, error: string | null }`**, plus `pagination` for list
endpoints. A matching custom exception handler (`core/exceptions.py`) wraps DRF's
default error responses into the same envelope. There is no authentication —
`DEFAULT_PERMISSION_CLASSES = [AllowAny]` (internal tool, not exposed publicly).

| Method & Path | Purpose |
|---|---|
| `GET /health` | liveness check |
| `GET/POST /collections` | list (with live test counts) / create |
| `PATCH/DELETE /collections/<id>` | rename / soft-delete (cascades soft-delete to its Tests) |
| `GET/POST /collections/<id>/tests` | list tests in a collection (each annotated with detected `specFile`/`planFile` on disk) / create a test |
| `PUT/DELETE /tests/<id>` | update test (name/prompt/status/collection/environments; `duplicate: true` also clones it) / soft-delete |
| `GET /collections/<id>/specs` | list generated `.py` spec files for a collection, sorted by mtime |
| `GET /specs/view?file=...` | read raw content of a spec file |
| `DELETE /specs?file=...` | delete a spec file from disk |
| `GET/PUT /tests/<id>/spec` | fetch / hand-edit a test's generated spec source |
| `POST /tests/<id>/run-spec` | re-run an existing spec file (skips orchestrator/planner/generator) |
| `GET/POST /environments` | list / create an Environment (validates name/baseUrl/loginEmail/loginPassword) |
| `PUT/DELETE /environments/<id>` | update (password optional — blank keeps existing) / soft-delete |
| `GET /environments/active-publisher` | live-detects the publisher of the stored session via `/api/user/` |
| `GET /executions` | paginated, filterable (`testId`, `collection_id`, `status`, `from`, `to`) list, includes a window-function `runNumber` per test |
| `GET /executions/<id>` | full detail incl. its `steps[]` and a computed `runNumber` |
| `DELETE /executions/<id>` | soft-delete (rejected with 409 while `status='running'`) |
| `GET /executions/<id>/steps` | per-test pytest results parsed live from `results.json` |
| `GET /executions/<id>/tests` | same, flattened test list with `pending` flag while running |
| `GET /executions/<id>/files` | returns the generated spec source + plan.md content for this run |
| `GET /executions/<id>/stream` | **Server-Sent Events** — polls DB every 0.8s and streams `{execution, steps}` JSON until the run leaves `'running'` |
| `POST /executions/tests/<test_id>/run` | **kicks off the full 4-stage pipeline** in a background thread, returns `{executionId}` immediately (202) |
| `POST /collections/<id>/run-all-specs` | runs every existing spec file in a collection as one Execution |
| `GET /reports/<path>` | static file serving of `data/reports/` (HTML report viewer), wired directly in `config/urls.py`, not under `/api` |

Both "run" endpoints spawn a **daemon thread** that calls `django.setup()` then
`pipeline.run_pipeline.run_pipeline(...)` / `run_spec_file(...)` — there's no task
queue (no Celery/RQ); concurrency is just raw Python threads, and progress is observed
by the frontend via polling/SSE against the DB rows the thread writes to.

---

## 6. The AI test-generation pipeline (`backend/pipeline/`)

This is the core IP of the project. Entry point: `pipeline/run_pipeline.py:run_pipeline()`,
called from a background thread per Execution. It runs four stages in order, writing one
`ExecutionStep` row per stage (`orchestrator → planner → generator → runner`), capturing
each stage's stdout/stderr into that step's `log` via a `LogCapture`/`_TeeWriter`
redirect. A stage failure aborts the remaining stages but still finalizes the Execution.

Before any stage: it resolves the Test's prompt + Collection slug, refreshes the stored
browser session (`login_helper.refresh_session`), detects the **active publisher** from
that session (`pipeline/publisher.py`), and stashes both as **thread-local runtime
credentials** (`pipeline/credential_manager.py`) so every downstream module can call
`get_credentials()`/`get_publisher()` without threading parameters through every call.

### 6.1 Stage 1 — Orchestrator (`pipeline/orchestrator.py`)

Pure LLM call, no browser. Sends the user's free-text prompt + URL + detected publisher
+ any matching "dashboard knowledge" facts (see §6.7) to `gpt-4o` with
`response_format: json_object`, asking for a structured `TestPlan`:

```json
{ "url": str, "title": str, "pages": [str],
  "flows": [ { "id": str, "name": str, "description": str, "steps": [str], "assertions": [str] } ] }
```

The system prompt (`pipeline/prompts/orchestrator_prompt.py`) hard-codes important
product knowledge so the LLM doesn't have to infer it every time: articles/custom
pages/entity-pages **publish directly** (no draft→edit→publish detour), every test
flow must be self-contained and use a millisecond timestamp for uniqueness, and a flow
that mutates an existing item must first create that item itself.

The parsed plan is then run through `expand_plan_with_preconditions()`, which
deterministically inserts missing required-field steps (e.g. a forgotten "fill the
permalink field" step before a "publish" step) as a belt-and-suspenders fix — using
`pipeline/knowledge/dashboard_facts.py`'s `detect_intent`/`expand_preconditions`, not the
LLM.

### 6.2 Stage 2 — Planner agent (`pipeline/planner_agent.py`)

An **agentic loop** (max 20 iterations, `gpt-4o`, `tool_choice='required'`) that drives a
real headless browser through `pipeline/mcp_bridge.py` to *discover* the dashboard
rather than guess at it. Tools available: 2 custom (`planner_setup_page`,
`planner_save_plan`) plus a filtered subset of Playwright MCP tools
(`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_hover`,
`browser_wait_for` — **read-only**, no typing/filling; the planner's job is to map the
UI, not operate it).

Flow: navigate to the target URL → repeatedly snapshot/click to find the real feature
page → call `planner_save_plan` with a markdown plan. Every saved plan is validated by
`pipeline/transforms/plan_validator.py::validate_plan_content` before being accepted;
rejections (unverified URLs, missing required fields, hallucinated dropdown option
text, wrong save-button for the page type, fields that don't exist on the visited page,
unresolved placeholder text) feed back into the conversation as a structured error so
the model retries. Login redirects mid-navigation are treated as "feature unavailable
for this publisher," not as an auth bug. On success it writes:
- `data/specs/<collection-slug>/<test-id>/plan.md` — the markdown plan (flows →
  scenarios → numbered steps → expected assertions, see example in §9)
- a sibling `plan-snapshots.json` — every ARIA snapshot seen this session, keyed by URL,
  reused as locator ground-truth by the next stage.

### 6.3 Stage 3 — Generator agent (`pipeline/generator_agent.py`)

Parses `plan.md` into `Scenario` objects (`pipeline/transforms/plan_parser.py`, one per
`### Scenario:` block) and, **for each scenario independently**, runs another agentic
loop (max 20 iterations, `gpt-4o`, temperature 0) that writes one Python
pytest-playwright file. Tools: `generator_setup_page`, `generator_read_log`,
`generator_write_test` (the only way the code is persisted — text replies are
discarded, though a regex-based salvage path recovers code accidentally returned as
prose), `generator_discover_limits` (read-only DOM inspection of `maxLength`/
`required`/etc., used instead of live form interaction so the agent never triggers
React `onChange` side effects by accident), plus read-only `browser_navigate`/
`browser_snapshot`.

Every `generator_write_test` call is gated by
`pipeline/transforms/spec_validator.py` (semantic rules — missing Summary/Meta
Description before a publish action, missing timeout on `to_have_url`, forbidden
`page.locator("text=...")`/jQuery selectors/raw `document.querySelector`, wrong
save-button usage, fields not present in dashboard-facts for the visited page, dropped
plan steps) and `validate_spec_data_uniqueness` (rejects hardcoded test-data strings
not derived from `time.time()`). Rejected code is *not* written — the model gets the
rejection reason back as a tool result and must retry.

Accepted code is then passed through `pipeline/transforms/spec_sanitizer.py`, a
deterministic regex-based cleanup pass that runs regardless of what the LLM produced:
`to_have_url('exact')` → regex form, absolute dashboard URLs in `page.goto()` → relative
paths, `get_by_role('option', ...)` → `get_by_title(..., exact=True).last` (Ant Design's
real DOM shape), `get_by_label()` → `get_by_role('textbox', ...)` (this dashboard has no
real `<label>` elements), adds missing `timeout=15000` on visibility/enabled
assertions, injects `ts = int(time.time()*1000)` and missing imports, and rewrites raw
`press_sequentially` sequences into the `safe_sequential_fill` helper call. Output path:
`data/tests/<collection-slug>/test_<flow-slug>-<scenario-slug>.py`. If a spec file for a
scenario already exists on disk, generation is skipped (idempotent re-runs).

After writing, `run_pipeline.py` also does a final **Python `compile()` syntax check**
on every generated file before handing off to the runner.

### 6.4 Stage 4 — Runner (`pipeline/runner.py`)

No LLM involved. Shells out to `pytest` (`subprocess.Popen`, own process group via
`start_new_session=True` so the whole tree — pytest + chromium + ffmpeg — can be
SIGKILLed on timeout without orphans) with `--json-report`, `--html`
(self-contained), `--timeout=30` per test, and an outer 4-minute hard kill
(`PIPELINE_KILL_TIMEOUT_MS`). Dashboard credentials/URL/publisher are passed down purely
via env vars (`DASHBOARD_URL`/`EMAIL`/`PASSWORD`/`PUBLISHER`) — the actual `data/tests/`
fixtures (`conftest.py`) pick those up. Parses `results.json` (the
`pytest-json-report` schema: `summary{passed,failed,skipped,total}`, `tests[]` with
`nodeid`/`outcome`/`call.longrepr`) into the same shape the API and frontend expect, and
prints a small box-drawn summary to the captured log.

### 6.5 Supporting infrastructure

- **`pipeline/mcp_bridge.py` (`MCPBridge`)** — spawns
  `backend/node_modules/@playwright/mcp`'s CLI as a child process and speaks raw
  JSON-RPC 2.0 over stdin/stdout (hand-rolled, no SDK), one background reader thread
  dispatching responses to whichever call is waiting via a `threading.Event`. Re-uses
  `data/.auth/session.json` as Playwright `storage_state` if present, and does a
  warm-up navigation to `<dashboard>/home` on startup. A fresh `MCPBridge` (and thus a
  fresh real browser instance) is spawned per planner run and per generator scenario.
- **`pipeline/ai_client.py`** — thin wrapper creating an `OpenAI()` client from
  `OPENAI_API_KEY`; model is the single constant `AI_MODEL = 'gpt-4o'`
  (`pipeline/constants.py`). **The pipeline is OpenAI-powered, not Claude-powered.**
- **`pipeline/credential_manager.py`** — thread-local credential/publisher store with
  env-var fallback; nothing here is persisted, it's purely request/run-scoped.
- **`pipeline/agent_utils.py`** — shared agent-loop plumbing: MCP-tool→OpenAI-tool-schema
  conversion, tool-result truncation (8000 chars, cut at a line boundary), conversation
  history pruning (keep last N assistant "turns" + the first 2 system/user messages),
  and `call_with_retry` (exponential-ish backoff on 429/502/503/connection errors).
- **`pipeline/login_helper.py`** — see §7.
- **`pipeline/publisher.py`** — see §7.

### 6.6 Knowledge base (`pipeline/knowledge/`)

Two complementary, hand-maintained sources of ground truth that get injected into every
LLM prompt to suppress hallucination on this specific, undocumented dashboard:

- **`dashboard_facts.py`** — structured `PageFacts`/`FieldConstraint`/`ComboboxFacts`/
  `PublishStep` dataclasses for known pages (Article Create, Custom Page Create, Draft
  List, Published List, Tag Create, Category Create, Geography Create, etc.):
  exact required/optional field labels, which fields are React-controlled (must use
  `safe_sequential_fill`), combobox names + known options, the save button name, the
  URL pattern after save, and free-text notes (e.g. "Publish button is briefly disabled
  right after fields are filled — wait for `to_be_enabled`"). `detect_intent()` maps a
  free-text prompt → `{verb, page}`; `facts_for_prompt`/`facts_for_all_mentioned_pages`
  render the relevant subset as text for prompt injection; this same module backs the
  orchestrator's precondition-expansion and the planner/generator validators.
- **`dashboardHeuristics.md`** (loaded once via `heuristics_loader.get_heuristics`,
  `lru_cache`) — a hand-written "known failure patterns" doc in strict
  Always/Never imperative style, covering things like: the sidebar has no
  `role="navigation"`; Ant Design dropdown portals render at the end of `<body>` and
  share title text with sidebar links (`.last` + `exact=True` required); Ant Select
  option lists are **virtualized** (only ~9 of 65+ options exist in the DOM at a time,
  and the option set differs per publisher — never hardcode a category, always pick the
  first live option or type-to-filter); which fields are React-controlled; locator
  strategy is semantic-only (`get_by_role`/`get_by_text`/`get_by_title`, no CSS/XPath
  except one named exception); entity pages (geography/food/horoscope/...) live at
  `/posts/entity/<plural>/<singular>/create`, not at a guessable short path.

This file is effectively the institutional memory of every past flaky-test failure,
turned into prompt instructions — treat it as authoritative if writing docs about *why*
the generated tests look the way they do.

### 6.7 Validators & sanitizers (`pipeline/transforms/`)

| File | Role |
|---|---|
| `plan_parser.py` | regex-parses `plan.md` into `Scenario` objects; also has a large keyword→URL fallback table (`extract_scenario_url`) for when a plan step doesn't contain an explicit `page.goto`. |
| `plan_validator.py` | rejects a planner-proposed plan for ~9 distinct reasons (see §6.2); also exports `extract_fill_labels`/`normalize_field_name`, reused by the spec validator. |
| `spec_sanitizer.py` | deterministic regex rewrites applied to *every* accepted generated spec, regardless of validation (see §6.3). |
| `spec_validator.py` | semantic + data-uniqueness gates applied before a generated spec is allowed to be written to disk. |

---

## 7. Authentication, sessions & multi-publisher handling

The dashboard enforces **email-OTP MFA** that cannot be cleared by scripted
email+password login. The whole auth strategy is built around that constraint:

1. **`backend/capture_session.py`** — a manual, one-off script
   (`env/bin/python capture_session.py [EnvName]`) that opens a **headed** browser,
   pre-fills credentials from the named `Environment` row, checks "Stay signed in," and
   waits up to 5 minutes for a human to enter the 6-digit OTP. On success it saves
   Playwright's `storage_state` to `data/.auth/session.json` and rewrites any
   session-only cookies to expire ~24h out (`SESSION_EXPIRY_SECONDS`), and hard-fails if
   no real auth cookie (`session` / `publisher_agency`) was captured.
2. Every run reuses that one stored session file rather than logging in fresh.
   `pipeline/login_helper.py: refresh_session()` checks cookie validity (ignoring
   transient cookies like Cloudflare's `__cf_bm` or analytics cookies — only `session`
   and `publisher_agency` count) and **only** attempts a scripted login if the stored
   session is actually expired; if a scripted attempt lands on `/mfa`, it fails loudly
   instead of silently saving a useless session.
3. Because the dashboard is **multi-tenant**, the same session is always pinned to one
   publisher org via the `publisher_agency` cookie — not via URL. `pipeline/publisher.py:
   detect_active_publisher()` calls the dashboard's own `GET /api/user/` with the stored
   cookies and returns `{name, slug, id, domain}`. This is called at the start of every
   pipeline run, **logged**, and cached onto the `Environment.publisher` column —
   the system is explicitly designed to **never switch publishers itself**; switching
   requires a human to log in/provide a session for a different org.
4. `data/tests/conftest.py` independently re-derives/re-validates all of the above at
   pytest collection time (session-scoped autouse fixture `_report_active_publisher`)
   so a generated test run always logs which publisher it actually ran against, even
   when triggered outside the Django pipeline.

---

## 8. Frontend architecture

### 8.1 The 3-layer pattern (mandatory, documented in `CLAUDE.md`)

```
src/services/   Layer 1 — pure functions wrapping api.get/post/put/del. No state, no hooks.
src/hooks/      Layer 2 — all useQuery/useMutation/useQueryClient calls live here.
                One hook per domain concern (useCollections, useCollectionTests,
                useEnvironments, useExecutions, useExecutionDetail). Returns a flat
                object with everything its page needs.
src/pages/      Layer 3 — call 1-2 hooks, destructure, render. Own only ephemeral UI
                state (which modal is open, which row is selected).
```

`CLAUDE.md` calls out `https://production-code-docs.vercel.app/` as the canonical
architecture reference for this pattern and says every new file must conform to it —
"no exceptions." React Query conventions: query keys are
`['resource']`/`['resource', id]`/`['resource', 'scope', filters]`;
`invalidateQueries` always happens inside the owning hook's `onSuccess`;
`refetchInterval` is used (not raw polling) and is conditional on "is anything still
running/queued" so idle screens don't poll. The `api` client
(`frontend/src/api/client.ts`) is a 20-line `fetch` wrapper with `.get/.post/.put/.patch/.del`,
throwing `Error(body.error)` on non-2xx so React Query's `error.message` is always the
backend's envelope error string.

### 8.2 Routing & pages (`frontend/src/App.tsx`)

Single `Layout` (fixed 240px dark `Sidebar` + `TopBar`) wraps 5 routed pages:

| Route | Page component | Purpose |
|---|---|---|
| `/` | `Collections.tsx` | Table of collections w/ search + date filters, multi-select bulk run/delete, create/rename modals, empty-state onboarding illustration. |
| `/collections/:id` | `CollectionDetail.tsx` | Tests within one collection; each row expands inline (`TestExecutionDetail`) to show its run history; per-test run/edit/edit-spec/delete actions; "Run Suite" runs every generated spec in the collection. |
| `/executions` | `Executions.tsx` | **3-level drill-down** via URL search params (`?col=`, `?test=`): all executions (Live/History sections, filters, multi-select → `ComparePanel`) → per-collection test "folder" cards → per-test run list. Row actions include retry, delete, live log viewer (`LogViewerModal`, SSE), and a link to the static HTML report. |
| `/executions/:id` | `ExecutionDetail.tsx` | One run: status banner, 4-stage `PipelineSteps` timeline (click a stage to expand its captured log), per-test results table grouped by file, collapsible `plan.md` viewer, collapsible generated-spec code viewer, full run history table for that test, "Re-run" button. |
| `/environments` | `Environments.tsx` | Card grid CRUD for Environments — name/base URL/description/active toggle/login email+password (password optional on edit — blank keeps the existing one) — plus a read-only detected-Publisher field. |

Notable modals/slide-overs used across pages: `CreateTestSlideOver` (creating a test
optionally kicks off the live 4-stage pipeline with the same step-circle UI as
`ExecutionDetail`, streamed via SSE), `EditTestSlideOver`, `SpecEditor` (full code editor
for a generated `.py` file — edit, save, and re-run from the same panel, with a live
run-status side panel), `RunTestModal`/`RunSuiteModal`/`RunAllModal` (environment picker
+ kick off a run), `FilterDrawer`/`CollectionFilterDrawer`, `ComparePanel` (side-by-side
diff of 2 executions' steps/results).

### 8.3 Real-time updates

Two mechanisms coexist:
- **SSE**: `GET /api/executions/<id>/stream` (built via
  `constants.ts: sseStreamUrl()`), consumed directly with `EventSource`-style code in
  `LogViewerModal`/`SpecEditor`/`CreateTestSlideOver` for live step/log updates while a
  pipeline run is in flight.
- **React Query polling**: most list/detail queries set `refetchInterval` to a callback
  that checks `status === 'running' | 'queued'` and returns `false` otherwise — e.g.
  `useExecutionDetail`'s detail query polls every 2s only while running, test-results
  poll every 2s only while `pending`.

### 8.4 Styling

Tailwind with a fully custom Material-Design-3-flavored token palette defined in
`tailwind.config.ts` (`primary #3525cd`, semantic `surface-*`/`text-*`/`success`/
`warning`/`error` tokens, `Poppins` for UI text, `JetBrains Mono` for code/mono).
Icons are Google "Material Symbols" via class name + inline `fontVariationSettings`
(no icon component library). No CSS-in-JS; `index.css` is just the 3 Tailwind layer
directives plus one base rule.

---

## 9. Generated artifacts — concrete example

A real plan (`data/specs/category/<test-id>/plan.md`) for "create and verify a category":

```markdown
# Test Plan: Create and Verify Category
URL: https://betadashboard.thepublive.com/v2/categories/new

## Flow 1: Create Category and Verify
### Scenario: Create a category named 'QA Agent category' and verify it appears...
**Steps:**
1. Navigate to /categories/new via page.goto(...)
2. Use safe_sequential_fill(page, 'Name *', f'QA Agent category {ts}', delay=50) ...
3. Use safe_fill(page, 'Name in English (Permalink) *', f'qa-agent-category-{ts}')
4. Click get_by_role('combobox', name='Content Type'), then click the first live option...
5. Click get_by_role('button', name='Save Category')
**Expected:**
- expect(page).to_have_url(re.compile(r'/categories/'))
- get_by_text(f'QA Agent category {ts}') is visible in the categories list

## ACTIVE PUBLISHER: OdishaTv - Khabar
```

…and the corresponding generated+sanitized spec
(`data/tests/category/test_create-category-and-verify-....py`):

```python
import re, time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill

def test_create_category_and_verify(page):
    ts = int(time.time() * 1000)
    category_name = f'QA Agent category {ts}'
    permalink = f'qa-agent-category-{ts}'
    page.goto('/categories/new')
    safe_sequential_fill(page, 'Name *', category_name, delay=50)
    safe_fill(page, 'Name in English (Permalink) *', permalink)
    page.get_by_role('combobox', name='Content Type').click()
    option = page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first
    option.wait_for(state='visible')
    option.click()
    page.get_by_role('button', name='Save Category').click()
    expect(page).to_have_url(re.compile(r'/categories/'), timeout=15000)
```

`data/tests/helpers.py` provides the two fill helpers every generated test uses:
`safe_fill` (reads DOM `maxLength` at runtime, truncates, plain `.fill()`) and
`safe_sequential_fill` (same, but uses `press_sequentially` — required for
React-controlled inputs that don't fire `onChange` on a programmatic `.fill()`).
`data/tests/conftest.py` configures session-scoped browser launch args (headed only if
`HEADED=true`), reuses `.auth/session.json` as `storage_state` when valid, disables
video recording by default (enabling it risks a multi-minute hang if a test is killed
mid-action by `pytest-timeout`), and caps default action/navigation timeouts to 15s/20s
so a stuck locator fails inside the per-test 30s budget instead of hanging the whole run.

---

## 10. Running locally

```bash
# Backend
cd backend
pip install -r requirements.txt
npm install                  # pulls in @playwright/mcp + @playwright/test
python -m playwright install chromium
cp .env.example .env         # fill in SECRET_KEY, DATABASE_URL, OPENAI_API_KEY,
                              # DASHBOARD_URL/EMAIL/PASSWORD, FRONTEND_URL
python manage.py migrate
python capture_session.py Beta   # one-time: clear MFA by hand, save .auth/session.json
python manage.py runserver       # :8000

# Frontend
cd frontend
npm install
npm run dev                  # :5173, proxies /api and /reports to :8000 (vite.config.ts)
```

No Docker/CI config exists in the repo today (no `.github/` workflows found).

---

## 11. Observability

New Relic Python agent is wired in (`backend/newrelic.ini`, commit "Integrated New
Relic") for APM. **Caveat for anyone reusing this repo as a template: the New Relic
license key is currently committed in plaintext in `backend/newrelic.ini` and is not in
`.gitignore`** — treat it as already-leaked and rotate/move it to an env var if this
code is reused or made public.

---

## 12. Conventions & domain-specific gotchas worth knowing

These are encoded throughout the pipeline (prompts, validators, sanitizer) because they
were each, at some point, a real flaky-test root cause on this specific dashboard:

- **Never use `get_by_label()`** — form "labels" are styled `<div>`s, not `<label>`
  elements; use `get_by_role('textbox', name=...)`.
- **Never use `get_by_role('navigation')`** — the sidebar is a plain `<div>`.
- **Ant Design `<Select>` dropdown lists are virtualized** — only the visible ~9 options
  exist in the DOM at once, and the option set is per-publisher and time-varying. Always
  either pick the first live `.ant-select-item-option`, or type into the combobox to
  filter before clicking. Never hardcode an option's display text.
- **`get_by_title(...)` for Ant option text needs `exact=True` and `.last`** — sidebar
  links and dropdown options can share the same title text, and Ant renders dropdown
  portals at the end of `<body>`.
- **React-controlled inputs** (notably `Title *` on content-create forms, `Name *` on
  tag/category create) silently don't register a plain `.fill()` — must use
  `press_sequentially` (wrapped as `safe_sequential_fill`).
- **Articles/custom pages/entity pages publish directly** — there is no
  draft→edit→publish path for the default flow; "Save as Draft" is a separate, optional
  action. Entity pages (geography/food/horoscope/...) have *only* a Publish button.
- **Entity-type URLs follow `/posts/entity/<plural>/<singular>/create`** — never a
  guessable short path like `/geography`.
- **Every piece of generated test data is timestamp-suffixed** (`ts = int(time.time()*1000)`)
  so repeated runs never collide on uniqueness constraints (slugs, names).
- **Locators are semantic-only** (`get_by_role`/`get_by_text`/`get_by_title`) — CSS/XPath
  is banned except one named exception (`button.publisher-switcher`, which has no
  ARIA label).

---

## 13. Open items / things a future contributor should know

- No backend automated test suite exists yet (`core/tests.py`/`pipeline/tests.py` are
  unedited Django scaffolding).
- Run orchestration is plain background threads, not a task queue — fine at current
  scale, but there's no retry/visibility infrastructure beyond the DB rows themselves.
- `frontend/src/types.ts`'s `Environment` interface declares a `publisherId: string`
  field that the backend never actually serializes (`core/views/environments.py` only
  returns `publisher`, the name) — harmless today since nothing reads it, but a
  trap for anyone trying to use it.
- The New Relic key issue noted in §11.
