import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useExecutionDetail } from '../hooks/useExecutionDetail';
import { usePlanningMemory } from '../hooks/usePlanningMemory';
import {
  ExecStep, TestResult, Execution, ExecutionDetail as ExecutionDetailData, PLANNING_MEMORY_MAX,
} from '../types';
import { relTime, fmtDatetime, fmtMSS } from '../utils/formatters';
import { StatusPill, TestStatusBadge } from '../components/StatusPill';
import { PageLoader } from '../components/PageLoader';
import { Button, IconButton } from '../components/Button';
import { LiveBrowserModal } from '../components/LiveBrowserModal';
import { isLiveViewEnabled } from '../services/liveView';
import {
  Clock, ArrowRight, Code2, FileText, ChevronDown, ArrowLeft, ChevronRight,
  RotateCcw, Timer, Network, Trash2, ExternalLink, AlertTriangle, Wrench, Send, Info, MonitorPlay,
} from 'lucide-react';

/** Numbered steps of the plan's first scenario (mirrors the backend's first-scenario target). */
function parsePlanSteps(planContent: string): string[] {
  const block = planContent.match(/\*\*Steps:?\*\*\s*\n([\s\S]*?)(?=\n\s*\*\*Expected|$)/);
  if (!block) return [];
  return [...block[1].matchAll(/^\s*\d+\.\s+(.+)$/gm)].map((m) => m[1].trim());
}

const STEP_ORDER = ['orchestrator', 'planner', 'generator', 'runner'] as const;

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
              <TestStatusBadge status={r.status} />
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

