import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiResponse, Collection, Test, Execution } from '../types';
import ComparePanel from '../components/ComparePanel';
import ExpandedTestResults, { StatusPill } from '../components/ExpandedTestResults';
import RunSuiteModal from '../components/RunSuiteModal';
import FilterDrawer, { FilterState, DEFAULT_FILTERS, STATUS_OPTIONS } from '../components/FilterDrawer';
import PaginationBar from '../components/PaginationBar';
import { formatDuration, fmtDatetime, fmtDate, fmtMSS, relTime } from '../utils/formatters';
import { ACCENTS, STATUS_BG } from '../utils/status';
import LogViewerModal from '../components/LogViewerModal';

// Page-local types

interface Pagination { page: number; pageSize: number; total: number; totalPages: number }
interface PaginatedExecs { data: Execution[]; pagination: Pagination; error: string | null }

// Constants

const RUN_LIST_PAGE_SIZE = 10;
const TABLE_PAGE_SIZE    = 20;

// FilterBar

function FilterBar({
  applied,
  activeCount,
  onOpen,
  onClear,
  onRemove,
  collections,
}: {
  applied: FilterState;
  activeCount: number;
  onOpen: () => void;
  onClear: () => void;
  onRemove: (key: keyof FilterState | 'dateRange') => void;
  collections: Collection[];
}) {
  const chipCls = 'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20';

  const collectionName = collections.find((c) => c.id === applied.collectionId)?.name;
  const statusLabel = STATUS_OPTIONS.find((o) => o.value === applied.status && o.value !== '')?.label;
  const hasDateRange = applied.from || applied.to;
  const dateRangeLabel = [
    applied.from ? fmtDate(`${applied.from}T12:00:00Z`) : null,
    applied.to   ? fmtDate(`${applied.to}T12:00:00Z`)   : null,
  ].filter(Boolean).join(' – ');

  return (
    <div className="flex items-center gap-2 flex-wrap mb-5">
      {/* Active filter chips */}
      {collectionName && (
        <span className={chipCls}>
          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>folder</span>
          {collectionName}
          <button onClick={() => onRemove('collectionId')} className="hover:text-primary/60 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
          </button>
        </span>
      )}
      {statusLabel && (
        <span className={chipCls}>
          {statusLabel}
          <button onClick={() => onRemove('status')} className="hover:text-primary/60 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
          </button>
        </span>
      )}
      {hasDateRange && (
        <span className={chipCls}>
          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>calendar_today</span>
          {dateRangeLabel}
          <button onClick={() => onRemove('dateRange')} className="hover:text-primary/60 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
          </button>
        </span>
      )}

      {activeCount > 0 && (
        <button
          onClick={onClear}
          className="text-xs text-text-secondary hover:text-error transition-colors"
        >
          Clear all
        </button>
      )}

      {/* Filter button — right-aligned */}
      <button
        onClick={onOpen}
        className={`ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
          activeCount > 0
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border-subtle text-text-secondary hover:bg-surface-muted'
        }`}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>filter_list</span>
        Filters
        {activeCount > 0 && (
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white text-[10px] font-bold leading-none">
            {activeCount}
          </span>
        )}
      </button>
    </div>
  );
}

// Skeleton

function FolderCardSkeleton() {
  return (
    <div className="relative pt-3 animate-pulse">
      <div className="absolute top-0 left-5 h-[13px] w-[72px] rounded-t-lg bg-surface-muted" />
      <div className="rounded-2xl border border-border-subtle bg-surface-muted h-36" />
    </div>
  );
}

// Main

