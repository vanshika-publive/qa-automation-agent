import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { formatDuration, fmtDatetime } from '../utils/formatters';

interface ExecSummary {
  id: string; testId: string; environmentId: string;
  status: 'running' | 'passed' | 'failed';
  startedAt: string; completedAt: string | null;
  durationMs: number | null;
  passCount: number; failCount: number; totalCount: number;
  testName: string; environmentName: string; reportDir: string | null;
}
interface ExecStep {
  id: string; stepName: string;
  status: 'running' | 'passed' | 'failed';
  log: string; startedAt: string; completedAt: string | null;
}
interface ExecDetail extends ExecSummary { steps: ExecStep[] }
interface TestResult {
  title: string; file: string;
  status: 'passed' | 'failed' | 'skipped';
  durationMs: number; error: string | null;
}

const STEP_ORDER = ['orchestrator', 'planner', 'generator', 'runner'] as const;

export default function TestExecutionDetail({ testId, colSpan, asPanel }: { testId: string; colSpan: number; asPanel?: boolean }) {
  // Fetch most recent execution for this test
  const execsQ = useQuery({
    queryKey: ['test-executions', testId],
    queryFn: () => api.get<{ data: ExecSummary[]; error: string | null }>(`/executions?testId=${testId}`),
    staleTime: 10_000,
  });

  const latest = execsQ.data?.data?.[0] ?? null;

  // Fetch full detail (with steps) for the latest execution
  const detailQ = useQuery({
    queryKey: ['execution-detail', latest?.id],
    queryFn: () => api.get<{ data: ExecDetail; error: string | null }>(`/executions/${latest!.id}`),
    enabled: !!latest?.id,
    staleTime: 10_000,
    refetchInterval: latest?.status === 'running' ? 2000 : false,
  });

  // Fetch test results from results.json
  const resultsQ = useQuery({
    queryKey: ['execution-tests', latest?.id],
    queryFn: () => api.get<{ data: TestResult[]; pending: boolean; error: string | null }>(`/executions/${latest!.id}/tests`),
    enabled: !!latest?.id,
    staleTime: 10_000,
    refetchInterval: latest?.status === 'running' ? 2000 : false,
  });

  const detail = detailQ.data?.data ?? null;
  const steps = detail?.steps ?? [];
  const testResults = resultsQ.data?.data ?? [];

  const stepMap = new Map(steps.map((s) => [s.stepName, s]));

  const panelContent = (
    <div className="rounded-xl border border-border-subtle bg-surface-muted/40 overflow-hidden">

          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-border-subtle bg-surface-muted">
            {execsQ.isLoading || detailQ.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-text-secondary">
                <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                Loading run history…
              </div>
            ) : !latest ? (
              <span className="text-sm text-text-secondary italic">No runs yet — click the play button to generate and run this test.</span>
            ) : (
              <>
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-semibold text-text-primary">Last run</span>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${
                    latest.status === 'passed' ? 'bg-success/10 text-success border-success/20' :
                    latest.status === 'failed'  ? 'bg-error/10 text-error border-error/20' :
                    'bg-warning/10 text-warning border-warning/20'
                  }`}>
                    <span className={`material-symbols-outlined ${latest.status === 'running' ? 'animate-spin' : ''}`}
                      style={{ fontSize: 11, fontVariationSettings: '"FILL" 1' }}>
                      {latest.status === 'passed' ? 'check_circle' : latest.status === 'failed' ? 'cancel' : 'sync'}
                    </span>
                    {latest.status.charAt(0).toUpperCase() + latest.status.slice(1)}
                  </span>
                  <span className="text-text-secondary">{fmtDatetime(latest.startedAt)}</span>
                  {latest.durationMs && <span className="text-text-secondary font-mono-code text-xs">{formatDuration(latest.durationMs)}</span>}
                  {latest.totalCount > 0 && (
                    <span className="text-text-secondary">
                      <span className="text-success font-semibold">{latest.passCount}</span>/{latest.totalCount} tests passed
                    </span>
                  )}
                </div>
                <a href="/executions" className="text-xs text-primary hover:underline flex items-center gap-1">
                  <span className="material-symbols-outlined" style={{ fontSize: 13 }}>open_in_new</span>
                  All runs
                </a>
              </>
            )}
          </div>

          {latest && (
            <div className="px-5 py-4">
              {/* Pipeline steps */}
              <div className="flex items-stretch gap-0 mb-5">
                {STEP_ORDER.map((stepName, i) => {
                  const step = stepMap.get(stepName);
                  const status = step?.status ?? 'pending';
                  const isLast = i === STEP_ORDER.length - 1;

                  const colors = {
                    passed:  { dot: 'bg-success', label: 'text-success', card: 'border-success/20 bg-success/5' },
                    failed:  { dot: 'bg-error',   label: 'text-error',   card: 'border-error/20 bg-error/5'   },
                    running: { dot: 'bg-warning',  label: 'text-warning', card: 'border-warning/20 bg-warning/5'},
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
                        <span className="material-symbols-outlined text-border-subtle flex-shrink-0 mx-1" style={{ fontSize: 16 }}>
                          chevron_right
                        </span>
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
                              <span className="material-symbols-outlined" style={{ fontSize: 13, fontVariationSettings: '"FILL" 1' }}>
                                {t.status === 'passed' ? 'check_circle' : t.status === 'skipped' ? 'skip_next' : 'cancel'}
                              </span>
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

              {/* Failed step log */}
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
