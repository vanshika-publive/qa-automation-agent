# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Reference doc:** https://production-code-docs.vercel.app/
This is the team's canonical architecture guide. Every new file must conform to it.

---

## Repository structure

```
automation-agent-2/
├── frontend/      # React + Vite + TypeScript dashboard
├── backend/       # Django + DRF API server + AI pipeline
└── data/          # Test specs, session data, pipeline artifacts (runtime, mostly gitignored)
    ├── .auth/session.json          # stored MFA session (single file, all pipeline runs reuse it)
    ├── specs/<collection>/<id>/    # plan.md + plan-snapshots.json per test
    ├── tests/<collection>/         # generated pytest specs + conftest.py + helpers.py
    └── reports/<collection>/<id>/  # results.json + HTML report per execution
```

---

## Dev commands

### Backend
```bash
cd backend
pip install -r requirements.txt
npm install                       # pulls @playwright/mcp and @playwright/test (Node-side, for the MCP bridge)
python -m playwright install chromium
cp .env.example .env              # fill SECRET_KEY, DATABASE_URL, OPENAI_API_KEY, DASHBOARD_URL/EMAIL/PASSWORD, FRONTEND_URL
python manage.py migrate
python capture_session.py Beta    # one-time: human clears MFA OTP, saves data/.auth/session.json
python manage.py runserver        # :8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev     # :5173 — Vite proxies /api and /reports to :8000
npm run build   # tsc -b && vite build
```

There is no automated test suite for the backend (`core/tests.py` and `pipeline/tests.py` are unedited Django scaffolding).

---

## Frontend architecture — 3 layers (non-negotiable)

All React code follows a strict **Services → Hooks → Pages** pattern.

```
frontend/src/
├── services/      # Layer 1 — pure API calls, no state
├── hooks/         # Layer 2 — all React Query + derived state
├── pages/         # Layer 3 — render only, thin
├── components/    # Shared UI primitives, modals, slide-overs
├── api/           # fetch wrapper (api.get/post/put/patch/del)
├── types.ts       # Shared TypeScript types
├── constants/     # editor colors, layout sizes, SSE URL builder
└── utils/         # Pure helpers (formatters, status maps)
```

### Layer 1 — Services (`src/services/`)
- Pure functions calling `api.get / api.post / api.put / api.del`
- No `useState`, no `useQuery`, no side effects
- One file per resource: `collections.ts`, `tests.ts`, `executions.ts`, `environments.ts`, `specs.ts`
- Return typed `ApiResponse<T>`

### Layer 2 — Hooks (`src/hooks/`)
- All `useQuery` / `useMutation` / `useQueryClient` calls live here
- One hook per domain: `useCollections`, `useCollectionTests`, `useEnvironments`, `useExecutions`, `useExecutionDetail`
- Return a flat object with everything the page needs
- `invalidateQueries` on mutation success always inside the hook's `onSuccess`
- `refetchInterval` only when `status === 'running' | 'queued'`; `enabled` guards on ID-dependent queries

### Layer 3 — Pages (`src/pages/`)
- Call 1–2 hooks, destructure, render JSX
- Own only ephemeral UI state: `modalOpen`, `selectedId`, `inputValue`
- No `api.*` calls, no raw `useQuery`, no business logic

---

## API response envelope

All endpoints return `{ data: T | null, error: string | null }` (`ApiResponse<T>`).  
Always destructure `.data` — never assume the top-level response is the payload.  
The API client (`api/client.ts`) throws `Error(body.error)` on non-2xx so `error.message` is always the backend's envelope error string.

---

## Backend — domain model

All tables use **soft delete** (`deleted_at`; default manager filters it out; `all_objects` sees everything). IDs are UUID `TextField`s. Timestamps are ISO-8601 strings, not native datetimes.

```
Environment                 Collection
  id, name, base_url           id, name
  login_email, login_password  └─< Test (FK collection)
  publisher  ← detected live        id, name, prompt, status
  is_active                         environment_ids (JSON array stored as text)
                                    └─< Execution (FK test + FK environment)
                                          id, status, pass/fail/total counts, report_dir
                                          └─< ExecutionStep  (orchestrator|planner|generator|runner)
```

