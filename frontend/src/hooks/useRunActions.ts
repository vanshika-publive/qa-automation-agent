import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { collectionsService } from '../services/collections';
import { executionsService } from '../services/executions';

export function useRunSuite() {
  return useMutation({
    mutationFn: ({ collectionId, testId, environmentId }: { collectionId: string; testId: string; environmentId: string }) =>
      testId
        ? executionsService.retry({ testId, environmentId })
        : collectionsService.runAllSpecs(collectionId, environmentId),
  });
}

export function useRunTest(testId: string) {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (environmentId: string) => executionsService.retry({ testId, environmentId }),
    onSuccess: () => navigate('/executions'),
  });
}

export function useRunAll(collectionIds: string[]) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (environmentId: string) =>
      Promise.all(collectionIds.map((id) => collectionsService.runAllSpecs(id, environmentId))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['executions'] });
      navigate('/executions');
    },
  });
}
