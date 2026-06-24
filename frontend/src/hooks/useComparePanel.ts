import { useQuery } from '@tanstack/react-query';
import { executionsService } from '../services/executions';

export function useComparePanel(idA: string, idB: string) {
  const { data: dataA, isLoading: loadingA } = useQuery({
    queryKey: ['exec-steps', idA],
    queryFn: () => executionsService.getSteps(idA),
    staleTime: 30_000,
  });

  const { data: dataB, isLoading: loadingB } = useQuery({
    queryKey: ['exec-steps', idB],
    queryFn: () => executionsService.getSteps(idB),
    staleTime: 30_000,
  });

  return {
    stepsA: dataA?.data ?? [],
    stepsB: dataB?.data ?? [],
    isLoading: loadingA || loadingB,
  };
}
