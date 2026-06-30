import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { collectionsService } from '../services/collections';
import { testsService, TestUpdatePayload } from '../services/tests';

export function useCollectionTests(collectionId: string | null) {
  const qc = useQueryClient();

  const testsQuery = useQuery({
    queryKey: ['tests', collectionId],
    queryFn: () => collectionsService.getTests(collectionId!),
    enabled: !!collectionId,
  });

  const specsQuery = useQuery({
    queryKey: ['specs', collectionId],
    queryFn: () => collectionsService.getSpecs(collectionId!),
    enabled: !!collectionId,
  });

  const deleteTestMutation = useMutation({
    mutationFn: testsService.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tests', collectionId] }),
  });

  const updateTestMutation = useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & TestUpdatePayload) =>
      testsService.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tests', collectionId] });
      qc.invalidateQueries({ queryKey: ['collections'] });
    },
  });

  const runAllSpecsMutation = useMutation({
    mutationFn: ({ environmentId }: { environmentId: string }) =>
      collectionsService.runAllSpecs(collectionId!, environmentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executions'] }),
  });

  function invalidateTests() {
    qc.invalidateQueries({ queryKey: ['tests', collectionId] });
    qc.invalidateQueries({ queryKey: ['collections'] });
  }

  return {
    tests: testsQuery.data?.data ?? [],
    specs: specsQuery.data?.data ?? [],
    isLoadingTests: testsQuery.isLoading,
    isLoadingSpecs: specsQuery.isLoading,
    deleteTestMutation,
    updateTestMutation,
    runAllSpecsMutation,
    invalidateTests,
  };
}
