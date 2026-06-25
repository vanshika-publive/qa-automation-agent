import { useQuery } from '@tanstack/react-query';
import { executionsService } from '../services/executions';
import type { Execution } from '../types';

export function useTestExecutionHistory(testId: string, expandedExecId: string | null) {
  const execsQ = useQuery({
    queryKey: ['test-executions', testId],
    queryFn: () => executionsService.getAll({ testId }),
    staleTime: 10_000,
  });

  const allRuns: Execution[] = execsQ.data?.data ?? [];
  const openId = expandedExecId ?? allRuns[0]?.id ?? null;
  const selectedRun = allRuns.find((e) => e.id === openId) ?? null;

  const detailQ = useQuery({
    queryKey: ['execution-detail', openId],
    queryFn: () => executionsService.getDetail(openId!),
    enabled: !!openId,
    staleTime: 10_000,
    refetchInterval: selectedRun?.status === 'running' ? 2000 : false,
  });

  const resultsQ = useQuery({
    queryKey: ['execution-tests', openId],
    queryFn: () => executionsService.getTestResults(openId!),
    enabled: !!openId,
    staleTime: 10_000,
  });

  return {
    allRuns,
    openId,
    isLoadingRuns: execsQ.isLoading,
    steps: detailQ.data?.data?.steps ?? [],
    isLoadingDetail: detailQ.isLoading,
    testResults: resultsQ.data?.data ?? [],
  };
}