Key rules:
- `Environment.publisher` is **never set by the user** — it's detected live from the dashboard's `GET /api/user/` using stored session cookies and cached on the row. The system never switches publisher.
- `Execution.report_dir` (`"<collection-slug>/<execution-id>"`) is the join key into `data/reports/`; per-test results live in `results.json` on disk, not fully in Postgres.
- On every Django startup (`CoreConfig.ready()`): stuck `running` executions are marked `failed`, and two default Environments ("Beta", "Production") are seeded if the table is empty.

---

## AI pipeline (`backend/pipeline/`)

Entry point: `pipeline/run_pipeline.py:PipelineRunner.run()`, called from a **daemon thread** (no Celery/RQ). Four stages run sequentially; one `ExecutionStep` row per stage captures stdout/stderr via a `LogCapture`/`_TeeWriter` redirect. A stage failure aborts remaining stages.

Before any stage: resolves prompt + collection slug, refreshes the stored session, detects the active publisher (thread-locally via `pipeline/utils/credential_manager.py`).

Pipeline subpackage layout:
```
pipeline/
├── services/        # one class per stage: OrchestratorService, PlannerService, GeneratorService, RunnerService
├── infrastructure/  # ai_client.py, mcp_bridge.py, login_helper.py, publisher.py
├── utils/           # agent_utils.py, credential_manager.py, log_capture.py, step_manager.py
├── tools/           # planner_tools.py, generator_tools.py — OpenAI tool schemas
├── prompts/         # orchestrator_prompt.py, planner_prompt.py, generator_prompt.py
├── transforms/      # plan_parser.py, plan_validator.py, spec_validator.py, spec_sanitizer.py
├── knowledge/       # dashboard_facts.py, heuristics_loader.py
└── run_pipeline.py  # PipelineRunner entry point
```

| Stage | File | What it does |
|---|---|---|
| **Orchestrator** | `pipeline/services/orchestrator_service.py` | Pure LLM (`gpt-4o`). Turns user's prompt → structured `TestPlan` JSON. Injects `dashboard_facts.py` knowledge. Then deterministically expands missing precondition steps (no LLM). |
| **Planner** | `pipeline/services/planner_service.py` | Agentic loop (max 20 iters). Drives a **real headless browser** via `MCPBridge` to discover the actual UI. Read-only Playwright MCP tools (navigate/snapshot/click/hover). Writes `plan.md` + `plan-snapshots.json`. Plans are validated by `transforms/plan_validator.py` before acceptance; rejections feed back as retries. |
| **Generator** | `pipeline/services/generator_service.py` | Agentic loop per scenario (max 20 iters). Writes Python pytest-playwright code. Gated by `transforms/spec_validator.py` before write, then deterministically cleaned up by `transforms/spec_sanitizer.py`. Skips if spec already on disk (idempotent). |
| **Runner** | `pipeline/services/runner_service.py` | No LLM. Shells out to `pytest` with `--json-report --html --timeout=30`. 4-minute hard kill with `SIGKILL` on the process group. |

The pipeline is **OpenAI-powered** (`gpt-4o`), not Claude. `pipeline/infrastructure/ai_client.py` holds the single `AI_MODEL = 'gpt-4o'` constant (`pipeline/constants.py`).

`pipeline/infrastructure/mcp_bridge.py` spawns `backend/node_modules/@playwright/mcp`'s CLI as a child process and speaks raw JSON-RPC 2.0 over stdin/stdout. A fresh `MCPBridge` (= a fresh real browser) is spawned per planner run and per generator scenario.

`pipeline/utils/agent_utils.py` is shared plumbing for both agentic loops: MCP-tool→OpenAI-tool-schema conversion, tool-result truncation (8000 chars), conversation history pruning (keep last N assistant turns + first 2 system/user messages), and `call_with_retry` (exponential backoff on 429/502/503/connection errors).

---

## Knowledge base (`pipeline/knowledge/`)

Two hand-maintained sources injected into every LLM prompt:

