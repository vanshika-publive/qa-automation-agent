import { useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, HelpCircle, SkipForward, ChevronDown, ChevronRight, type LucideIcon } from 'lucide-react';
import { formatDuration, fmtDatetime } from '../utils/formatters';
import type { Execution } from '../types';
import { useTestExecutionHistory } from '../hooks/useTestExecutionHistory';

const STATUS_ICON_MAP: Record<string, LucideIcon> = {
  check_circle: CheckCircle2,
  cancel: XCircle,
  sync: RefreshCw,
  help: HelpCircle,
  skip_next: SkipForward,
};

const STEP_ORDER = ['orchestrator', 'planner', 'generator', 'runner'] as const;

function StatusBadge({ status }: { status: Execution['status'] }) {
  const cfg = {
    passed:  { bg: 'bg-success/10 text-success border-success/20',                        icon: 'check_circle' },
    failed:  { bg: 'bg-error/10 text-error border-error/20',                              icon: 'cancel'       },
    running: { bg: 'bg-warning/10 text-warning border-warning/20',                        icon: 'sync'         },
    queued:  { bg: 'bg-surface-muted text-text-secondary border-border-subtle',           icon: 'schedule'     },
  }[status] ?? { bg: 'bg-surface-muted text-text-secondary border-border-subtle', icon: 'help' };
  const StatusIcon = STATUS_ICON_MAP[cfg.icon] ?? HelpCircle;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${cfg.bg}`}>
      <StatusIcon size={11} className={status === 'running' ? 'animate-spin' : ''} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default function TestExecutionDetail({ testId, colSpan, asPanel }: { testId: string; colSpan: number; asPanel?: boolean }) {
  const [expandedExecId, setExpandedExecId] = useState<string | null>(null);

  const { allRuns, openId, isLoadingRuns, steps, isLoadingDetail, testResults } =
    useTestExecutionHistory(testId, expandedExecId);

  const stepMap = new Map(steps.map((s) => [s.stepName, s]));

  const panelContent = (
    <div className="rounded-xl border border-border-subtle bg-surface-muted/40 overflow-hidden">

      {isLoadingRuns ? (
        <div className="flex items-center gap-2 px-5 py-4 text-sm text-text-secondary">
          <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          Loading run history…
        </div>
      ) : allRuns.length === 0 ? (
        <div className="px-5 py-4 text-sm text-text-secondary italic">
          No runs yet — click the play button to generate and run this test.
        </div>
      ) : (
        <div className="divide-y divide-border-subtle">
          {allRuns.map((run, idx) => {
            const isOpen = run.id === openId;
            const runNumber = allRuns.length - idx;

            return (
              <div key={run.id}>
                {/* Run row */}
                <button
                  type="button"
                  onClick={() => setExpandedExecId(isOpen && expandedExecId !== null ? null : run.id)}
                  className={`w-full flex items-center gap-3 px-5 py-3 text-left transition-colors ${
                    isOpen ? 'bg-primary/5' : 'hover:bg-surface-muted/60'
                  }`}
                >
                  <span className="font-mono-code text-sm font-semibold text-primary w-8 shrink-0">#{runNumber}</span>
                  <StatusBadge status={run.status} />
                  <span className="text-sm font-medium text-text-primary">{run.testName}</span>
                  <span className="text-xs text-text-secondary">{fmtDatetime(run.startedAt)}</span>
                  {run.durationMs != null && (
                    <span className="text-xs text-text-secondary font-mono-code">{formatDuration(run.durationMs)}</span>
                  )}
                  {run.totalCount > 0 && (
                    <span className="text-xs text-text-secondary">
                      <span className="text-success font-semibold">{run.passCount}</span>/{run.totalCount} passed
                    </span>
                  )}
                  <span className="text-xs text-text-secondary ml-1">{run.environmentName}</span>
                  <ChevronDown
                    size={16}
                    className={`text-text-secondary ml-auto transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                  />
                </button>

                {/* Step detail for this run */}
                {isOpen && (
                  <div className="px-5 py-4 bg-surface-main/60 border-t border-border-subtle">
                    {isLoadingDetail ? (
                      <div className="flex items-center gap-2 text-sm text-text-secondary">
                        <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                        Loading details…
                      </div>
                    ) : (
                      <>
                        {/* Pipeline steps */}
                        <div className="flex items-stretch gap-0 mb-4">
                          {STEP_ORDER.map((stepName, i) => {
                            const step = stepMap.get(stepName);
                            const status = step?.status ?? 'pending';
                            const isLast = i === STEP_ORDER.length - 1;
                            const colors = {
                              passed:  { dot: 'bg-success', label: 'text-success', card: 'border-success/20 bg-success/5'   },
                              failed:  { dot: 'bg-error',   label: 'text-error',   card: 'border-error/20 bg-error/5'       },
                              running: { dot: 'bg-warning',  label: 'text-warning', card: 'border-warning/20 bg-warning/5'   },
                              pending: { dot: 'bg-border-subtle', label: 'text-text-secondary', card: 'border-border-subtle bg-surface-main' },
                            }[status];
                            return (
                              <div key={stepName} className="flex items-center flex-1 min-w-0">
                                <div className={`flex-1 rounded-xl border px-3 py-2.5 ${colors.card}`}>
                                  <div className="flex items-center gap-1.5 mb-0.5">
                                    {status === 'running'
                                      ? <span className="w-2 h-2 rounded-full bg-warning animate-pulse flex-shrink-0" />
                                      : <span className={`w-2 h-2 rounded-full ${colors.dot} flex-shrink-0`} />
                                    }
                                    <span className={`text-[10px] font-bold uppercase tracking-wider ${colors.label}`}>{stepName}</span>
                                  </div>
                                  <div className="text-[10px] text-text-secondary leading-tight">
                                    {status === 'pending' ? 'Not reached' :
                                     status === 'running' ? 'In progress…' :
                                     step?.log ? step.log.split('\n')[0].slice(0, 60) : status}
                                  </div>
                                </div>
                                {!isLast && (
                                  <ChevronRight size={16} className="text-border-subtle flex-shrink-0 mx-1" />
                                )}
                              </div>
                            );
                          })}
                        </div>

                        {/* Test results table */}
                        {testResults.length > 0 && (
                          <div className="rounded-xl overflow-hidden border border-border-subtle">
                            <table className="w-full">
                              <thead>
                                <tr className="bg-surface-muted border-b border-border-subtle">
                                  <th className="text-left px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">Test</th>
                                  <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-text-secondary w-24">Result</th>
                                  <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-text-secondary w-20">Duration</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-border-subtle bg-surface-main">
                                {testResults.map((t, i) => (
                                  <tr key={i} className={t.status === 'failed' ? 'bg-error/3' : ''}>
                                    <td className="px-4 py-2.5">
                                      <span className="text-xs font-medium text-text-primary">{t.title}</span>
                                      {t.error && (
                                        <p className="mt-0.5 text-[11px] text-error font-mono-code leading-tight line-clamp-1">{t.error.split('\n')[0]}</p>
                                      )}
                                    </td>
                                    <td className="px-3 py-2.5">
                                      <span className={`inline-flex items-center gap-1 text-xs font-semibold ${
                                        t.status === 'passed' ? 'text-success' : t.status === 'skipped' ? 'text-text-secondary' : 'text-error'
                                      }`}>
                                        {t.status === 'passed' ? <CheckCircle2 size={13} /> : t.status === 'skipped' ? <SkipForward size={13} /> : <XCircle size={13} />}
                                        {t.status.charAt(0).toUpperCase() + t.status.slice(1)}
                                      </span>
                                    </td>
                                    <td className="px-3 py-2.5">
                                      <span className="text-xs text-text-secondary font-mono-code">{formatDuration(t.durationMs)}</span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {/* Failed step log (when no test results) */}
                        {testResults.length === 0 && steps.some((s) => s.status === 'failed') && (() => {
                          const failedStep = steps.find((s) => s.status === 'failed');
                          return failedStep?.log ? (
                            <div className="rounded-xl border border-error/20 bg-error/5 px-4 py-3">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-error mb-1.5">{failedStep.stepName} error</p>
                              <pre className="text-[11px] text-text-secondary font-mono leading-relaxed whitespace-pre-wrap line-clamp-5">
                                {failedStep.log.trim()}
                              </pre>
                            </div>
                          ) : null;
                        })()}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  if (asPanel) return panelContent;

  return (
    <tr>
      <td colSpan={colSpan} className="px-0 pb-0">
        <div className="mx-5 mb-4">{panelContent}</div>
      </td>
    </tr>
  );
}
