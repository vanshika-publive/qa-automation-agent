import { useEnvironments } from './useEnvironments';

export function useActiveEnvironments() {
  const { environments, isLoading } = useEnvironments();
  return {
    environments: environments.filter((e) => e.isActive),
    isLoading,
  };
}
