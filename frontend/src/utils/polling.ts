// Shared React Query `refetchInterval` helpers for execution polling.
// Single source of truth for which statuses are considered "in flight".

type QueryState<T> = { state: { data?: T } };

/** An execution is worth polling while it is still queued or running. */
export const isActiveStatus = (status?: string | null): boolean =>
  status === 'running' || status === 'queued';

/** `refetchInterval` for a query whose data is an execution list (`{ data: [...] }`). */
export const pollWhileActive =
  (intervalMs: number) =>
  (query: QueryState<{ data?: Array<{ status?: string | null }> }>): number | false =>
    (query.state.data?.data ?? []).some((e) => isActiveStatus(e.status)) ? intervalMs : false;

/** `refetchInterval` for a query whose data is a single execution (`{ data: {...} }`). */
export const pollWhileActiveDetail =
  (intervalMs: number) =>
  (query: QueryState<{ data?: { status?: string | null } | null }>): number | false =>
    isActiveStatus(query.state.data?.data?.status) ? intervalMs : false;
