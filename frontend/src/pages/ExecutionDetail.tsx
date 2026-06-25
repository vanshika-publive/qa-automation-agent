import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useExecutionDetail } from '../hooks/useExecutionDetail';
import { ExecStep, TestResult, Execution } from '../types';
import { relTime, fmtDatetime, fmtMSS } from '../utils/formatters';
import {
  CheckCircle2, XCircle, RefreshCw, Clock, HelpCircle, MinusCircle,
  ArrowRight, Code2, FileText, ChevronDown, ArrowLeft, ChevronRight,
  RotateCcw, Timer, Network,
} from 'lucide-react';

// ── Helpers ───────────────────────────────────────────────────────────────────

const STEP_ORDER = ['orchestrator', 'planner', 'generator', 'runner'] as const;

function StatusBadge({ status }: { status: Execution['status'] }) {
  const cfg = {
    passed:  { cls: 'bg-success/10 text-success border-success/20',   label: 'Passed'  },
    failed:  { cls: 'bg-error/10 text-error border-error/20',         label: 'Failed'  },
    running: { cls: 'bg-warning/10 text-warning border-warning/20',   label: 'Running' },
    queued:  { cls: 'bg-surface-muted text-text-secondary border-border-subtle', label: 'Queued' },
  }[status] ?? { cls: '', label: status };

  function StatusIcon() {
    if (status === 'passed') return <CheckCircle2 size={14} />;
    if (status === 'failed') return <XCircle size={14} />;
    if (status === 'running') return <RefreshCw size={14} className="animate-spin" />;
    if (status === 'queued') return <Clock size={14} />;
    return <HelpCircle size={14} />;
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-sm font-semibold ${cfg.cls}`}>
      <StatusIcon />
      {cfg.label}
    </span>
  );
}

function TestResultBadge({ status }: { status: TestResult['status'] }) {
  const cfg = {
    passed:  { cls: 'text-success' },
    failed:  { cls: 'text-error'   },
    skipped: { cls: 'text-warning' },
  }[status];

  function ResultIcon() {
    if (status === 'passed') return <CheckCircle2 size={13} />;
    if (status === 'failed') return <XCircle size={13} />;
    return <MinusCircle size={13} />;
  }

  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold ${cfg.cls}`}>
      <ResultIcon />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ── Pipeline steps timeline ───────────────────────────────────────────────────

function PipelineSteps({ steps }: { steps: ExecStep[] }) {
  const stepMap = Object.fromEntries(steps.map((s) => [s.stepName, s]));
  const [expandedLog, setExpandedLog] = useState<string | null>(null);

  return (
    <section className="bg-surface-main rounded-2xl border border-border-subtle p-5 mb-5">
      <h2 className="text-sm font-semibold text-text-primary mb-4">Pipeline</h2>
      <div className="flex items-center gap-0 flex-wrap">
        {STEP_ORDER.map((name, i) => {
          const step = stepMap[name];
          const s = step?.status ?? 'pending';
          const cfg = {
            passed:  { ring: 'border-success bg-success/10 text-success',   dot: 'bg-success'   },
            failed:  { ring: 'border-error bg-error/10 text-error',         dot: 'bg-error'     },
            running: { ring: 'border-warning bg-warning/10 text-warning',   dot: 'bg-warning animate-pulse' },
            pending: { ring: 'border-border-subtle bg-surface-muted text-text-secondary', dot: 'bg-border-subtle' },
          }[s] ?? { ring: 'border-border-subtle bg-surface-muted text-text-secondary', dot: 'bg-border-subtle' };

          return (
            <div key={name} className="flex items-center">
              <button
                onClick={() => step?.log ? setExpandedLog(expandedLog === name ? null : name) : undefined}
                className={`flex flex-col items-center px-4 py-2.5 rounded-xl border transition-all ${cfg.ring} ${step?.log ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
                  <span className="text-xs font-semibold capitalize">{name}</span>
                </div>
                {step?.completedAt && step?.startedAt && (
                  <span className="text-[10px] opacity-60">
                    {fmtMSS(new Date(step.completedAt).getTime() - new Date(step.startedAt).getTime())}
                  </span>
                )}
              </button>
              {i < STEP_ORDER.length - 1 && (
                <ArrowRight size={16} className="text-border-subtle mx-1" />
              )}
            </div>
          );
        })}
      </div>
      {expandedLog && stepMap[expandedLog]?.log && (
        <div className="mt-4 rounded-xl bg-[#0f172a] p-4 overflow-x-auto">
          <pre className="text-[11px] text-[#94a3b8] font-mono leading-relaxed whitespace-pre-wrap">
            {stepMap[expandedLog].log}
          </pre>
        </div>
      )}
    </section>
  );
}

// ── Test results table ────────────────────────────────────────────────────────

function TestResultsTable({ results, pending }: { results: TestResult[]; pending: boolean }) {
  if (pending && results.length === 0) {
    return (
      <section className="bg-surface-main rounded-2xl border border-border-subtle p-5 mb-5">
        <h2 className="text-sm font-semibold text-text-primary mb-4">Test Results</h2>
        <div className="flex items-center gap-2 text-sm text-text-secondary py-4">
          <span className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          Running…
        </div>
      </section>
    );
  }

  if (results.length === 0) {
    return (
      <section className="bg-surface-main rounded-2xl border border-border-subtle p-5 mb-5">
        <h2 className="text-sm font-semibold text-text-primary mb-2">Test Results</h2>
        <p className="text-sm text-text-secondary">No results yet.</p>
      </section>
    );
  }

  const byFile = results.reduce<Record<string, TestResult[]>>((acc, r) => {
    (acc[r.file] = acc[r.file] ?? []).push(r);
    return acc;
  }, {});

  return (
    <section className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-border-subtle">
        <h2 className="text-sm font-semibold text-text-primary">Test Results</h2>
      </div>
      {Object.entries(byFile).map(([file, rows]) => (
        <div key={file}>
          <div className="px-5 py-2 bg-surface-muted/60 border-b border-border-subtle flex items-center gap-2">
            <Code2 size={14} className="text-text-secondary" />
            <span className="text-xs font-mono text-text-secondary">{file || 'unknown file'}</span>
          </div>
          {rows.map((r, i) => (
            <div key={i} className="px-5 py-3 border-b border-border-subtle last:border-b-0 flex items-start gap-3">
              <TestResultBadge status={r.status} />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-text-primary">{r.title}</span>
                {r.error && (
                  <pre className="mt-1.5 text-xs text-error bg-error/5 border border-error/15 rounded-lg px-3 py-2 whitespace-pre-wrap font-mono overflow-x-auto">
                    {r.error}
                  </pre>
                )}
              </div>
              <span className="text-xs font-mono text-text-secondary flex-shrink-0 mt-0.5">
                {fmtMSS(r.durationMs)}
              </span>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}

// ── Plan.md viewer ────────────────────────────────────────────────────────────

function PlanView({ content }: { content: string }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden mb-5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full px-5 py-4 flex items-center justify-between border-b border-border-subtle hover:bg-surface-muted/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-text-secondary" />
          <h2 className="text-sm font-semibold text-text-primary">Test Plan (plan.md)</h2>
        </div>
        <ChevronDown size={18} className={`text-text-secondary transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-5 py-4 overflow-x-auto">
          <pre className="text-sm text-text-primary font-mono leading-relaxed whitespace-pre-wrap">
            {content}
          </pre>
        </div>
      )}
    </section>
  );
}

// ── .py file viewer ───────────────────────────────────────────────────────────

function SpecFileView({ filename, content }: { filename: string | null; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden mb-5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-surface-muted/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Code2 size={16} className="text-text-secondary" />
          <h2 className="text-sm font-semibold text-text-primary">Generated Test File</h2>
          {filename && (
            <span className="text-xs text-text-secondary font-mono bg-surface-muted px-2 py-0.5 rounded-md border border-border-subtle">
              {filename}
            </span>
          )}
        </div>
        <ChevronDown size={18} className={`text-text-secondary transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-border-subtle">
          <div className="flex items-center gap-1.5 px-5 py-2 bg-[#0f172a] border-b border-white/10">
            <div className="w-2 h-2 rounded-full bg-red-500/50" />
            <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
            <div className="w-2 h-2 rounded-full bg-green-500/50" />
            <span className="ml-2 text-[10px] text-[#64748b] font-mono">{filename ?? 'test.py'}</span>
          </div>
          <div className="bg-[#0f172a] overflow-x-auto max-h-[480px] overflow-y-auto">
            <pre className="p-5 text-[12px] text-[#e2e8f0] font-mono leading-relaxed whitespace-pre">
              {content}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Run history ───────────────────────────────────────────────────────────────

function RunHistory({ history, currentId }: { history: Execution[]; currentId: string }) {
  if (history.length === 0) return null;

  function HistoryStatusIcon({ status }: { status: Execution['status'] }) {
    if (status === 'passed') return <CheckCircle2 size={11} />;
    if (status === 'failed') return <XCircle size={11} />;
    if (status === 'running') return <RefreshCw size={11} />;
    return <Clock size={11} />;
  }

  return (
    <section className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-border-subtle">
        <h2 className="text-sm font-semibold text-text-primary">Run History</h2>
        <p className="text-xs text-text-secondary mt-0.5">All runs for this test</p>
      </div>
      <table className="w-full">
        <thead>
          <tr className="bg-surface-muted border-b border-border-subtle">
            <th className="text-left px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary w-16">Run</th>
            <th className="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary w-28">Status</th>
            <th className="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary w-24">Passed</th>
            <th className="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary w-24">Failed</th>
            <th className="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary w-24">Duration</th>
            <th className="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary">Started</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {history.map((e) => {
            const isCurrent = e.id === currentId;
            return (
              <tr
                key={e.id}
                className={`transition-colors ${isCurrent ? 'bg-primary/5' : 'hover:bg-surface-muted/40'}`}
              >
                <td className="px-5 py-3">
                  <Link
                    to={`/executions/${e.id}`}
                    className="font-mono text-sm font-semibold text-primary hover:underline"
                  >
                    #{e.runNumber}
                    {isCurrent && <span className="ml-1.5 text-[10px] font-normal text-text-secondary">(this)</span>}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${
                    e.status === 'passed' ? 'bg-success/10 text-success border-success/20' :
                    e.status === 'failed' ? 'bg-error/10 text-error border-error/20' :
                    e.status === 'running' ? 'bg-warning/10 text-warning border-warning/20' :
                    'bg-surface-muted text-text-secondary border-border-subtle'
                  }`}>
                    <HistoryStatusIcon status={e.status} />
                    {e.status.charAt(0).toUpperCase() + e.status.slice(1)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-semibold text-success">{e.passCount}</span>
                  <span className="text-xs text-text-secondary">/{e.totalCount}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-semibold text-error">{e.failCount}</span>
                  <span className="text-xs text-text-secondary">/{e.totalCount}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-mono text-text-secondary">{fmtMSS(e.durationMs)}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm text-text-secondary" title={fmtDatetime(e.startedAt)}>
                    {relTime(e.startedAt)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    exec, steps, testResults, testResultsPending,
    files, history, isLoading, isError, retryMutation,
  } = useExecutionDetail(id!);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (isError || !exec) {
    return (
      <div className="p-8 max-w-5xl">
        <button onClick={() => navigate('/executions')} className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary mb-6 transition-colors">
          <ArrowLeft size={18} />
          Back to Executions
        </button>
        <p className="text-text-secondary">Execution not found.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/executions')}
            className="w-9 h-9 flex items-center justify-center rounded-xl border border-border-subtle hover:bg-surface-muted transition-colors"
          >
            <ArrowLeft size={18} className="text-text-secondary" />
          </button>
          <div>
            <nav className="flex items-center gap-1 text-xs text-text-secondary mb-0.5">
              <button onClick={() => navigate('/executions')} className="hover:text-primary transition-colors">Executions</button>
              <ChevronRight size={14} />
              <span className="text-text-primary font-medium">{exec.collectionName} · #{exec.runNumber}</span>
            </nav>
            <h1 className="text-xl font-bold text-text-primary">{exec.testName}</h1>
          </div>
        </div>
        <button
          onClick={() => retryMutation.mutate()}
          disabled={exec.status === 'running' || retryMutation.isPending}
          className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
        >
          {retryMutation.isPending
            ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Re-running…</>
            : <><RotateCcw size={16} />Re-run</>
          }
        </button>
      </div>

      {/* Status banner */}
      <div className="bg-surface-main rounded-2xl border border-border-subtle p-5 mb-5 flex flex-wrap items-center gap-4">
        <StatusBadge status={exec.status} />
        <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary">
          <span className="flex items-center gap-1.5">
            <Clock size={14} />
            {relTime(exec.startedAt)}
            <span className="text-text-secondary/50 mx-0.5">·</span>
            <span className="text-xs text-text-secondary/70">{fmtDatetime(exec.startedAt)}</span>
          </span>
          {exec.durationMs != null && (
            <span className="flex items-center gap-1.5">
              <Timer size={14} />
              {fmtMSS(exec.durationMs)}
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <Network size={14} />
            {exec.environmentName}
            {exec.environmentUrl && (
              <span className="text-text-secondary/60 text-xs ml-0.5">{exec.environmentUrl}</span>
            )}
          </span>
          {exec.totalCount > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="text-success font-semibold">{exec.passCount}</span>
              <span className="text-text-secondary/50">/</span>
              <span className="font-medium">{exec.totalCount}</span>
              <span className="text-xs">passed</span>
            </span>
          )}
        </div>
      </div>

      {/* Pipeline */}
      <PipelineSteps steps={steps} />

      {/* Test results */}
      <TestResultsTable results={testResults} pending={testResultsPending} />

      {/* Plan.md */}
      {files?.planContent && <PlanView content={files.planContent} />}

      {/* Generated .py file */}
      {files?.specContent && (
        <SpecFileView filename={files.specFilename} content={files.specContent} />
      )}

      {/* Run history */}
      <RunHistory history={history} currentId={id!} />
    </div>
  );
}
