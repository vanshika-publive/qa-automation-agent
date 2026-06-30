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

function mostCommonEnvironmentId(environmentIdLists: string[][]): string | null {
  const counts = new Map<string, number>();
  for (const ids of environmentIdLists) {
    const first = ids[0];
    if (!first) continue;
    counts.set(first, (counts.get(first) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [id, count] of counts) {
    if (count > bestCount) { best = id; bestCount = count; }
  }
  return best;
}

export function useRunAllCollections() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: async (collections: Collection[]): Promise<BatchEntry[]> => {
      const entries: BatchEntry[] = await Promise.all(
        collections.map(async (col): Promise<BatchEntry> => {
          if (col.testCount === 0) {
            return { collectionId: col.id, collectionName: col.name, executionId: null, launchStatus: 'skipped' };
          }

          const testsRes = await collectionsService.getTests(col.id);
          const tests = testsRes.data ?? [];
          const envId = mostCommonEnvironmentId(tests.map((t) => t.environmentIds));

          if (!envId) {
            return { collectionId: col.id, collectionName: col.name, executionId: null, launchStatus: 'skipped' };
          }

          try {
            const res = await collectionsService.runAllSpecs(col.id, envId);
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
