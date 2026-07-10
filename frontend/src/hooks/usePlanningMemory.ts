import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { planningMemoryService, CorrectionPayload } from '../services/planningMemory';

/**
 * Per-test Planning Memory (navigation guidance) + the corrective-replan trigger.
 * All React Query wiring lives here; pages/components stay thin.
 */
export function usePlanningMemory(testId: string | null) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const key = ['planningMemory', testId];

  const entriesQuery = useQuery({
    queryKey: key,
    queryFn: () => planningMemoryService.list(testId!),
    enabled: !!testId,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: key });

  const createMutation = useMutation({
    mutationFn: (content: string) => planningMemoryService.create(testId!, content),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      planningMemoryService.update(testId!, id, content),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => planningMemoryService.remove(testId!, id),
    onSuccess: invalidate,
  });

  const correctionMutation = useMutation({
    mutationFn: (payload: CorrectionPayload) =>
      planningMemoryService.submitCorrection(testId!, payload),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['executions'] });
      invalidate();
      const executionId = res.data?.executionId;
      if (executionId) navigate(`/executions/${executionId}`);
    },
  });

  return {
    entries: entriesQuery.data?.data ?? [],
    isLoading: entriesQuery.isLoading,
    createMutation,
    updateMutation,
    deleteMutation,
    correctionMutation,
  };
}
