import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FilterState, DEFAULT_FILTERS } from '../components/FilterDrawer';
import { executionsService } from '../services/executions';
import { collectionsService } from '../services/collections';
import { pollWhileActive } from '../utils/polling';
import { useRowSelection } from './useRowSelection';
import { Execution } from '../types';

const RUN_LIST_PAGE_SIZE = 10;
const TABLE_PAGE_SIZE    = 20;

export function useExecutions(
  selectedColId: string | null,
  selectedTestId: string | null,
) {
  const qc = useQueryClient();

  const [tablePage,      setTablePage]      = useState(1);
  const [runListPage,    setRunListPage]     = useState(0);
  const selection = useRowSelection();
  const [expandedId,     setExpandedId]      = useState<string | null>(null);
  const [retryingId,     setRetryingId]      = useState<string | null>(null);
  const [stoppingId,     setStoppingId]      = useState<string | null>(null);
  const [appliedFilters, setAppliedFilters]  = useState<FilterState>(DEFAULT_FILTERS);
  const [search,         setSearchRaw]       = useState('');

  function setSearch(q: string) { setSearchRaw(q); setTablePage(1); }
  const [now,            setNow]             = useState(Date.now());

  const collectionsQuery = useQuery({
    queryKey: ['collections'],
    queryFn: collectionsService.getAll,
  });

  const tableExecsQuery = useQuery({
    queryKey: ['executions', 'table', appliedFilters, search, tablePage],
    queryFn: () => executionsService.getAll({
      collectionId: appliedFilters.collectionId || undefined,
      status:       appliedFilters.status || undefined,
      from:         appliedFilters.from || undefined,
      to:           appliedFilters.to || undefined,
      search:       search || undefined,
      page:         tablePage,
      pageSize:     TABLE_PAGE_SIZE,
    }),
    enabled: !selectedColId && !selectedTestId,
    refetchInterval: pollWhileActive(5000),
  });

  const colExecsQuery = useQuery({
    queryKey: ['executions', 'col', selectedColId],
    queryFn: () => executionsService.getAll({ collectionId: selectedColId!, pageSize: 100 }),
    enabled: !!selectedColId && !selectedTestId,
    refetchInterval: pollWhileActive(3000),
  });

  const testsQuery = useQuery({
    queryKey: ['tests', selectedColId],
    queryFn: () => collectionsService.getTests(selectedColId!),
    enabled: !!selectedColId,
  });

  const testExecsQuery = useQuery({
    queryKey: ['executions', 'test', selectedTestId],
    queryFn: () => executionsService.getAll({ testId: selectedTestId!, pageSize: 20 }),
    enabled: !!selectedTestId,
    refetchInterval: pollWhileActive(3000),
  });

  const collections     = collectionsQuery.data?.data ?? [];
  const tableExecs      = tableExecsQuery.data?.data ?? [];
  const tablePagination = tableExecsQuery.data?.pagination;
  const colExecs        = colExecsQuery.data?.data ?? [];
  const tests           = testsQuery.data?.data ?? [];
  const testExecs       = testExecsQuery.data?.data ?? [];

  const hasRunning = tableExecs.some((e) => e.status === 'running');

  useEffect(() => {
    if (!hasRunning) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [hasRunning]);

  const execsByTestId = useMemo(() => {
    const map = new Map<string, Execution[]>();
    for (const exec of colExecs) {
      if (!map.has(exec.testId)) map.set(exec.testId, []);
      map.get(exec.testId)!.push(exec);
    }
    return map;
  }, [colExecs]);

  const compareExecutions = useMemo(() => {
    const ids = Array.from(selection.selected).slice(0, 2);
    return ids.map((id) => tableExecs.find((e) => e.id === id)).filter(Boolean) as Execution[];
  }, [selection.selected, tableExecs]);

  const runListTotalPages = Math.ceil(testExecs.length / RUN_LIST_PAGE_SIZE);
  const runListSlice = testExecs.slice(
    runListPage * RUN_LIST_PAGE_SIZE,
    (runListPage + 1) * RUN_LIST_PAGE_SIZE,
  );

  const activeFilterCount = [
    appliedFilters.collectionId,
    appliedFilters.status,
    appliedFilters.from || appliedFilters.to,
  ].filter(Boolean).length;

  const selectedTestName =
    tests.find((t) => t.id === selectedTestId)?.name ??
    testExecs.find((e) => e.testId === selectedTestId)?.testName ??
    'Test';

  const deleteMutation = useMutation({
    mutationFn: executionsService.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['executions'] });
      setExpandedId(null);
    },
  });

  const retryMutation = useMutation({
    mutationFn: (exec: Execution) => executionsService.retry(exec),
    onMutate: (exec) => setRetryingId(exec.id),
    onSettled: () => setRetryingId(null),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executions'] }),
  });

  const stopMutation = useMutation({
    mutationFn: (id: string) => executionsService.stop(id),
    onMutate: (id) => setStoppingId(id),
    onSettled: () => setStoppingId(null),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executions'] }),
  });

  function applyFilters(f: FilterState) { setAppliedFilters(f); setTablePage(1); }
  function clearFilters() { setAppliedFilters(DEFAULT_FILTERS); setTablePage(1); }
  function removeFilter(key: keyof FilterState | 'dateRange') {
    setAppliedFilters((f) => {
      if (key === 'dateRange') return { ...f, from: '', to: '' };
      return { ...f, [key]: '' };
    });
    setTablePage(1);
  }

  return {
    collections,
    tableExecs, tablePagination,
    execsByTestId,
    tests, testExecs,
    runListSlice, runListTotalPages,
    compareExecutions,
    selectedTestName,
    isLoadingTable: tableExecsQuery.isLoading || collectionsQuery.isLoading,
    isLoadingTests: testsQuery.isLoading,
    isLoadingTestExecs: testExecsQuery.isLoading,
    tablePage, setTablePage,
    runListPage, setRunListPage,
    selectedIds: selection.selected,
    toggleRow: selection.toggle,
    toggleAll: selection.toggleAll,
    clearSelection: selection.clear,
    search, setSearch,
    appliedFilters, activeFilterCount,
    applyFilters, clearFilters, removeFilter,
    expandedId, setExpandedId,
    retryingId,
    stoppingId,
    now,
    deleteMutation,
    retryMutation,
    stopMutation,
  };
}
