# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Reference doc:** https://production-code-docs.vercel.app/
This is the team's canonical architecture guide. Every new file must conform to it.

---

## Repository structure

```
automation-agent-2/
├── frontend/      # React + Vite + TypeScript dashboard
├── backend/       # Django + DRF API server + AI pipeline + live_view streamer
├── scripts/       # ops scripts (e.g. smoke-check-liveview.sh)
└── data/          # Pipeline scratch space (runtime, mostly gitignored) — see note below
    ├── .auth/session.json          # scratch copy of the MFA session; DB (AuthSession) is canonical
    ├── specs/<collection>/<id>/    # scratch plan.md + plan-snapshots.json while a run is in-flight
    ├── tests/<collection>/         # scratch generated pytest specs + conftest.py + helpers.py
    └── reports/<collection>/<id>/  # HTML report per execution (still disk-only) + scratch results.json
```

**Postgres is now the source of truth for specs/plans/results/session** (migrated from pure-disk storage; see `TestSpec`/`TestPlan`/`ExecutionResult`/`AuthSession` in the domain model below and `core/services/artifact_store.py`). `data/` is kept only because `pytest` and the `@playwright/mcp` subprocess can only read/write real files — the pipeline writes there as scratch and a service layer (`ArtifactStore`) mirrors it into the DB. The one exception: generated HTML reports stay disk-only, served at `/reports/`.

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
- One file per resource: `collections.ts`, `tests.ts`, `executions.ts`, `environments.ts`, `specs.ts`, `liveView.ts` (reads `VITE_LIVE_VIEW_*` env vars — no API calls, see **WebRTC live-view** below)
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

TypeScript is configured with `strict: true`, `noUnusedLocals: true`, and `noUnusedParameters: true` — unused variables or parameters are **compile errors**, not warnings. `npm run build` runs `tsc -b` first and will fail on any unused identifier.

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
  └─< AuthSession (FK, nullable)     latest_good_plan, failed_at_step
        id, storage_state           ├─< TestSpec (FK test) — id, filename, content
                                     ├─< TestPlan (FK test, related_name='plan')
                                     │     id, plan_md, plan_snapshots (JSON-as-text), plan_prompt
                                     ├─< Execution (FK test + FK environment)
                                     │     id, status, pass/fail/total counts, report_dir
                                     │     ├─< ExecutionStep  (orchestrator|planner|generator|runner)
                                     │     └─< ExecutionResult (related_name='result')
                                     │           id, results_json, step_failure_json
                                     └─< TestPlanningMemory (FK test)
                                           id, content   ← human navigation corrections, max 4
