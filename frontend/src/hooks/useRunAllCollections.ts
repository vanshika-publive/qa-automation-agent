import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { collectionsService } from '../services/collections';
import { Collection } from '../types';

interface BatchEntry {
  collectionId: string;
  collectionName: string;
  executionId: string | null;
  launchStatus: 'launched' | 'skipped' | 'failed';
}

interface RunAllArgs {
  collections: Collection[];
  environmentId: string;
}

export function useRunAllCollections() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: async ({ collections, environmentId }: RunAllArgs): Promise<BatchEntry[]> => {
      const entries: BatchEntry[] = await Promise.all(
        collections.map(async (col): Promise<BatchEntry> => {
          if (col.testCount === 0) {
            return { collectionId: col.id, collectionName: col.name, executionId: null, launchStatus: 'skipped' };
          }

          try {
            const res = await collectionsService.runAllSpecs(col.id, environmentId);
            const executionId = res.data?.executionId ?? null;
            return executionId
              ? { collectionId: col.id, collectionName: col.name, executionId, launchStatus: 'launched' }
              : { collectionId: col.id, collectionName: col.name, executionId: null, launchStatus: 'failed' };
          } catch {
            return { collectionId: col.id, collectionName: col.name, executionId: null, launchStatus: 'failed' };
          }
        }),
      );

      return entries;
    },
    onSuccess: (entries) => {
      const ids = entries.map((e) => e.executionId ?? '').join(',');
      const collections = entries.map((e) => e.collectionId).join(',');
      const names = entries.map((e) => encodeURIComponent(e.collectionName)).join(',');
      const statuses = entries.map((e) => e.launchStatus).join(',');
      navigate(`/executions/batch?ids=${ids}&collections=${collections}&names=${names}&statuses=${statuses}`);
    },
  });
}