- **`dashboard_facts.py`** — structured `PageFacts` dataclasses per dashboard page: exact field labels, which fields are React-controlled, combobox options, save-button name, URL-after-save. Powers orchestrator precondition expansion and planner/generator validators.
- **`dashboardHeuristics.md`** — institutional memory of past flaky-test failures in Always/Never imperative style. Authoritative for *why* generated tests look the way they do.

---

## MFA session & auth

The dashboard enforces email-OTP MFA that can't be scripted. Auth strategy:

1. `capture_session.py` — run manually once; opens a headed browser, waits for human OTP entry, saves `data/.auth/session.json`. Sessions expire ~24h.
2. Every pipeline run reuses the single stored session. `pipeline/infrastructure/login_helper.py:SessionManager.refresh()` checks cookie validity (only `session`/`publisher_agency` cookies count) and fails loudly on `/mfa` redirect rather than saving a broken session.
3. Re-run `python capture_session.py [EnvName]` from `backend/` to refresh after expiry.

---

## Backend REST API — key endpoints

Base path `/api/`. No authentication (`AllowAny`). All responses use the `{ data, error }` envelope.

- `GET/POST /collections`, `PATCH/DELETE /collections/<id>`
- `GET/POST /collections/<id>/tests`, `PUT/DELETE /tests/<id>`
- `POST /executions/tests/<test_id>/run` — **kicks off the full 4-stage pipeline**, returns `{executionId}` immediately (202)
- `GET /executions/<id>/stream` — **Server-Sent Events**, polls DB every 0.8s until run exits `'running'`
- `GET /executions/<id>/steps` — per-test pytest results parsed live from `results.json`
- `GET /executions/<id>/tests` — same results, flattened with a `pending` flag while running
- `GET /executions/<id>/files` — returns generated spec source + `plan.md` for this run
- `DELETE /executions/<id>` — soft-delete (409 if `status='running'`)
- `GET/PUT /tests/<id>/spec`, `POST /tests/<id>/run-spec` — view/edit/re-run a generated spec (skips orchestrator/planner/generator)
- `GET /collections/<id>/specs`, `GET /specs/view?file=...`, `DELETE /specs?file=...` — list/read/delete spec files on disk
- `POST /collections/<id>/run-all-specs` — runs every existing spec in a collection as one Execution
- `GET /environments/active-publisher` — live-detects publisher from stored session
- `GET /health` — liveness check

---

## Frontend pages

Single `Layout` (240px dark `Sidebar` + `TopBar`) wraps 5 routes:

| Route | Page | Purpose |
|---|---|---|
| `/` | `Collections.tsx` | Table with search/date filters, create/rename/bulk-delete |
| `/collections/:id` | `CollectionDetail.tsx` | Tests within a collection; inline execution history; "Run Suite" |
| `/executions` | `Executions.tsx` | 3-level drill-down via `?col=`/`?test=` params; ComparePanel |
| `/executions/:id` | `ExecutionDetail.tsx` | 4-stage pipeline timeline, per-test results, plan.md + spec viewer, Re-run |
| `/environments` | `Environments.tsx` | Card grid CRUD; detected publisher field (read-only) |

Real-time updates: SSE (`EventSource`) for in-flight pipeline runs; React Query `refetchInterval` for list/detail polling (only while `status === 'running' | 'queued'`).

---

## Styling

Tailwind with a custom MD3-flavored token palette (`tailwind.config.ts`): `primary #3525cd`, `surface-*`/`text-*`/`success`/`warning`/`error` tokens. Fonts: `Poppins` (UI), `JetBrains Mono` (code). Icons: Google Material Symbols via class name + inline `fontVariationSettings` — no icon component library.

---

## Generated-test conventions (important gotchas)

These rules are enforced by the validators and sanitizer — violating them causes test failures on this specific dashboard:

