import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FilterState, DEFAULT_FILTERS } from '../components/FilterDrawer';
import { executionsService } from '../services/executions';
import { collectionsService } from '../services/collections';
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
  const [selectedIds,    setSelectedIds]     = useState<Set<string>>(new Set());
  const [expandedId,     setExpandedId]      = useState<string | null>(null);
  const [retryingId,     setRetryingId]      = useState<string | null>(null);
  const [appliedFilters, setAppliedFilters]  = useState<FilterState>(DEFAULT_FILTERS);
  const [now,            setNow]             = useState(Date.now());

  // Level 0: collections list (for filter chips)
  const collectionsQuery = useQuery({
    queryKey: ['collections'],
    queryFn: collectionsService.getAll,
  });

  // Level 1: filtered + paginated table
  const tableExecsQuery = useQuery({
    queryKey: ['executions', 'table', appliedFilters, tablePage],
    queryFn: () => executionsService.getAll({
      collectionId: appliedFilters.collectionId || undefined,
      status:       appliedFilters.status || undefined,
      from:         appliedFilters.from || undefined,
      to:           appliedFilters.to || undefined,
      page:         tablePage,
      pageSize:     TABLE_PAGE_SIZE,
    }),
    enabled: !selectedColId && !selectedTestId,
    refetchInterval: (q) => {
      const data = q.state.data?.data ?? [];
      return data.some((e) => e.status === 'running' || e.status === 'queued') ? 5000 : false;
    },
  });

  // Level 2: collection-scoped executions for test-card indicators
  const colExecsQuery = useQuery({
    queryKey: ['executions', 'col', selectedColId],
    queryFn: () => executionsService.getAll({ collectionId: selectedColId!, pageSize: 100 }),
    enabled: !!selectedColId && !selectedTestId,
    refetchInterval: (q) => {
      const data = q.state.data?.data ?? [];
      return data.some((e) => e.status === 'running') ? 3000 : false;
    },
  });

  // Level 2: tests within selected collection
  const testsQuery = useQuery({
    queryKey: ['tests', selectedColId],
    queryFn: () => collectionsService.getTests(selectedColId!),
    enabled: !!selectedColId,
  });

  // Level 3: runs for specific test
  const testExecsQuery = useQuery({
    queryKey: ['executions', 'test', selectedTestId],
    queryFn: () => executionsService.getAll({ testId: selectedTestId!, pageSize: 20 }),
    enabled: !!selectedTestId,
    refetchInterval: (q) => {
      const data = q.state.data?.data ?? [];
      return data.some((e) => e.status === 'running') ? 3000 : false;
    },
  });

  // Derived data
  const collections     = collectionsQuery.data?.data ?? [];
  const tableExecs      = tableExecsQuery.data?.data ?? [];
  const tablePagination = tableExecsQuery.data?.pagination;
  const colExecs        = colExecsQuery.data?.data ?? [];
  const tests           = testsQuery.data?.data ?? [];
  const testExecs       = testExecsQuery.data?.data ?? [];

  const hasRunning = useMemo(
    () => tableExecs.some((e) => e.status === 'running'),
    [tableExecs],
  );

  // Live timer for running execution durations
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
    const ids = Array.from(selectedIds).slice(0, 2);
    return ids.map((id) => tableExecs.find((e) => e.id === id)).filter(Boolean) as Execution[];
  }, [selectedIds, tableExecs]);

  // Client-side pagination for level 3 run list
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

  // Mutations
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

  // Filter actions
  function applyFilters(f: FilterState) { setAppliedFilters(f); setTablePage(1); }
  function clearFilters() { setAppliedFilters(DEFAULT_FILTERS); setTablePage(1); }
  function removeFilter(key: keyof FilterState | 'dateRange') {
    setAppliedFilters((f) => {
      if (key === 'dateRange') return { ...f, from: '', to: '' };
      return { ...f, [key]: '' };
    });
    setTablePage(1);
  }

  // Selection actions
  function toggleRow(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function toggleAll(ids: string[]) {
    const allChecked = ids.length > 0 && ids.every((id) => selectedIds.has(id));
    setSelectedIds(allChecked ? new Set() : new Set(ids));
  }

  return {
    // Data
    collections,
    tableExecs, tablePagination,
    colExecs, execsByTestId,
    tests, testExecs,
    runListSlice, runListTotalPages,
    compareExecutions,
    selectedTestName,
    // Loading states
    isLoadingTable: tableExecsQuery.isLoading || collectionsQuery.isLoading,
    isLoadingTests: testsQuery.isLoading,
    isLoadingTestExecs: testExecsQuery.isLoading,
    // Pagination
    tablePage, setTablePage,
    runListPage, setRunListPage,
    // Selection
    selectedIds, toggleRow, toggleAll,
    // Filters
    appliedFilters, activeFilterCount,
    applyFilters, clearFilters, removeFilter,
    // State
    expandedId, setExpandedId,
    retryingId,
    now,
    // Mutations
    deleteMutation,
    retryMutation,
  };
}