```

Key rules:
- `Environment.publisher` is **never set by the user** — it's detected live from the dashboard's `GET /api/user/` using stored session cookies and cached on the row. The system never switches publisher.
- `Execution.report_dir` (`"<collection-slug>/<execution-id>"`) is the join key into `data/reports/` for the HTML report; per-test results live in Postgres (`ExecutionResult.results_json`), mirrored from disk by `ArtifactStore.save_results` after the runner stage.
- `TestSpec` (generated pytest source), `TestPlan` (`plan.md` + snapshots + the prompt that produced it), and `AuthSession` (`storage_state`, keyed to an `Environment`) replaced the old disk-only `data/specs/`, `data/tests/`, and `data/.auth/session.json` respectively — Postgres is canonical, disk is ephemeral scratch. `core/services/artifact_store.py:ArtifactStore` is the single seam for all reads/writes between disk scratch and these tables (`save_spec`, `save_plan`/`save_plan_from_disk`, `materialize_plan`, `save_results`, `save_session`/`save_session_from_disk`, `materialize_session`, etc.). `Test.latest_good_plan` (plain text column, unrelated to the `TestPlan` table) is unchanged — see planning memory below.
- On every Django startup (`CoreConfig.ready()`): stuck `running` executions are marked `failed`, and two default Environments ("Beta", "Production") are seeded if the table is empty.
- **Planning memory & good plans** (`Test.latest_good_plan` / `failed_at_step` + `TestPlanningMemory`): `latest_good_plan` is the exact `plan.md` markdown that last passed for a test — a run replays it (skipping orchestrator+planner) and only falls back to a fresh planner run when there's no good plan or the replay fails. `TestPlanningMemory` holds up to 4 **human-authored** navigation corrections injected into fresh planner prompts. The automated pipeline (`run()`/`run_spec()`) never writes planning memory — only the human `POST /tests/<id>/planning-memory` and `POST /tests/<id>/corrections` paths do.

---

## AI pipeline (`backend/pipeline/`)

Entry point: `pipeline/run_pipeline.py:PipelineRunner.run()`, called from a **daemon thread** (no Celery/RQ). Four stages run sequentially; one `ExecutionStep` row per stage captures stdout/stderr via a `LogCapture`/`_TeeWriter` redirect. All four `ExecutionStep` rows are **pre-created as `pending`** before the pipeline starts — this lets the SSE stream report them immediately. A stage failure aborts remaining stages (remaining steps stay `pending`, not `failed`). Runs are cooperatively cancellable via `pipeline/utils/cancellation.py` (backs the `POST /executions/<id>/stop` endpoint).

Three `PipelineRunner` entry points share this scaffolding: `run()` (full 4-stage), `run_spec()` (runner only, replays a saved spec), and `run_correction()` (human-initiated corrective replan — planner→generator→runner over a plan whose prefix is preserved). Two feature behaviors thread through them:
- **Replay-first**: `run()` restores `Test.latest_good_plan` to `plan.md` and **skips orchestrator+planner** when a good plan exists for the unchanged prompt; a clean pass writes `plan.md` back to `latest_good_plan`. Only a missing good plan or a failed replay triggers a fresh planner run.
- **Planning-memory injection**: fresh planner runs inject up to 4 `TestPlanningMemory` corrections into the system prompt (via `prompts/_shared.py:_planning_memory_section`). Empty memory ⇒ the prompt is byte-identical to the pre-feature baseline. `run_correction()` additionally feeds the human correction + fixed prefix to `PlannerService.run(..., correction=)`, then `transforms/plan_parser.py:preserve_prefix_steps` guarantees the prefix is byte-identical before generator/runner; on pass it records the correction as planning memory.

Before any stage: resolves prompt + collection slug, refreshes the stored session, detects the active publisher (thread-locally via `pipeline/utils/credential_manager.py`).

Stage services (`planner_service.py`, `generator_service.py`) still read/write **disk only** (`plan.md`, `plan-snapshots.json`, `test_<name>.py`) — they have no knowledge of Postgres. `run_pipeline.py` mirrors disk into the DB one layer up (`ArtifactStore.materialize_plan` before a stage, `save_plan_from_disk`/`save_specs_from_paths` after), and `runner_service.py` calls `ArtifactStore.save_results` once pytest finishes. See **Backend — domain model** above for the tables this mirrors into.

Pipeline subpackage layout:
```
pipeline/
├── services/        # one class per stage: OrchestratorService, PlannerService, GeneratorService, RunnerService
├── infrastructure/  # ai_client.py, mcp_bridge.py, login_helper.py, publisher.py
├── utils/           # agent_utils.py, cancellation.py, credential_manager.py, log_capture.py, step_manager.py
├── tools/           # planner_tools.py, generator_tools.py — OpenAI tool schemas
├── prompts/         # orchestrator_prompt.py, planner_prompt.py, generator_prompt.py, _shared.py
├── transforms/      # plan_parser.py, plan_validator.py, spec_validator.py, spec_sanitizer.py
├── knowledge/       # dashboard_facts.py, heuristics_loader.py
└── run_pipeline.py  # PipelineRunner entry point
```

| Stage | File | What it does |
|---|---|---|
| **Orchestrator** | `pipeline/services/orchestrator_service.py` | Pure LLM (`gpt-4o`). Turns user's prompt → structured `TestPlan` JSON. Injects `dashboard_facts.py` knowledge. Then deterministically expands missing precondition steps (no LLM). |
| **Planner** | `pipeline/services/planner_service.py` | Agentic loop (max **8** iters). Drives a **real headless browser** via `MCPBridge` to discover the actual UI. Read-only Playwright MCP tools (navigate/snapshot/click/hover). Writes `plan.md` + `plan-snapshots.json`. Plans are validated by `transforms/plan_validator.py` before acceptance; rejections feed back as retries. |
| **Generator** | `pipeline/services/generator_service.py` | Agentic loop per scenario (max 10 iters). Writes Python pytest-playwright code. Gated by `transforms/spec_validator.py` before write, then deterministically cleaned up by `transforms/spec_sanitizer.py`. Skips if spec already on disk (idempotent). |
| **Runner** | `pipeline/services/runner_service.py` | No LLM. Shells out to `pytest` with `--json-report --html --timeout=30`. 4-minute hard kill with `SIGKILL` on the process group. |

The pipeline is **OpenAI-powered** (`gpt-4o`), not Claude. `pipeline/infrastructure/ai_client.py` holds the single `AI_MODEL = 'gpt-4o'` constant. Key tuning thresholds live in `pipeline/constants.py`: `MAX_PLANNER_ITERATIONS=8`, `MAX_GENERATOR_ITERATIONS=10`, `MCP_TIMEOUT_MS=30_000`, `PIPELINE_KILL_TIMEOUT_MS=240_000`, `MCP_PROTOCOL_VERSION='2024-11-05'`. Nudge thresholds gate mid-loop intervention messages: `PLANNER_NUDGE_THRESHOLD=0.75`, `GENERATOR_NUDGE_THRESHOLD=0.7`, `GENERATOR_FINAL_WARNING_THRESHOLD=0.87` (fraction of max iterations at which the agent is warned it's running low).

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

1. `capture_session.py` — run manually once; opens a headed browser, waits for human OTP entry, writes `data/.auth/session.json` then mirrors it into Postgres via `ArtifactStore.save_session_from_disk` (the `AuthSession` row, keyed to an `Environment`, is now canonical). Sessions expire ~24h.
2. Every pipeline run reuses the most recent `AuthSession` row (`core/services/environment_service.py` calls `ArtifactStore.materialize_session` to re-hydrate the disk scratch file before use). `pipeline/infrastructure/login_helper.py:SessionManager.refresh()` checks cookie validity (only `session`/`publisher_agency` cookies count), then confirms the dashboard still **accepts** those cookies via `utils/session_liveness.py` (see below), and fails loudly on `/mfa` redirect rather than saving a broken session.

**A session can be revoked while its cookies still look valid.** The dashboard invalidates sessions server-side long before the cookie `expires` that `capture_session.py` writes — in particular, capturing a new session on another machine kills the older one, so only one machine can hold a live session at a time. Cookie-presence/expiry checks therefore report a dead session as usable, and the whole pipeline runs logged out: the planner's last observed page is `/v2/login` and the runner fails on sidebar nav links (`get_by_role('link', name='Configuration')`) with `Element not found`, which reads like per-test locator bugs. `utils/session_liveness.py:check_session()` is the guard — it asks `GET /api/user/` and returns `LIVE` / `REVOKED` / `UNKNOWN`, and is called from **both** `SessionManager.refresh()` (raises with re-capture instructions) and the pytest harness's `_require_live_session` fixture in `harness/conftest.py` (fails the run at setup, in <1s, instead of after minutes of bogus timeouts). `UNKNOWN` (offline, 5xx) is deliberately **not** treated as a failure — those runs proceed exactly as before. The module is stdlib-only and imports no Django on purpose, because the pytest subprocess has no `DJANGO_SETTINGS_MODULE` configured.
3. Re-run `python capture_session.py [EnvName]` from `backend/` to refresh after expiry.

---

## Backend REST API — key endpoints

Base path `/api/`. No authentication (`AllowAny`). All responses use the `{ data, error }` envelope.

- `GET/POST /collections`, `PATCH/DELETE /collections/<id>`
- `GET/POST /collections/<id>/tests`, `PUT/DELETE /tests/<id>`
- `POST /executions/tests/<test_id>/run` — **kicks off the full 4-stage pipeline**, returns `{executionId}` immediately (202)
- `GET /executions/<id>/stream` — **Server-Sent Events**, polls DB every 0.8s until run exits `'running'`
- `GET /executions/<id>/steps` — per-test pytest results, read from `ExecutionResult.results_json` (Postgres)
- `GET /executions/<id>/tests` — same results, flattened with a `pending` flag while running
- `GET /executions/<id>/files` — returns generated spec source (`TestSpec`) + plan (`TestPlan.plan_md`) for this run
- `POST /executions/<id>/stop` — request cooperative cancellation of a running execution
- `DELETE /executions/<id>` — soft-delete (409 if `status='running'`)
- `GET/PUT /tests/<id>/spec`, `POST /tests/<id>/run-spec` — view/edit/re-run a generated spec (skips orchestrator/planner/generator)
- `GET/POST /tests/<id>/planning-memory`, `PATCH/DELETE /tests/<id>/planning-memory/<mid>` — human-authored navigation corrections (max 4; POST returns a non-blocking intent-vs-navigation `advisory`)
- `POST /tests/<id>/corrections` `{ failedAtStep, correction, environmentId }` — **human-initiated corrective replan**: keeps the plan prefix (steps 1..N-1), re-plans the tail, and on pass saves the good plan + records the correction as planning memory (409 if memory is full)
- `GET /collections/<id>/specs`, `GET /specs/view?file=...`, `DELETE /specs?file=...` — list/read/delete generated specs (`TestSpec` rows, materialized to disk on demand via `ArtifactStore`)
- `POST /collections/<id>/run-all-specs` — runs every existing spec in a collection as one Execution
- `GET /environments/active-publisher` — live-detects publisher from stored session
- `GET /health` — liveness check

---

## Frontend pages

Single `Layout` (240px dark `Sidebar` + `TopBar`) wraps 6 routes:

| Route | Page | Purpose |
|---|---|---|
| `/` | `Collections.tsx` | Table with search/date filters, create/rename/bulk-delete |
| `/collections/:id` | `CollectionDetail.tsx` | Tests within a collection; inline execution history; "Run Suite" |
| `/executions` | `Executions.tsx` | 3-level drill-down via `?col=`/`?test=` params; ComparePanel |
| `/executions/:id` | `ExecutionDetail.tsx` | 4-stage pipeline timeline, per-test results, plan.md + spec viewer, Re-run |
| `/executions/batch` | `BatchExecutionStatus.tsx` | Live status of a batch run (run-all-specs / run-all-collections) |
| `/environments` | `Environments.tsx` | Card grid CRUD; detected publisher field (read-only) |

Real-time updates: SSE (`EventSource`) for in-flight pipeline runs; React Query `refetchInterval` for list/detail polling (only while `status === 'running' | 'queued'`).

---

## WebRTC live-view

Lets a user watch a pipeline run's real headless browser live from the dashboard. Not a Django feature — a separate process.

- **Backend**: `backend/live_view/` (`webrtc_server.py`, `__main__.py`) — a standalone asyncio/aiohttp process, run as `python -m live_view`. Captures the Xvfb `:99` display via GStreamer (`ximagesrc` → `vp8enc` → `webrtcbin`), serves `GET /health` and signals over `ws://<host>:<LIVE_VIEW_PORT>/ws/live?token=<LIVE_VIEW_TOKEN>` (default port `8001`). Started by `backend/docker-entrypoint.sh`, which brings up `Xvfb :99 -screen 0 1280x800x24` and, when `LIVE_VIEW_ENABLED` is truthy, forces `HEADED=true` and launches the streamer in the background. Config is read directly via `os.environ` (not in `config/settings.py`): `LIVE_VIEW_ENABLED`, `LIVE_VIEW_TOKEN`, `LIVE_VIEW_PORT`, `LIVE_VIEW_FPS` (default 15), `LIVE_VIEW_BITRATE` (default 2_000_000), `LIVE_VIEW_STUN`, `DISPLAY` (default `:99`).
- **Frontend**: `services/liveView.ts` (`isLiveViewEnabled()`, `liveViewWsUrl()`), `hooks/useLiveBrowser.ts` (owns the `RTCPeerConnection` + signaling `WebSocket` lifecycle), `components/LiveBrowserModal.tsx` (modal shell). Wired into `pages/ExecutionDetail.tsx` as a "Watch live" button gated by `isLiveViewEnabled()`. `useRunActions.ts`'s `useRunTest` navigates to `/executions/:id` with `state: { autoLive: true }` on Run/Re-run, and `ExecutionDetail.tsx` auto-opens the modal when that flag is set and live-view is enabled.
- **Deploy**: only relevant on the single-box EC2 deploy, via the `docker-compose.webrtc.yml` overlay layered on top of the base compose file (see **Docker** below).

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

