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
    onSuccess: (res) => {
      // Jump straight to the run's detail page and flag it to auto-open the live
      // stream (honored there only when live-view is enabled). Fall back to the
      // list if the backend didn't return an id.
      const executionId = res.data?.executionId;
      if (executionId) navigate(`/executions/${executionId}`, { state: { autoLive: true } });
      else navigate('/executions');
    },
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
