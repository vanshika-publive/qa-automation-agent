import { useQueries } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { executionsService } from '../services/executions';
import { pollWhileActiveDetail } from '../utils/polling';

export interface BatchRow {
  collectionId: string;
  collectionName: string;
  executionId: string | null;
  launchStatus: 'launched' | 'skipped' | 'failed';
  status: 'running' | 'queued' | 'passed' | 'failed' | null;
  passCount: number;
  failCount: number;
  totalCount: number;
  isLoading: boolean;
}

export function useBatchExecutionStatus() {
  const [searchParams] = useSearchParams();

  const ids = searchParams.get('ids')?.split(',') ?? [];
  const collectionIds = searchParams.get('collections')?.split(',') ?? [];
  const names = (searchParams.get('names')?.split(',') ?? []).map((n) => decodeURIComponent(n));
  const statuses = (searchParams.get('statuses')?.split(',') ?? []) as BatchRow['launchStatus'][];

  const executionQueries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['execution', id],
      queryFn: () => executionsService.getDetail(id),
      enabled: !!id,
      refetchInterval: pollWhileActiveDetail(2000),
    })),
  });

  const rows: BatchRow[] = collectionIds.map((collectionId, i) => {
    const executionId = ids[i] || null;
    const launchStatus = statuses[i] ?? 'failed';
    const q = executionId ? executionQueries[i] : null;
    const exec = q?.data?.data;

    return {
      collectionId,
      collectionName: names[i] ?? 'Collection',
      executionId,
      launchStatus,
      status: exec?.status ?? null,
      passCount: exec?.passCount ?? 0,
      failCount: exec?.failCount ?? 0,
      totalCount: exec?.totalCount ?? 0,
      isLoading: !!q?.isLoading,
    };
  });

  const isRunning = rows.some((r) => r.status === 'running' || r.status === 'queued');
  const summary = {
    total: rows.length,
    passed: rows.filter((r) => r.status === 'passed').length,
    failed: rows.filter((r) => r.status === 'failed').length,
    running: rows.filter((r) => r.status === 'running' || r.status === 'queued').length,
    skipped: rows.filter((r) => r.launchStatus === 'skipped' || r.launchStatus === 'failed').length,
  };

  return { rows, summary, isRunning };
}