function RunHistory({ history, currentId, retryMutation, deleteMutation }: {
  history: Execution[];
  currentId: string;
  retryMutation: { mutate: () => void; isPending: boolean };
  deleteMutation: { mutate: (id: string) => void; isPending: boolean; variables?: string };
}) {
  const navigate = useNavigate();
  if (history.length === 0) return null;

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
            <th className="text-right px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary w-28">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {history.map((e) => {
            const isCurrent = e.id === currentId;
            const isDeleting = deleteMutation.isPending && deleteMutation.variables === e.id;
            return (
              <tr
                key={e.id}
                onClick={() => navigate(`/executions/${e.id}`)}
                className={`cursor-pointer transition-colors ${isCurrent ? 'bg-primary/5' : 'hover:bg-surface-muted/40'}`}
              >
                <td className="px-5 py-3">
                  <span className="font-mono text-sm font-semibold text-primary">
                    #{e.runNumber}
                    {isCurrent && <span className="ml-1.5 text-[10px] font-normal text-text-secondary">(this)</span>}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StatusPill status={e.status} />
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
                <td className="px-5 py-3" onClick={(ev) => ev.stopPropagation()}>
                  <div className="flex items-center justify-end gap-1">
                    {e.reportDir && e.totalCount > 0 && (
                      <a
                        href={`/reports/${e.reportDir}/html/index.html`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="View report"
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-primary/10 transition-colors"
                      >
                        <ExternalLink size={15} />
                      </a>
                    )}
                    <IconButton
                      tone="primary"
                      onClick={() => retryMutation.mutate()}
                      disabled={e.status === 'running' || retryMutation.isPending}
                      title="Re-run"
                    >
                      {retryMutation.isPending
                        ? <span className="w-3.5 h-3.5 border-2 border-primary/30 border-t-primary rounded-full animate-spin block" />
                        : <RotateCcw size={15} />}
                    </IconButton>
                    <IconButton
                      tone="error"
                      onClick={() => deleteMutation.mutate(e.id)}
                      disabled={e.status === 'running' || isDeleting}
                      title="Delete"
                    >
                      {isDeleting
                        ? <span className="w-3.5 h-3.5 border-2 border-error/30 border-t-error rounded-full animate-spin block" />
                        : <Trash2 size={15} />}
                    </IconButton>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function FailureBanner({ exec }: { exec: ExecutionDetailData }) {
  if (exec.status !== 'failed' || !exec.failureReason) return null;
  return (
    <section className="bg-error/5 border border-error/20 rounded-2xl p-5 mb-5">
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="text-error flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-error">
              Failure reason
            </span>
            {exec.failureCategory && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full border border-error/20 bg-error/10 text-error text-xs font-semibold">
                {exec.failureCategory}
              </span>
            )}
          </div>
          <p className="text-sm text-text-primary">{exec.failureReason}</p>
          {exec.failureLocator && (
            <pre className="mt-2 text-xs text-error bg-error/5 border border-error/15 rounded-lg px-3 py-2 whitespace-pre-wrap font-mono overflow-x-auto">
              {exec.failureLocator}
            </pre>
          )}
        </div>
      </div>
    </section>
  );
}

function CorrectiveReplanPanel({ exec, planContent }: { exec: ExecutionDetailData; planContent: string }) {
  const { entries, correctionMutation } = usePlanningMemory(exec.testId);
  const steps = parsePlanSteps(planContent);
  const [failedAtStep, setFailedAtStep] = useState<number | null>(null);
  const [correction, setCorrection] = useState('');
  const [scopeHint, setScopeHint] = useState(false);

  if (steps.length === 0) return null;

  const full = entries.length >= PLANNING_MEMORY_MAX;

  function handleSubmit() {
    if (!failedAtStep || !correction.trim()) return;
    correctionMutation.mutate(
      { failedAtStep, correction: correction.trim(), environmentId: exec.environmentId },
      { onSuccess: (res) => setScopeHint(res.data?.advisory?.kind === 'scope') },
    );
  }

  return (
    <section className="bg-surface-main rounded-2xl border border-border-subtle p-5 mb-5">
      <div className="flex items-center gap-2 mb-1">
        <Wrench size={16} className="text-text-secondary" />
        <h2 className="text-sm font-semibold text-text-primary">Correct this run</h2>
      </div>
      <p className="text-xs text-text-secondary mb-4">
        Pick the step where it went wrong and describe the fix. The steps before it are kept
        as-is; only the rest is re-planned, then saved as this test's known-good plan.
      </p>

      {full ? (
        <p className="text-sm text-text-secondary bg-surface-muted rounded-xl px-4 py-3 border border-border-subtle">
          Planning memory is full ({PLANNING_MEMORY_MAX} corrections). Open the test and edit or
          delete a guidance entry to make room before correcting again.
        </p>
      ) : (
        <>
          <div className="space-y-1 mb-4 max-h-64 overflow-y-auto">
            {steps.map((step, i) => {
              const n = i + 1;
              const selected = failedAtStep === n;
              return (
                <button
                  key={n}
                  onClick={() => setFailedAtStep(n)}
                  className={[
                    'w-full text-left flex items-start gap-2 px-3 py-2 rounded-lg border transition-all text-xs',
                    selected
                      ? 'border-primary bg-primary/5 text-text-primary'
                      : 'border-border-subtle text-text-secondary hover:border-primary/40',
                  ].join(' ')}
                >
                  <span className={`font-mono font-semibold flex-shrink-0 ${selected ? 'text-primary' : 'text-text-secondary'}`}>
                    {n}.
                  </span>
                  <span className="whitespace-pre-wrap">{step}</span>
                </button>
              );
            })}
          </div>

          <textarea
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
            rows={3}
            placeholder="e.g. Go to Posts → Create instead of clicking Assets"
            className="w-full border border-border-subtle rounded-xl px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary focus:ring-2 focus:ring-primary focus:border-primary outline-none resize-none mb-3"
          />

          {scopeHint && (
            <div className="flex items-start gap-2 text-xs bg-warning/5 border border-warning/20 rounded-xl px-3 py-2 mb-3">
              <Info size={14} className="text-warning flex-shrink-0 mt-0.5" />
              <span className="text-text-primary">
                This looks like it might change what's being tested rather than how to navigate —
                if so, edit the test description. The replan is running regardless.
              </span>
            </div>
          )}

          {correctionMutation.isError && (
            <p className="text-sm text-error mb-3">{(correctionMutation.error as Error)?.message}</p>
          )}

          <Button
            onClick={handleSubmit}
            disabled={!failedAtStep || !correction.trim() || correctionMutation.isPending}
          >
            {correctionMutation.isPending
              ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Replanning…</>
              : <><Send size={16} />Submit correction &amp; replan</>}
          </Button>
        </>
      )}
    </section>
  );
}

export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    exec, steps, testResults, testResultsPending,
    files, history, isLoading, isError, retryMutation, deleteMutation,
  } = useExecutionDetail(id!);

  const [liveOpen, setLiveOpen] = useState(false);

  if (isLoading) {
    return (
      <PageLoader />
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
        <div className="flex items-center gap-2">
          {isLiveViewEnabled() && (
            <Button variant="secondary" onClick={() => setLiveOpen(true)}>
              <MonitorPlay size={16} />Watch live
            </Button>
          )}
          <Button
            onClick={() => retryMutation.mutate()}
            disabled={exec.status === 'running' || retryMutation.isPending}
          >
            {retryMutation.isPending
              ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Re-running…</>
              : <><RotateCcw size={16} />Re-run</>
            }
          </Button>
        </div>
      </div>

      {liveOpen && <LiveBrowserModal onClose={() => setLiveOpen(false)} />}

      <div className="bg-surface-main rounded-2xl border border-border-subtle p-5 mb-5 flex flex-wrap items-center gap-4">
        <StatusPill status={exec.status} size="md" />
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

      <FailureBanner exec={exec} />
      {exec.status === 'failed' && files?.planContent && (
        <CorrectiveReplanPanel exec={exec} planContent={files.planContent} />
      )}
      <PipelineSteps steps={steps} />
      <TestResultsTable results={testResults} pending={testResultsPending} />
      {files?.planContent && steps.some(s => s.stepName === 'planner' && s.status === 'passed') && (
        <PlanView content={files.planContent} />
      )}
      {files?.specContent && (
        steps.some(s => s.stepName === 'generator' && s.status === 'passed') ||
        steps.some(s => s.stepName === 'runner')
      ) && (
        <SpecFileView filename={files.specFilename} content={files.specContent} />
      )}
      <RunHistory history={history} currentId={id!} retryMutation={retryMutation} deleteMutation={deleteMutation} />
    </div>
  );
}