export default function Executions() {
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();

  const [expandedId,     setExpandedId]     = useState<string | null>(null);
  const [runModal,       setRunModal]        = useState(false);
  const [runListPage,    setRunListPage]     = useState(0);          // level 3: client-side pagination
  const [tablePage,      setTablePage]       = useState(1);          // level 1: server-side pagination
  const [retryingId,     setRetryingId]      = useState<string | null>(null);
  const [selectedIds,    setSelectedIds]     = useState<Set<string>>(new Set());
  const [compareOpen,    setCompareOpen]     = useState(false);
  const [filterOpen,     setFilterOpen]      = useState(false);
  const [appliedFilters, setAppliedFilters]  = useState<FilterState>(DEFAULT_FILTERS);
  const [now,            setNow]             = useState(Date.now());
  const [logExec,        setLogExec]         = useState<Execution | null>(null);

  const selectedColId  = searchParams.get('col');
  const selectedTestId = searchParams.get('test');

  // Queries

  const collectionsQ = useQuery({
    queryKey: ['collections'],
    queryFn: () => api.get<ApiResponse<Collection[]>>('/collections'),
  });

  // Level 1: filtered + paginated executions for the main table.
  const tableExecsQ = useQuery({
    queryKey: ['executions', 'table', appliedFilters, tablePage],
    queryFn: () => {
      const qs = new URLSearchParams();
      if (appliedFilters.collectionId) qs.set('collection_id', appliedFilters.collectionId);
      if (appliedFilters.status)       qs.set('status', appliedFilters.status);
      if (appliedFilters.from)         qs.set('from', appliedFilters.from);
      if (appliedFilters.to)           qs.set('to', appliedFilters.to);
      qs.set('page', String(tablePage));
      qs.set('pageSize', String(TABLE_PAGE_SIZE));
      return api.get<PaginatedExecs>(`/executions?${qs}`);
    },
    enabled: !selectedColId && !selectedTestId,
    refetchInterval: (q) => {
      const data = q.state.data?.data ?? [];
      return data.some((e) => e.status === 'running' || e.status === 'queued') ? 5000 : false;
    },
  });

  // Level 2: collection-scoped executions for test-card status indicators.
  const colExecsQ = useQuery({
    queryKey: ['executions', 'col', selectedColId],
    queryFn: () => api.get<PaginatedExecs>(`/executions?collection_id=${selectedColId}&pageSize=100`),
    enabled: !!selectedColId && !selectedTestId,
    refetchInterval: (q) => {
      const data = q.state.data?.data ?? [];
      return data.some((e) => e.status === 'running') ? 3000 : false;
    },
  });

  // Level 2: tests within the selected collection.
  const testsQ = useQuery({
    queryKey: ['tests', selectedColId],
    queryFn: () => api.get<ApiResponse<Test[]>>(`/collections/${selectedColId}/tests`),
    enabled: !!selectedColId,
  });

  // Level 3: runs for a specific test.
  const testExecsQ = useQuery({
    queryKey: ['executions', 'test', selectedTestId],
    queryFn: () => api.get<PaginatedExecs>(`/executions?testId=${selectedTestId}&pageSize=20`),
    enabled: !!selectedTestId,
    refetchInterval: (q) => {
      const data = q.state.data?.data ?? [];
      return data.some((e) => e.status === 'running') ? 3000 : false;
    },
  });

  // Derived data

  const collections    = collectionsQ.data?.data ?? [];
  const tableExecs     = tableExecsQ.data?.data ?? [];
  const tablePagination = tableExecsQ.data?.pagination;
  const colExecs       = colExecsQ.data?.data ?? [];
  const tests          = testsQ.data?.data ?? [];
  const testExecs      = testExecsQ.data?.data ?? [];

  const hasRunning = useMemo(
    () => tableExecs.some((e) => e.status === 'running'),
    [tableExecs],
  );

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

  const selectedCollection = collections.find((c) => c.id === selectedColId);

  // Level 3: client-side pagination within the loaded test runs.
  const runListTotalPages = Math.ceil(testExecs.length / RUN_LIST_PAGE_SIZE);
  const runListSlice = testExecs.slice(runListPage * RUN_LIST_PAGE_SIZE, (runListPage + 1) * RUN_LIST_PAGE_SIZE);
  if (runListPage > 0 && runListPage >= runListTotalPages) setRunListPage(0);

  // Filter helpers.
  const activeFilterCount = [
    appliedFilters.collectionId,
    appliedFilters.status,
    appliedFilters.from || appliedFilters.to,
  ].filter(Boolean).length;

  function applyFilters(f: FilterState) {
    setAppliedFilters(f);
    setTablePage(1);
  }

  function clearFilters() {
    setAppliedFilters(DEFAULT_FILTERS);
    setTablePage(1);
  }

  function removeFilter(key: keyof FilterState | 'dateRange') {
    setAppliedFilters((f) => {
      if (key === 'dateRange') return { ...f, from: '', to: '' };
      return { ...f, [key]: '' };
    });
    setTablePage(1);
  }

  // Mutations

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.del<ApiResponse<{ id: string }>>(`/executions/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['executions'] });
      setExpandedId(null);
    },
  });

  const retryMut = useMutation({
    mutationFn: (exec: Execution) =>
      api.post<ApiResponse<{ executionId: string }>>(`/executions/tests/${exec.testId}/run`, { environmentId: exec.environmentId }),
    onMutate: (exec) => setRetryingId(exec.id),
    onSettled: () => setRetryingId(null),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executions'] }),
  });

  // Navigation

  function goBack() {
    setExpandedId(null);
    setRunListPage(0);
    if (selectedTestId && selectedColId) {
      setSearchParams({ col: selectedColId });
    } else {
      setSearchParams({});
    }
  }

  // Header

  const selectedTestName =
    tests.find((t) => t.id === selectedTestId)?.name ??
    testExecs.find((e) => e.testId === selectedTestId)?.testName ??
    'Test';

  function renderHeader() {
    const backBtn = (
      <button onClick={goBack} className="w-9 h-9 flex items-center justify-center rounded-xl border border-border-subtle hover:bg-surface-muted transition-colors">
        <span className="material-symbols-outlined text-text-secondary" style={{ fontSize: 18 }}>arrow_back</span>
      </button>
    );

    if (selectedTestId) {
      return (
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            {backBtn}
            <div>
              <nav className="flex items-center gap-1 text-xs text-text-secondary mb-0.5">
                <button onClick={() => setSearchParams({})} className="hover:text-primary transition-colors">Collections</button>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
                {selectedCollection && (
                  <>
                    <button onClick={() => setSearchParams({ col: selectedColId! })} className="hover:text-primary transition-colors">{selectedCollection.name}</button>
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
                  </>
                )}
                <span className="text-text-primary font-medium">{selectedTestName}</span>
              </nav>
              <h1 className="text-xl font-bold text-text-primary">{selectedTestName}</h1>
            </div>
          </div>
          <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0">
            <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1' }}>play_arrow</span>
            Run Again
          </button>
        </div>
      );
    }

    if (selectedColId && selectedCollection) {
      return (
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            {backBtn}
            <div>
              <nav className="flex items-center gap-1 text-xs text-text-secondary mb-0.5">
                <button onClick={() => setSearchParams({})} className="hover:text-primary transition-colors">Collections</button>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
                <span className="text-text-primary font-medium">{selectedCollection.name}</span>
              </nav>
              <h1 className="text-xl font-bold text-text-primary">{selectedCollection.name}</h1>
            </div>
          </div>
          <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0">
            <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1' }}>play_arrow</span>
            Run Suite
          </button>
        </div>
      );
    }

    const total = tablePagination?.total ?? 0;
    return (
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Executions</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {total > 0 ? `${total} run${total !== 1 ? 's' : ''}${activeFilterCount > 0 ? ' matching filters' : ' across all collections'}` : 'No executions yet'}
          </p>
        </div>
        <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0">
          <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1' }}>play_arrow</span>
          Run Suite
        </button>
      </div>
    );
  }

  // Level 3: run list

  function renderRunList() {
    if (testExecsQ.isLoading) {
      return (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        </div>
      );
    }

    if (testExecs.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 28, fontVariationSettings: '"FILL" 1' }}>play_circle</span>
          </div>
          <h2 className="text-base font-semibold text-text-primary mb-1.5">No runs yet</h2>
          <p className="text-sm text-text-secondary max-w-xs mb-5">Run this test to see execution history here.</p>
          <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-primary/90 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1' }}>play_arrow</span>
            Run Now
          </button>
        </div>
      );
    }

    const COL_COUNT = 7;

    return (
      <div className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-surface-muted border-b border-border-subtle">
              <th className="text-left py-3 pl-5 pr-4 text-xs font-semibold uppercase tracking-wider text-text-secondary w-[90px]">Run</th>
              <th className="text-left py-3 pr-4 text-xs font-semibold uppercase tracking-wider text-text-secondary w-[130px]">Status</th>
              <th className="text-left py-3 pr-4 text-xs font-semibold uppercase tracking-wider text-text-secondary w-[80px]">Tests</th>
              <th className="text-left py-3 pr-4 text-xs font-semibold uppercase tracking-wider text-text-secondary w-[100px]">Duration</th>
              <th className="text-left py-3 pr-4 text-xs font-semibold uppercase tracking-wider text-text-secondary w-[180px]">Environment</th>
              <th className="text-left py-3 pr-4 text-xs font-semibold uppercase tracking-wider text-text-secondary">Started</th>
              <th className="text-left py-3 pr-5 text-xs font-semibold uppercase tracking-wider text-text-secondary w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {runListSlice.flatMap((exec, pageIdx) => {
              const globalIdx = runListPage * RUN_LIST_PAGE_SIZE + pageIdx;
              const runNumber = testExecs.length - globalIdx;
              const isExpanded = expandedId === exec.id;
              return [
                <tr
                  key={exec.id}
                  onClick={() => setExpandedId(isExpanded ? null : exec.id)}
                  className={`cursor-pointer transition-colors ${isExpanded ? 'bg-primary/5' : 'hover:bg-surface-muted'}`}
                >
                  <td className="py-4 pl-5 pr-4">
                    <span className="font-mono-code text-sm font-semibold text-primary">#{runNumber}</span>
                  </td>
                  <td className="py-4 pr-4"><StatusPill status={exec.status} /></td>
                  <td className="py-4 pr-4">
                    {exec.totalCount > 0 ? (
                      <span className="text-sm text-text-primary font-medium">
                        <span className="text-success">{exec.passCount}</span>
                        <span className="text-text-secondary">/{exec.totalCount}</span>
                      </span>
                    ) : <span className="text-sm text-text-secondary">—</span>}
                  </td>
                  <td className="py-4 pr-4">
                    <span className="text-sm font-mono-code text-text-secondary">{formatDuration(exec.durationMs)}</span>
                  </td>
                  <td className="py-4 pr-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-xs font-medium text-text-secondary border border-border-subtle">
                      <span className="material-symbols-outlined" style={{ fontSize: 11 }}>network_node</span>
                      {exec.environmentName}
                    </span>
                  </td>
                  <td className="py-4 pr-4">
                    <span className="text-sm text-text-secondary">{fmtDatetime(exec.startedAt)}</span>
                  </td>
                  <td className="py-4 pr-5">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); if (exec.status !== 'running' && retryingId !== exec.id) retryMut.mutate(exec); }}
                        disabled={exec.status === 'running' || retryingId === exec.id}
                        title="Retry"
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        {retryingId === exec.id
                          ? <span className="w-3.5 h-3.5 border-2 border-primary/30 border-t-primary rounded-full animate-spin block" />
                          : <span className="material-symbols-outlined" style={{ fontSize: 16 }}>replay</span>
                        }
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (exec.status !== 'running') deleteMut.mutate(exec.id); }}
                        disabled={exec.status === 'running' || deleteMut.isPending}
                        title="Delete"
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                      </button>
                      <span className={`material-symbols-outlined text-text-secondary transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} style={{ fontSize: 18 }}>
                        expand_more
                      </span>
                    </div>
                  </td>
                </tr>,
                ...(isExpanded ? [<ExpandedTestResults key={`detail-${exec.id}`} execution={exec} colSpan={COL_COUNT} />] : []),
              ];
            })}
          </tbody>
        </table>
        {runListTotalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-border-subtle bg-surface-muted">
            <span className="text-xs text-text-secondary">Page {runListPage + 1} of {runListTotalPages} · {testExecs.length} runs</span>
            <div className="flex items-center gap-2">
              <button disabled={runListPage === 0} onClick={() => setRunListPage((p) => p - 1)} className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-border-subtle rounded-lg text-text-secondary hover:bg-surface-main disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_left</span>Prev
              </button>
              {Array.from({ length: runListTotalPages }).map((_, i) => (
                <button key={i} onClick={() => setRunListPage(i)} className={`w-7 h-7 rounded-lg text-xs font-semibold transition-colors ${i === runListPage ? 'bg-primary text-white' : 'text-text-secondary hover:bg-surface-main border border-border-subtle'}`}>
                  {i + 1}
                </button>
              ))}
              <button disabled={runListPage >= runListTotalPages - 1} onClick={() => setRunListPage((p) => p + 1)} className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-border-subtle rounded-lg text-text-secondary hover:bg-surface-main disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                Next<span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Level 2: test folder cards

  function renderTestFolders() {
    if (testsQ.isLoading) {
      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <FolderCardSkeleton key={i} />)}
        </div>
      );
    }

    if (tests.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <span className="material-symbols-outlined text-border-subtle mb-3" style={{ fontSize: 48 }}>folder_open</span>
          <p className="text-text-primary font-medium">No tests in this folder</p>
          <p className="text-sm text-text-secondary mt-1">Add tests from the Folders page</p>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {tests.map((test, idx) => {
          const accent = ACCENTS[idx % ACCENTS.length];
          const execs = execsByTestId.get(test.id) ?? [];
          const lastExec = execs[0] ?? null;
          const runCount = execs.length;

          const colors = lastExec ? STATUS_BG[lastExec.status] : accent;

          return (
            <div
              key={test.id}
              className="group relative pt-3 cursor-pointer"
              onClick={() => {
                setRunListPage(0);
                setExpandedId(null);
                setSearchParams({ col: selectedColId!, test: test.id });
              }}
            >
              <div className={`absolute top-0 left-5 h-[13px] w-[72px] rounded-t-lg border border-b-0 transition-all ${colors.bg} border-border-subtle group-hover:border-primary/30`} />
              <div className="rounded-2xl border border-border-subtle p-5 bg-surface-main hover:border-primary/30 hover:shadow-sm transition-all">
                <div className="flex items-start justify-between mb-4">
                  <div className={`w-11 h-11 ${colors.bg} rounded-xl flex items-center justify-center flex-shrink-0`}>
                    <span className={`material-symbols-outlined ${colors.icon}`} style={{ fontSize: 22, fontVariationSettings: '"FILL" 1' }}>
                      {lastExec ? 'folder' : 'folder_open'}
                    </span>
                  </div>
                  {lastExec && <StatusPill status={lastExec.status} />}
                </div>
                <div className="font-semibold text-text-primary text-sm mb-1 leading-snug line-clamp-2">{test.name}</div>
                <div className="text-xs text-text-secondary">
                  {runCount > 0
                    ? `${runCount} run${runCount !== 1 ? 's' : ''} · Last ${relTime(lastExec!.startedAt)}`
                    : 'Never run'
                  }
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Level 1: main executions table

  function renderCollectionFolders() {
    const isLoading = tableExecsQ.isLoading || collectionsQ.isLoading;

    const liveRows    = tableExecs.filter((e) => e.status === 'running' || e.status === 'queued');
    const historyRows = tableExecs.filter((e) => e.status === 'passed'  || e.status === 'failed');

    const allVisible = [...liveRows, ...historyRows];
    const allChecked = allVisible.length > 0 && allVisible.every((e) => selectedIds.has(e.id));
    const someChecked = allVisible.some((e) => selectedIds.has(e.id));

    function toggleAll() {
      if (allChecked) {
        setSelectedIds(new Set());
      } else {
        setSelectedIds(new Set(allVisible.map((e) => e.id)));
      }
    }

    function toggleRow(id: string) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
      });
    }

    function renderRow(exec: Execution) {
      const isSelected = selectedIds.has(exec.id);
      const isRunning  = exec.status === 'running';
      const progressPct = exec.totalCount > 0 ? (exec.passCount / exec.totalCount) * 100 : 0;
      const elapsedMs   = isRunning ? now - new Date(exec.startedAt).getTime() : exec.durationMs;

      return (
        <tr
          key={exec.id}
          className={`border-b border-border-subtle transition-colors last:border-b-0 ${
            isSelected ? 'bg-[#3525cd]/[0.08]' : 'hover:bg-surface-muted/40'
          }`}
        >
          <td className="px-[14px] py-[11px]" style={{ width: 36 }}>
            <input type="checkbox" checked={isSelected} onChange={() => toggleRow(exec.id)} className="accent-primary" />
          </td>

          <td className="px-[14px] py-[11px]">
            <div className="flex items-start gap-2">
              {isRunning && (
                <span className="mt-[3px] w-1.5 h-1.5 rounded-full bg-primary animate-pulse flex-shrink-0 inline-block" />
              )}
              <div>
                <div className="font-medium text-sm text-text-primary">
                  {exec.collectionName} · #{exec.runNumber}
                </div>
                <div className="text-sm text-text-secondary mt-0.5">
                  {relTime(exec.startedAt)} · {exec.environmentUrl}
                </div>
                {isRunning && (
                  <div className="mt-1.5 w-32 h-1 rounded overflow-hidden bg-surface-muted" style={{ borderRadius: 2 }}>
                    <div className="h-full" style={{ width: `${progressPct}%`, backgroundColor: '#3525cd', borderRadius: 2 }} />
                  </div>
                )}
              </div>
            </div>
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 140 }}>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-muted border border-border-subtle text-xs font-medium text-text-secondary max-w-[120px] truncate">
              <span className="material-symbols-outlined flex-shrink-0" style={{ fontSize: 12 }}>folder</span>
              <span className="truncate">{exec.collectionName}</span>
            </span>
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 100 }}>
            <StatusPill status={exec.status} />
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 110 }}>
            {exec.status === 'queued' ? (
              <span className="text-sm text-text-secondary font-mono-code">—</span>
            ) : (
              <div>
                <div className="flex w-[60px] overflow-hidden mb-1" style={{ height: 4, borderRadius: 2 }}>
                  <div className="bg-success" style={{ width: `${exec.totalCount > 0 ? (exec.passCount / exec.totalCount) * 100 : 0}%` }} />
                  <div className="bg-error"   style={{ width: `${exec.totalCount > 0 ? (exec.failCount  / exec.totalCount) * 100 : 0}%` }} />
                  <div className="flex-1 bg-surface-muted" />
                </div>
                <span className="text-sm font-mono-code text-text-secondary tabular-nums">{exec.passCount}/{exec.totalCount}</span>
              </div>
            )}
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 72 }}>
            <span className="text-sm font-mono-code text-text-secondary tabular-nums">{fmtMSS(elapsedMs)}</span>
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 96 }}>
            <div className="flex items-center justify-end gap-1">
              {(exec.status === 'passed' || exec.status === 'failed') && (
                <>
                  {exec.reportDir && exec.totalCount > 0 && (
                    <a href={`/reports/${exec.reportDir}/html/index.html`} target="_blank" rel="noopener noreferrer" title="View report"
                      className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 border border-transparent hover:border-border-subtle transition-colors">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>assessment</span>
                    </a>
                  )}
                  <button title="Re-run" onClick={() => retryMut.mutate(exec)} disabled={retryMut.isPending}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 border border-transparent hover:border-border-subtle transition-colors disabled:opacity-40">
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>replay</span>
                  </button>
                </>
              )}
              {exec.status === 'running' && (
                <>
                  <button title="Stop"
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 border border-transparent hover:border-border-subtle transition-colors">
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>stop</span>
                  </button>
                  <button title="View log" onClick={() => setLogExec(exec)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 border border-transparent hover:border-border-subtle transition-colors">
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>terminal</span>
                  </button>
                </>
              )}
              {exec.status === 'queued' && (
                <button title="Cancel"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 border border-transparent hover:border-border-subtle transition-colors">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                </button>
              )}
              {exec.status !== 'running' && (
                <button title="Delete" onClick={() => deleteMut.mutate(exec.id)} disabled={deleteMut.isPending}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 border border-transparent hover:border-border-subtle transition-colors disabled:opacity-40">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                </button>
              )}
            </div>
          </td>
        </tr>
      );
    }

    const sectionHeaderCls = 'bg-surface-muted text-text-secondary text-[11px] font-medium uppercase tracking-wider px-[14px] py-[11px]';

    return (
      <>
        {/* Filter bar */}
        <FilterBar
          applied={appliedFilters}
          activeCount={activeFilterCount}
          onOpen={() => setFilterOpen(true)}
          onClear={clearFilters}
          onRemove={removeFilter}
          collections={collections}
        />

        {/* Compare button */}
        {selectedIds.size >= 2 && (
          <div className="flex justify-end mb-3">
            <button
              onClick={() => setCompareOpen(true)}
              className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2 text-sm font-semibold hover:bg-primary/90 transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>compare_arrows</span>
              Compare ({selectedIds.size})
            </button>
          </div>
        )}

        {/* Main table */}
        <div className="border border-border-subtle rounded-xl overflow-hidden">
          {isLoading ? (
            <div className="animate-pulse">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-14 border-b border-border-subtle bg-surface-muted/30 last:border-b-0" />
              ))}
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="bg-surface-muted border-b border-border-subtle">
                  <th className="px-[14px] py-[11px]" style={{ width: 36 }}>
                    <input
                      type="checkbox"
                      checked={allChecked}
                      ref={(el) => { if (el) el.indeterminate = someChecked && !allChecked; }}
                      onChange={toggleAll}
                      className="accent-primary"
                    />
                  </th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary">Run</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 140 }}>Collection</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 100 }}>Status</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 110 }}>Tests</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 72 }}>Duration</th>
                  <th className="px-[14px] py-[11px]" style={{ width: 96 }} />
                </tr>
              </thead>
              <tbody>
                {liveRows.length > 0 && (
                  <tr><td colSpan={7} className={sectionHeaderCls}>Live</td></tr>
                )}
                {liveRows.map(renderRow)}

                {historyRows.length > 0 && (
                  <tr><td colSpan={7} className={sectionHeaderCls}>History</td></tr>
                )}
                {historyRows.map(renderRow)}

                {tableExecs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-[14px] py-12 text-center text-sm text-text-secondary">
                      {activeFilterCount > 0
                        ? 'No executions match your filters.'
                        : 'No executions yet. Run a suite to see results here.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}

          {/* Pagination */}
          {tablePagination && (
            <PaginationBar
              page={tablePagination.page}
              totalPages={tablePagination.totalPages}
              total={tablePagination.total}
              pageSize={tablePagination.pageSize}
              onPage={(p) => { setTablePage(p); setExpandedId(null); }}
            />
          )}
        </div>

        {compareOpen && compareExecutions.length >= 2 && (
          <ComparePanel
            executionIds={compareExecutions.map((e) => e.id)}
            executions={compareExecutions}
            onClose={() => setCompareOpen(false)}
          />
        )}
      </>
    );
  }

  // Render

  return (
    <div className="p-8 max-w-7xl">
      {renderHeader()}

      {selectedTestId
        ? renderRunList()
        : selectedColId
          ? renderTestFolders()
          : renderCollectionFolders()
      }

      {runModal && (
        <RunSuiteModal
          onClose={() => setRunModal(false)}
          onRun={() => qc.invalidateQueries({ queryKey: ['executions'] })}
        />
      )}

      {/* Filter drawer — always mounted so the slide animation works */}
      <FilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        value={appliedFilters}
        onApply={applyFilters}
        collections={collections}
      />

      {logExec && (
        <LogViewerModal
          executionId={logExec.id}
          testName={`${logExec.collectionName} · ${logExec.testName}`}
          onClose={() => setLogExec(null)}
        />
      )}
    </div>
  );
}
