import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Execution } from '../types';
import ComparePanel from '../components/ComparePanel';
import ExpandedTestResults, { StatusPill } from '../components/ExpandedTestResults';
import RunSuiteModal from '../components/RunSuiteModal';
import FilterDrawer, { STATUS_OPTIONS } from '../components/FilterDrawer';
import PaginationBar from '../components/PaginationBar';
import { formatDuration, fmtDatetime, fmtDate, fmtMSS, relTime, fmtTableDatetime } from '../utils/formatters';
import { ACCENTS, STATUS_BG } from '../utils/status';
import LogViewerModal from '../components/LogViewerModal';
import { useExecutions } from '../hooks/useExecutions';
import {
  Folder, FolderOpen, X, Calendar, ListFilter, PlayCircle, Play,
  ChevronLeft, ChevronRight, Network, RotateCcw, Trash2, ChevronDown,
  BarChart3, Square, Terminal, ArrowLeftRight, ArrowLeft,
} from 'lucide-react';

// ── Page-local components ────────────────────────────────────────────────────

function FilterBar({
  applied,
  activeCount,
  onOpen,
  onClear,
  onRemove,
  collections,
}: {
  applied: ReturnType<typeof useExecutions>['appliedFilters'];
  activeCount: number;
  onOpen: () => void;
  onClear: () => void;
  onRemove: (key: keyof typeof applied | 'dateRange') => void;
  collections: ReturnType<typeof useExecutions>['collections'];
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
      {collectionName && (
        <span className={chipCls}>
          <Folder size={12} />
          {collectionName}
          <button onClick={() => onRemove('collectionId')} className="hover:text-primary/60 transition-colors">
            <X size={12} />
          </button>
        </span>
      )}
      {statusLabel && (
        <span className={chipCls}>
          {statusLabel}
          <button onClick={() => onRemove('status')} className="hover:text-primary/60 transition-colors">
            <X size={12} />
          </button>
        </span>
      )}
      {hasDateRange && (
        <span className={chipCls}>
          <Calendar size={12} />
          {dateRangeLabel}
          <button onClick={() => onRemove('dateRange')} className="hover:text-primary/60 transition-colors">
            <X size={12} />
          </button>
        </span>
      )}

      {activeCount > 0 && (
        <button onClick={onClear} className="text-xs text-text-secondary hover:text-error transition-colors">Clear all</button>
      )}

      <button
        onClick={onOpen}
        className={`ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
          activeCount > 0 ? 'border-primary bg-primary/10 text-primary' : 'border-border-subtle text-text-secondary hover:bg-surface-muted'
        }`}
      >
        <ListFilter size={16} />
        Filters
        {activeCount > 0 && (
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white text-[10px] font-bold leading-none">{activeCount}</span>
        )}
      </button>
    </div>
  );
}

