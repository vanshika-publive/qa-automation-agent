import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Folder, CheckCircle2, XCircle, RefreshCw, MinusCircle, ChevronRight } from 'lucide-react';
import { StatusPill } from '../components/ExpandedTestResults';
import { useBatchExecutionStatus, BatchRow } from '../hooks/useBatchExecutionStatus';

function SkippedPill() {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-semibold bg-surface-muted text-text-secondary border-border-subtle">
      <MinusCircle size={12} />
      Skipped
    </span>
  );
}

function SummaryStat({ icon: Icon, label, value, tone }: { icon: typeof CheckCircle2; label: string; value: number; tone: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-main border border-border-subtle">
      <Icon size={16} className={tone} />
      <span className="text-sm font-semibold text-text-primary">{value}</span>
      <span className="text-sm text-text-secondary">{label}</span>
    </div>
  );
}

function RowCard({ row, onClick }: { row: BatchRow; onClick: () => void }) {
  const clickable = row.launchStatus === 'launched' && !!row.executionId;
  return (
    <div
      onClick={clickable ? onClick : undefined}
      className={`flex items-center justify-between px-5 py-4 rounded-2xl border border-border-subtle bg-surface-main transition-all duration-150 ${
        clickable ? 'cursor-pointer hover:bg-surface-muted/50 hover:-translate-y-0.5 hover:shadow-md' : 'opacity-70'
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <Folder size={18} className="text-text-secondary flex-shrink-0" />
        <div className="min-w-0">
          <div className="font-medium text-sm text-text-primary truncate">{row.collectionName}</div>
          {row.launchStatus === 'launched' && row.status && row.status !== 'queued' && (
            <div className="text-xs text-text-secondary mt-0.5 font-mono-code tabular-nums">
              {row.passCount}/{row.totalCount} passed
            </div>
          )}
          {row.launchStatus === 'skipped' && (
            <div className="text-xs text-text-secondary mt-0.5">No specs or environment to run</div>
          )}
          {row.launchStatus === 'failed' && (
            <div className="text-xs text-error mt-0.5">Failed to launch</div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        {row.launchStatus === 'launched' && row.status ? <StatusPill status={row.status} /> : <SkippedPill />}
        {clickable && <ChevronRight size={16} className="text-text-secondary" />}
      </div>
    </div>
  );
}

export default function BatchExecutionStatus() {
  const navigate = useNavigate();
  const { rows, summary, isRunning } = useBatchExecutionStatus();

  return (
    <div className="p-8 max-w-4xl">
      <button
        onClick={() => navigate('/')}
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors mb-4"
      >
        <ArrowLeft size={16} />
        Back to Collections
      </button>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Running {summary.total} {summary.total === 1 ? 'Collection' : 'Collections'}
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {isRunning ? 'Live status — updates automatically' : 'All runs complete'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SummaryStat icon={CheckCircle2} label="passed" value={summary.passed} tone="text-success" />
          <SummaryStat icon={XCircle} label="failed" value={summary.failed} tone="text-error" />
          <SummaryStat icon={RefreshCw} label="running" value={summary.running} tone="text-warning" />
          <SummaryStat icon={MinusCircle} label="skipped" value={summary.skipped} tone="text-text-secondary" />
        </div>
      </div>

      <div className="space-y-2.5">
        {rows.length === 0 ? (
          <div className="px-5 py-16 text-center text-sm text-text-secondary border border-border-subtle rounded-2xl bg-surface-main">
            No collections in this batch.
          </div>
        ) : (
          rows.map((row) => (
            <RowCard
              key={row.collectionId}
              row={row}
              onClick={() => row.executionId && navigate(`/executions/${row.executionId}`)}
            />
          ))
        )}
      </div>
    </div>
  );
}