## Docker

`docker-compose.yml` runs `db` (Postgres 16), `backend` (:8000, also exposes :8001 for the live-view streamer), and `frontend` (:5173). Critical notes:
- Backend container requires `shm_size: '1gb'` — headless Chromium crashes without it.
- `VITE_API_PROXY_TARGET=http://backend:8000` must be set for the frontend container to reach the backend service (defaults to `localhost:8000` in local dev).
- `data/` is bind-mounted into the backend container; `capture_session.py` must be run on the **host** (needs a headed browser for OTP entry) and writes into the same `data/` directory (then gets mirrored into Postgres — see **MFA session & auth**).

`docker-compose.webrtc.yml` is an EC2-only overlay (`docker compose -f docker-compose.yml -f docker-compose.webrtc.yml up -d --build`) — bridge networking can't forward WebRTC's ephemeral UDP range, so this switches `backend` to `network_mode: host`, points `DATABASE_URL` at `127.0.0.1`, exposes Postgres on host loopback, and passes `VITE_LIVE_VIEW_ENABLED=1` / `VITE_LIVE_VIEW_PORT=8001` / `VITE_LIVE_VIEW_TOKEN` to `frontend`. `scripts/smoke-check-liveview.sh` is the post-deploy smoke check — verifies backend health + migrations, the live-view token gate, and optionally kicks off one real execution (`./scripts/smoke-check-liveview.sh <TEST_ID>`).

