# CLAUDE.md — Coding Standards & Architecture

**Reference doc:** https://production-code-docs.vercel.app/
This is the team's canonical architecture guide. Every new file must conform to it.

---

## Repository structure

```
automation-agent-2/
├── frontend/      # React + Vite + TypeScript dashboard
├── backend/       # Django + DRF API server
└── data/          # Test specs, session data, pipeline artifacts
```

---

## Frontend architecture — 3 layers (non-negotiable)

All React code follows a strict Services → Hooks → Pages pattern. No exceptions.

```
frontend/src/
├── services/      # Layer 1 — data (pure API calls, no state)
├── hooks/         # Layer 2 — logic (queries, mutations, derived state)
├── pages/         # Layer 3 — presentation (thin, renders only)
├── components/    # Shared UI primitives
├── api/           # api client (api.get/post/put/del)
├── types.ts       # Shared TypeScript types
└── utils/         # Pure helpers (formatters, status maps)
```

### Layer 1 — Services (`src/services/`)

- Pure functions that call `api.get / api.post / api.put / api.del`
- No `useState`, no `useQuery`, no side effects
- One file per resource: `collections.ts`, `tests.ts`, `executions.ts`, `environments.ts`, `specs.ts`
- Every function returns a typed `ApiResponse<T>` or equivalent

```ts
// Good
export const collectionsService = {
  getAll: () => api.get<ApiResponse<Collection[]>>('/collections'),
  create: (name: string) => api.post<ApiResponse<Collection>>('/collections', { name }),
};

// Bad — never call api.* from a component or page
```

### Layer 2 — Hooks (`src/hooks/`)

- All `useQuery` / `useMutation` / `useQueryClient` calls live here
- One hook per domain concern: `useCollections`, `useCollectionTests`, `useEnvironments`, `useExecutions`
- Hooks own all server state, derived state, filter state, and mutation logic
- Return a flat object with everything the page needs

```ts
// Good
export function useCollections() {
  const query = useQuery({ queryKey: ['collections'], queryFn: collectionsService.getAll });
  const createMutation = useMutation({ ... });
  return { collections, filteredCollections, isLoading, createMutation, ... };
}

// Bad — never write useQuery directly in a page
```

### Layer 3 — Pages (`src/pages/`)

- Call one or two hooks, destructure what they need, render JSX
- Own only ephemeral UI state: `modalOpen`, `selectedId`, `inputValue`
- No `api.*` calls, no raw `useQuery`, no business logic

```tsx
// Good
export default function Collections() {
  const { filteredCollections, createMutation } = useCollections();
  const { tests, deleteTestMutation } = useCollectionTests(selectedColId);
  return ( ... );
}

// Bad — 200-line useEffect soup in a page file
```

---

## React Query conventions

- Query keys: `['resource']`, `['resource', id]`, `['resource', 'scope', filters]`
- `invalidateQueries` on mutation success — always via the hook's `onSuccess`
- `refetchInterval` for polling only on actively running/queued executions
- `enabled` guards on queries that depend on a selected ID

---

## API response envelope

All backend endpoints return `{ data: T | null, error: string | null }` (typed as `ApiResponse<T>`).
Always destructure `.data` before using — never assume the top-level response is the payload.

---

## Backend

- Django + DRF at `backend/`
- Run: `python manage.py runserver` from `backend/`
- Env vars: `BACKEND_ROOT` (Python path injection), `PLAYWRIGHT_PROJECT_ROOT` (→ `data/`)
- MFA sessions expire ~24 h — re-run `capture_session.py` to refresh

---

## Git

- Active branch for frontend work: `frontend-changes`
- PR target: `main`
- Never force-push `main`