- **Never `get_by_label()`** — form "labels" are `<div>`s; use `get_by_role('textbox', name=...)`.
- **Never `get_by_role('navigation')`** — the sidebar is a plain `<div>`.
- **Ant Design `<Select>` lists are virtualized** — only ~9 options exist in DOM at once, per-publisher and time-varying. Always pick first live `.ant-select-item-option` or type-to-filter. Never hardcode option text.
- **`get_by_title()` for Ant options needs `exact=True` and `.last`** — sidebar links and dropdown options can share title text.
- **React-controlled inputs** (Title, Name fields) don't fire `onChange` on `.fill()` — use `safe_sequential_fill` from `data/tests/helpers.py`.
- **Articles/custom pages/entity pages publish directly** — no draft→edit→publish flow; "Save as Draft" is separate.
- **Entity-type URLs**: `/posts/entity/<plural>/<singular>/create` — not a short path.
- **All test data is timestamp-suffixed**: `ts = int(time.time()*1000)` — enforced by `spec_validator.py`.
- **Locators are semantic-only**: `get_by_role`/`get_by_text`/`get_by_title`. CSS/XPath banned (one exception: `button.publisher-switcher`).
- **Run tests headed** for debugging: set `HEADED=true` env var before the pytest command (wired in `data/tests/conftest.py`). Video recording is disabled by default — enabling it can cause a multi-minute hang if a test is killed mid-action by `pytest-timeout`.

---

## Observability

New Relic APM is wired in via `backend/newrelic.ini` (Python agent). The license key is currently committed in plaintext in that file — rotate it and move it to an env var before making this repo public.

---

## Known type mismatch

`frontend/src/types.ts`'s `Environment` interface declares a `publisherId: string` field that `core/views/environments.py` never serializes (it only returns `publisher`, the name string). Nothing currently reads `publisherId` so it's harmless, but don't write code that depends on it.

---

## Backend layout

```
backend/
├── config/          # Django project package: settings.py, urls.py, wsgi/asgi
├── core/            # CRUD app: models/, serializers/, views/, services/, decorators, managers
├── pipeline/        # AI pipeline (see above) — no DB models of its own
├── utils/           # Shared helpers: datetime_utils.py, slug.py, errors.py, json_utils.py, markdown.py
├── capture_session.py
└── manage.py
```

`config/settings.py` defines two important path constants used throughout:
- `BACKEND_ROOT` — the `backend/` dir (where `node_modules/@playwright/mcp` lives)
- `PLAYWRIGHT_PROJECT_ROOT` — the `data/` dir (overridable via env var; where all generated/runtime artifacts live)

`core/models/` is a **package** (not a single file): `collection.py`, `environment.py`, `execution.py`, `test.py`, with `__init__.py` re-exporting all models.

`core/services/` is the business logic layer sitting between views and models: `collection_service.py`, `environment_service.py`, `execution_service.py`, `test_service.py`. Views call services; services call ORM. Do not put ORM logic directly in views.

---

## Backend view architecture

All views are `APIView` subclasses — **one class per URL**, handlers named by the HTTP verb only (`get`, `post`, `put`, `patch`, `delete`). No `ViewSet`, no DRF router. Every route is declared explicitly in `core/urls.py` via `path(..., SomeView.as_view())`.

Two reusable decorators in `core/decorators.py` handle cross-cutting concerns:
- `@validate_body(SerializerClass)` — runs the input serializer, injects `data=validated_data` kwarg, raises `ValidationError` (→ 400) on failure.
- `@fetch_object(Model, "X not found", select_related=())` — fetches by URL `pk`, injects `obj=` kwarg, raises `NotFound` (→ 404) on miss.

Stacking order matters: `@fetch_object` outermost when a 404 should take priority over a 400; `@validate_body` outermost when a missing body field should be caught first.

---

## Serializer conventions

Serializers live in `backend/core/serializers/` (package — one file per resource: `collection.py`, `environment.py`, `test.py`, `execution.py`, plus `__init__.py` that re-exports all classes). All **output** serializers use **camelCase** field names that match `frontend/src/types.ts` exactly (e.g. `createdAt`, `testCount`, `baseUrl`, `isActive`, `collectionId`). Never add snake_case fields to an output serializer.

Input serializers (`*WriteSerializer`, `*CreateSerializer`, `*UpdateSerializer`) are used exclusively through the `@validate_body` decorator — never call `.is_valid()` manually inside a view handler.

---

## Git

- PR target: `main`
- Never force-push `main`