---

## Observability

New Relic APM is wired in via `backend/newrelic.ini` (Python agent). The license key is currently committed in plaintext in that file — rotate it and move it to an env var before making this repo public.

---

## Backend layout

```
backend/
├── config/          # Django project package: settings.py, urls.py, wsgi/asgi
├── core/            # CRUD app: models/, serializers/, views/, services/, decorators, managers
├── pipeline/        # AI pipeline (see above) — no DB models of its own
├── live_view/       # standalone WebRTC streamer (webrtc_server.py, __main__.py) — see WebRTC live-view
├── utils/           # Shared helpers: datetime_utils.py, slug.py, failure_classifier.py, json_utils.py, markdown.py, session_liveness.py
├── harness/         # CANONICAL pytest harness: conftest.py, helpers.py, pytest.ini — edit these, not the copies
├── docker-entrypoint.sh
├── newrelic.ini
├── capture_session.py
└── manage.py
```

`backend/harness/` holds the **canonical** pytest harness (`conftest.py`, `helpers.py`, `pytest.ini`). `CoreConfig.ready()` → `_seed_test_harness()` copies these three files over `data/tests/` on **every Django startup**, so edits made directly to `data/tests/conftest.py` are silently overwritten on the next restart — always edit `backend/harness/` and restart (or copy across manually to test without one). Generated spec files live in per-collection subdirs and are never touched by the seed.