function FolderCardSkeleton() {
  return (
    <div className="relative pt-3 animate-pulse">
      <div className="absolute top-0 left-5 h-[13px] w-[72px] rounded-t-lg bg-surface-muted" />
      <div className="rounded-2xl border border-border-subtle bg-surface-muted h-36" />
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function Executions() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [runModal,     setRunModal]     = useState(false);
  const [compareOpen,  setCompareOpen]  = useState(false);
  const [filterOpen,   setFilterOpen]   = useState(false);
  const [logExec,      setLogExec]      = useState<Execution | null>(null);

  const selectedColId  = searchParams.get('col');
  const selectedTestId = searchParams.get('test');

  const exec = useExecutions(selectedColId, selectedTestId);

  // Correct out-of-range page (happens when list shrinks)
  if (exec.runListPage > 0 && exec.runListPage >= exec.runListTotalPages) {
    exec.setRunListPage(0);
  }

  const selectedCollection = exec.collections.find((c) => c.id === selectedColId);

  function goBack() {
    exec.setExpandedId(null);
    exec.setRunListPage(0);
    if (selectedTestId && selectedColId) {
      setSearchParams({ col: selectedColId });
    } else {
      setSearchParams({});
    }
  }

  // ── Header ────────────────────────────────────────────────────────────────

  function renderHeader() {
    const backBtn = (
      <button onClick={goBack} className="w-9 h-9 flex items-center justify-center rounded-xl border border-border-subtle hover:bg-surface-muted transition-colors">
        <ArrowLeft size={18} className="text-text-secondary" />
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
                <ChevronRight size={14} />
                {selectedCollection && (
                  <>
                    <button onClick={() => setSearchParams({ col: selectedColId! })} className="hover:text-primary transition-colors">{selectedCollection.name}</button>
                    <ChevronRight size={14} />
                  </>
                )}
                <span className="text-text-primary font-medium">{exec.selectedTestName}</span>
              </nav>
              <h1 className="text-xl font-bold text-text-primary">{exec.selectedTestName}</h1>
            </div>
          </div>
          <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0">
            <Play size={16} />
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
                <ChevronRight size={14} />
                <span className="text-text-primary font-medium">{selectedCollection.name}</span>
              </nav>
              <h1 className="text-xl font-bold text-text-primary">{selectedCollection.name}</h1>
            </div>
          </div>
          <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0">
            <Play size={16} />
            Run Suite
          </button>
        </div>
      );
    }

    const total = exec.tablePagination?.total ?? 0;
    return (
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Executions</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {total > 0
              ? `${total} run${total !== 1 ? 's' : ''}${exec.activeFilterCount > 0 ? ' matching filters' : ' across all collections'}`
              : 'No executions yet'}
          </p>
        </div>
        <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0">
          <Play size={16} />
          Run Suite
        </button>
      </div>
    );
  }

  // ── Level 3: run list ────────────────────────────────────────────────────

  function renderRunList() {
    if (exec.isLoadingTestExecs) {
      return (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        </div>
      );
    }

    if (exec.testExecs.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
            <PlayCircle size={28} className="text-primary" />
          </div>
          <h2 className="text-base font-semibold text-text-primary mb-1.5">No runs yet</h2>
          <p className="text-sm text-text-secondary max-w-xs mb-5">Run this test to see execution history here.</p>
          <button onClick={() => setRunModal(true)} className="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-primary/90 transition-colors">
            <Play size={16} />
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
            {exec.runListSlice.flatMap((e, pageIdx) => {
              const globalIdx = exec.runListPage * 10 + pageIdx;
              const runNumber = exec.testExecs.length - globalIdx;
              const isExpanded = exec.expandedId === e.id;
              return [
                <tr
                  key={e.id}
                  onClick={() => exec.setExpandedId(isExpanded ? null : e.id)}
                  className={`cursor-pointer transition-colors ${isExpanded ? 'bg-primary/5' : 'hover:bg-surface-muted'}`}
                >
                  <td className="py-4 pl-5 pr-4">
                    <span className="font-mono-code text-sm font-semibold text-primary">#{runNumber}</span>
                  </td>
                  <td className="py-4 pr-4"><StatusPill status={e.status} /></td>
                  <td className="py-4 pr-4">
                    {e.totalCount > 0 ? (
                      <span className="text-sm text-text-primary font-medium">
                        <span className="text-success">{e.passCount}</span>
                        <span className="text-text-secondary">/{e.totalCount}</span>
                      </span>
                    ) : <span className="text-sm text-text-secondary">—</span>}
                  </td>
                  <td className="py-4 pr-4">
                    <span className="text-sm font-mono-code text-text-secondary">{formatDuration(e.durationMs)}</span>
                  </td>
                  <td className="py-4 pr-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-xs font-medium text-text-secondary border border-border-subtle">
                      <Network size={11} />
                      {e.environmentName}
                    </span>
                  </td>
                  <td className="py-4 pr-4">
                    <span className="text-sm text-text-secondary">{fmtDatetime(e.startedAt)}</span>
                  </td>
                  <td className="py-4 pr-5">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={(ev) => { ev.stopPropagation(); if (e.status !== 'running' && exec.retryingId !== e.id) exec.retryMutation.mutate(e); }}
                        disabled={e.status === 'running' || exec.retryingId === e.id}
                        title="Retry"
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        {exec.retryingId === e.id
                          ? <span className="w-3.5 h-3.5 border-2 border-primary/30 border-t-primary rounded-full animate-spin block" />
                          : <RotateCcw size={16} />
                        }
                      </button>
                      <button
                        onClick={(ev) => { ev.stopPropagation(); if (e.status !== 'running') exec.deleteMutation.mutate(e.id); }}
                        disabled={e.status === 'running' || exec.deleteMutation.isPending}
                        title="Delete"
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <Trash2 size={16} />
                      </button>
                      <ChevronDown size={18} className={`text-text-secondary transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                    </div>
                  </td>
                </tr>,
                ...(isExpanded ? [<ExpandedTestResults key={`detail-${e.id}`} execution={e} colSpan={COL_COUNT} />] : []),
              ];
            })}
          </tbody>
        </table>
        {exec.runListTotalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-border-subtle bg-surface-muted">
            <span className="text-xs text-text-secondary">Page {exec.runListPage + 1} of {exec.runListTotalPages} · {exec.testExecs.length} runs</span>
            <div className="flex items-center gap-2">
              <button disabled={exec.runListPage === 0} onClick={() => exec.setRunListPage((p) => p - 1)} className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-border-subtle rounded-lg text-text-secondary hover:bg-surface-main disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                <ChevronLeft size={14} />Prev
              </button>
              {Array.from({ length: exec.runListTotalPages }).map((_, i) => (
                <button key={i} onClick={() => exec.setRunListPage(i)} className={`w-7 h-7 rounded-lg text-xs font-semibold transition-colors ${i === exec.runListPage ? 'bg-primary text-white' : 'text-text-secondary hover:bg-surface-main border border-border-subtle'}`}>
                  {i + 1}
                </button>
              ))}
              <button disabled={exec.runListPage >= exec.runListTotalPages - 1} onClick={() => exec.setRunListPage((p) => p + 1)} className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-border-subtle rounded-lg text-text-secondary hover:bg-surface-main disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                Next<ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Level 2: test folder cards ─────────────────────────────────────────────

  function renderTestFolders() {
    if (exec.isLoadingTests) {
      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <FolderCardSkeleton key={i} />)}
        </div>
      );
    }

    if (exec.tests.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <FolderOpen size={48} className="text-border-subtle mb-3" />
          <p className="text-text-primary font-medium">No tests in this folder</p>
          <p className="text-sm text-text-secondary mt-1">Add tests from the Folders page</p>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {exec.tests.map((test, idx) => {
          const accent  = ACCENTS[idx % ACCENTS.length];
          const execs   = exec.execsByTestId.get(test.id) ?? [];
          const lastExec = execs[0] ?? null;
          const runCount = execs.length;
          const colors  = lastExec ? STATUS_BG[lastExec.status] : accent;

          return (
            <div
              key={test.id}
              className="group relative pt-3 cursor-pointer"
              onClick={() => {
                exec.setRunListPage(0);
                exec.setExpandedId(null);
                setSearchParams({ col: selectedColId!, test: test.id });
              }}
            >
              <div className={`absolute top-0 left-5 h-[13px] w-[72px] rounded-t-lg border border-b-0 transition-all ${colors.bg} border-border-subtle group-hover:border-primary/30`} />
              <div className="rounded-2xl border border-border-subtle p-5 bg-surface-main hover:border-primary/30 hover:shadow-sm transition-all">
                <div className="flex items-start justify-between mb-4">
                  <div className={`w-11 h-11 ${colors.bg} rounded-xl flex items-center justify-center flex-shrink-0`}>
                    {lastExec
                      ? <Folder size={22} className={colors.icon} />
                      : <FolderOpen size={22} className={colors.icon} />
                    }
                  </div>
                  {lastExec && <StatusPill status={lastExec.status} />}
                </div>
                <div className="font-semibold text-text-primary text-sm mb-1 leading-snug line-clamp-2">{test.name}</div>
                <div className="text-xs text-text-secondary">
                  {runCount > 0
                    ? `${runCount} run${runCount !== 1 ? 's' : ''} · Last ${(() => { const { date, time } = fmtTableDatetime(lastExec!.startedAt); return `${date}, ${time}`; })()}`
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

  // ── Level 1: main executions table ────────────────────────────────────────

  function renderCollectionFolders() {
    const liveRows    = exec.tableExecs.filter((e) => e.status === 'running' || e.status === 'queued');
    const historyRows = exec.tableExecs.filter((e) => e.status === 'passed'  || e.status === 'failed');
    const allVisible  = [...liveRows, ...historyRows];
    const allChecked  = allVisible.length > 0 && allVisible.every((e) => exec.selectedIds.has(e.id));
    const someChecked = allVisible.some((e) => exec.selectedIds.has(e.id));

    function renderRow(e: Execution) {
      const isSelected  = exec.selectedIds.has(e.id);
      const isRunning   = e.status === 'running';
      const progressPct = e.totalCount > 0 ? (e.passCount / e.totalCount) * 100 : 0;
      const elapsedMs   = isRunning ? exec.now - new Date(e.startedAt).getTime() : e.durationMs;

      return (
        <tr
          key={e.id}
          onClick={() => navigate(`/executions/${e.id}`)}
          className={`border-b border-border-subtle transition-colors last:border-b-0 cursor-pointer ${
            isSelected ? 'bg-[#3525cd]/[0.08]' : 'hover:bg-surface-muted/40'
          }`}
        >
          <td className="px-[14px] py-[11px]" style={{ width: 36 }} onClick={(ev) => ev.stopPropagation()}>
            <input type="checkbox" checked={isSelected} onChange={() => exec.toggleRow(e.id)} className="accent-primary" />
          </td>

          <td className="px-[14px] py-[11px]">
            <div className="flex items-start gap-2">
              {isRunning && <span className="mt-[3px] w-1.5 h-1.5 rounded-full bg-primary animate-pulse flex-shrink-0 inline-block" />}
              <div>
                <div className="font-medium text-sm text-text-primary">{e.testName}</div>
                <div className="text-sm text-text-secondary mt-0.5">
                  {(() => { const { date, time } = fmtTableDatetime(e.startedAt); return `${date}, ${time}`; })()} · #{e.runNumber}
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
              <Folder size={12} className="flex-shrink-0" />
              <span className="truncate">{e.collectionName}</span>
            </span>
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 100 }}><StatusPill status={e.status} /></td>

          <td className="px-[14px] py-[11px]" style={{ width: 140 }}>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-muted border border-border-subtle text-xs font-medium text-text-secondary max-w-[120px] truncate">
              <span className="truncate">{e.environmentName}</span>
            </span>
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 110 }}>
            {e.status === 'queued' ? (
              <span className="text-sm text-text-secondary font-mono-code">—</span>
            ) : (
              <div>
                <div className="flex w-[60px] overflow-hidden mb-1" style={{ height: 4, borderRadius: 2 }}>
                  <div className="bg-success" style={{ width: `${e.totalCount > 0 ? (e.passCount / e.totalCount) * 100 : 0}%` }} />
                  <div className="bg-error"   style={{ width: `${e.totalCount > 0 ? (e.failCount  / e.totalCount) * 100 : 0}%` }} />
                  <div className="flex-1 bg-surface-muted" />
                </div>
                <span className="text-sm font-mono-code text-text-secondary tabular-nums">{e.passCount}/{e.totalCount}</span>
              </div>
            )}
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 72 }}>
            <span className="text-sm font-mono-code text-text-secondary tabular-nums">{fmtMSS(elapsedMs)}</span>
          </td>

          <td className="px-[14px] py-[11px]" style={{ width: 96 }} onClick={(ev) => ev.stopPropagation()}>
            <div className="flex items-center justify-end gap-1">
              {(e.status === 'passed' || e.status === 'failed') && (
                <>
                  {e.reportDir && e.totalCount > 0 && (
                    <a href={`/reports/${e.reportDir}/html/index.html`} target="_blank" rel="noopener noreferrer" title="View report"
                      className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 border border-transparent hover:border-border-subtle transition-colors">
                      <BarChart3 size={16} />
                    </a>
                  )}
                  <button title="Re-run" onClick={() => exec.retryMutation.mutate(e)} disabled={exec.retryMutation.isPending}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 border border-transparent hover:border-border-subtle transition-colors disabled:opacity-40">
                    <RotateCcw size={16} />
                  </button>
                </>
              )}
              {e.status === 'running' && (
                <>
                  <button title="Stop"
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 border border-transparent hover:border-border-subtle transition-colors">
                    <Square size={16} />
                  </button>
                  <button title="View log" onClick={() => setLogExec(e)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 border border-transparent hover:border-border-subtle transition-colors">
                    <Terminal size={16} />
                  </button>
                </>
              )}
              {e.status === 'queued' && (
                <button title="Cancel"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 border border-transparent hover:border-border-subtle transition-colors">
                  <X size={16} />
                </button>
              )}
              {e.status !== 'running' && (
                <button title="Delete" onClick={() => exec.deleteMutation.mutate(e.id)} disabled={exec.deleteMutation.isPending}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-error hover:bg-error/10 border border-transparent hover:border-border-subtle transition-colors disabled:opacity-40">
                  <Trash2 size={16} />
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
        <FilterBar
          applied={exec.appliedFilters}
          activeCount={exec.activeFilterCount}
          onOpen={() => setFilterOpen(true)}
          onClear={exec.clearFilters}
          onRemove={exec.removeFilter}
          collections={exec.collections}
        />

        {exec.selectedIds.size >= 2 && (
          <div className="flex justify-end mb-3">
            <button
              onClick={() => setCompareOpen(true)}
              className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2 text-sm font-semibold hover:bg-primary/90 transition-colors"
            >
              <ArrowLeftRight size={16} />
              Compare ({exec.selectedIds.size})
            </button>
          </div>
        )}

        <div className="border border-border-subtle rounded-xl overflow-hidden">
          {exec.isLoadingTable ? (
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
                      onChange={() => exec.toggleAll(allVisible.map((e) => e.id))}
                      className="accent-primary"
                    />
                  </th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary">Run</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 140 }}>Collection</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 100 }}>Status</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 140 }}>Environment</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 110 }}>Tests</th>
                  <th className="text-left px-[14px] py-[11px] text-[11px] font-medium uppercase tracking-wider text-text-secondary" style={{ width: 72 }}>Duration</th>
                  <th className="px-[14px] py-[11px]" style={{ width: 96 }} />
                </tr>
              </thead>
              <tbody>
                {liveRows.length > 0 && <tr><td colSpan={8} className={sectionHeaderCls}>Live</td></tr>}
                {liveRows.map(renderRow)}
                {historyRows.length > 0 && <tr><td colSpan={8} className={sectionHeaderCls}>History</td></tr>}
                {historyRows.map(renderRow)}
                {exec.tableExecs.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-[14px] py-12 text-center text-sm text-text-secondary">
                      {exec.activeFilterCount > 0
                        ? 'No executions match your filters.'
                        : 'No executions yet. Run a suite to see results here.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}

          {exec.tablePagination && (
            <PaginationBar
              page={exec.tablePagination.page}
              totalPages={exec.tablePagination.totalPages}
              total={exec.tablePagination.total}
              pageSize={exec.tablePagination.pageSize}
              onPage={(p) => { exec.setTablePage(p); exec.setExpandedId(null); }}
            />
          )}
        </div>

        {compareOpen && exec.compareExecutions.length >= 2 && (
          <ComparePanel
            executionIds={exec.compareExecutions.map((e) => e.id)}
            executions={exec.compareExecutions}
            onClose={() => setCompareOpen(false)}
          />
        )}
      </>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────

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

      <FilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        value={exec.appliedFilters}
        onApply={exec.applyFilters}
        collections={exec.collections}
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
