import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { executionsService } from '../services/executions';

export function useExecutionDetail(id: string) {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const detailQ = useQuery({
    queryKey: ['execution', id],
    queryFn: () => executionsService.getDetail(id),
    refetchInterval: (query) => {
      const s = query.state.data?.data?.status;
      return s === 'running' || s === 'queued' ? 2000 : false;
    },
    enabled: !!id,
  });

  const exec = detailQ.data?.data;

  const resultsQ = useQuery({
    queryKey: ['execution', id, 'tests'],
    queryFn: () => executionsService.getTestResults(id),
    enabled: !!exec,
    refetchInterval: (query) => (query.state.data?.pending ? 2000 : false),
  });

  const filesQ = useQuery({
    queryKey: ['execution', id, 'files'],
    queryFn: () => executionsService.getFiles(id),
    enabled: !!exec,
    staleTime: Infinity,
  });

  const historyQ = useQuery({
    queryKey: ['executions', { testId: exec?.testId }],
    queryFn: () => executionsService.getAll({ testId: exec!.testId, pageSize: 50 }),
    enabled: !!exec?.testId,
  });

  const retryMutation = useMutation({
    mutationFn: () =>
      executionsService.retry({ testId: exec!.testId, environmentId: exec!.environmentId }),
    onSuccess: (res) => {
      const executionId = res.data?.executionId;
      qc.invalidateQueries({ queryKey: ['executions'] });
      if (executionId) navigate(`/executions/${executionId}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (executionId: string) => executionsService.delete(executionId),
    onSuccess: (_res, executionId) => {
      qc.invalidateQueries({ queryKey: ['executions'] });
      if (executionId === id) navigate('/executions');
    },
  });

  return {
    exec,
    steps: exec?.steps ?? [],
    testResults: resultsQ.data?.data ?? [],
    testResultsPending: resultsQ.data?.pending ?? (exec?.status === 'running'),
    files: filesQ.data?.data ?? null,
    history: historyQ.data?.data ?? [],
    isLoading: detailQ.isLoading,
    isError: detailQ.isError,
    retryMutation,
    deleteMutation,
  };
}