`utils/failure_classifier.py:classify_failure(error_text)` — deterministic (no-LLM) categorization of pytest stderr into 7 human-readable failure types (`'Element not found'`, `'Multiple elements matched'`, `'Navigation timeout'`, `'Session / login'`, `'Assertion failed'`, `'Timeout'`, `'Test error'`). Called by `execution_service.py` when parsing `results.json`.

`config/settings.py` defines two important path constants used throughout:
- `BACKEND_ROOT` — the `backend/` dir (where `node_modules/@playwright/mcp` lives)
- `PLAYWRIGHT_PROJECT_ROOT` — the `data/` dir (overridable via env var; where all generated/runtime artifacts live)

`core/models/` is a **package** (not a single file): `collection.py`, `environment.py`, `execution.py` (`Execution` + `ExecutionStep` + `ExecutionResult`), `test.py`, `test_spec.py`, `test_plan.py`, `auth_session.py`, `planning_memory.py` — the last three added by migrations `0003_artifact_tables` / `0004_backfill_artifacts` (see **Backend — domain model**) — with `__init__.py` re-exporting all models.

`core/services/` is the business logic layer sitting between views and models: `collection_service.py`, `environment_service.py`, `execution_service.py`, `test_service.py`, `planning_memory_service.py`, `artifact_store.py` (the disk-scratch ⇄ Postgres seam). Views call services; services call ORM. Do not put ORM logic directly in views.

---

## Backend view architecture

All views are `APIView` subclasses — **one class per URL**, handlers named by the HTTP verb only (`get`, `post`, `put`, `patch`, `delete`). No `ViewSet`, no DRF router. Every route is declared explicitly in `core/urls.py` via `path(..., SomeView.as_view())`.

Two reusable decorators in `core/decorators.py` handle cross-cutting concerns:
- `@validate_body(SerializerClass)` — runs the input serializer, injects `data=validated_data` kwarg, raises `ValidationError` (→ 400) on failure.
- `@fetch_object(Model, "X not found", select_related=())` — fetches by URL `pk`, injects `obj=` kwarg, raises `NotFound` (→ 404) on miss.

Stacking order matters: `@fetch_object` outermost when a 404 should take priority over a 400; `@validate_body` outermost when a missing body field should be caught first.

---

## Serializer conventions

Serializers live in `backend/core/serializers/` (package — one file per resource: `collection.py`, `environment.py`, `test.py`, `execution.py`, `planning_memory.py`, plus `__init__.py` that re-exports all classes). All **output** serializers use **camelCase** field names that match `frontend/src/types.ts` exactly (e.g. `createdAt`, `testCount`, `baseUrl`, `isActive`, `collectionId`). Never add snake_case fields to an output serializer.

Input serializers (`*WriteSerializer`, `*CreateSerializer`, `*UpdateSerializer`) are used exclusively through the `@validate_body` decorator — never call `.is_valid()` manually inside a view handler.

---

## Git

- PR target: `main`
- Never force-push `main`
