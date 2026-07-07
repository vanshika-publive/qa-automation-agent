import { useEnvironments } from './useEnvironments';

/**
 * Environments narrowed to the active ones — the only set a run picker may target.
 * Reuses the shared `['environments']` query, so mounting it costs no extra fetch.
 */
export function useActiveEnvironments() {
  const { environments, isLoading } = useEnvironments();
  return {
    environments: environments.filter((e) => e.isActive),
    isLoading,
  };
}
