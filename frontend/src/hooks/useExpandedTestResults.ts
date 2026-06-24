import { useQuery } from '@tanstack/react-query';
import { executionsService } from '../services/executions';
import { Execution } from '../types';

export function useExpandedTestResults(execution: Execution) {
  const resultsQuery = useQuery({
    queryKey: ['execution-tests', execution.id],
    queryFn: () => executionsService.getTestResults(execution.id),
    refetchInterval: execution.status === 'running' ? 3000 : false,
    staleTime: 0,
  });

  const tests = resultsQuery.data?.data ?? [];
  const isPending = resultsQuery.data?.pending ?? execution.status === 'running';
  const showStepDetails = execution.status === 'failed' && !resultsQuery.isLoading && tests.length === 0;

  const detailQuery = useQuery({
    queryKey: ['execution-detail', execution.id],
    queryFn: () => executionsService.getDetail(execution.id),
    enabled: showStepDetails,
    staleTime: 30_000,
  });

  return {
    tests,
    isLoading: resultsQuery.isLoading,
    isPending,
    showStepDetails,
    steps: detailQuery.data?.steps ?? [],
  };
}
