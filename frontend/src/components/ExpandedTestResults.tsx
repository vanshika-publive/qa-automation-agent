import { useQuery } from '@tanstack/react-query';
import { executionsService } from '../services/executions';
import { Execution, TestResult, ExecStep } from '../types';
import { formatDuration } from '../utils/formatters';

export function StatusPill({ status }: { status: Execution['status'] }) {
  const cfgMap: Record<Execution['status'], { cls: string; icon: string; label: string; spin: boolean }> = {
    passed:  { cls: 'bg-success/10 text-success border-success/20',               icon: 'check_circle', label: 'Passed',  spin: false },
    failed:  { cls: 'bg-error/10 text-error border-error/20',                     icon: 'cancel',       label: 'Failed',  spin: false },
    running: { cls: 'bg-warning/10 text-warning border-warning/20',               icon: 'sync',         label: 'Running', spin: true  },
    queued:  { cls: 'bg-surface-muted text-text-secondary border-border-subtle',  icon: 'schedule',     label: 'Queued',  spin: false },
  };
  const cfg = cfgMap[status] ?? cfgMap.failed;

  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-semibold ${cfg.cls}`}>
      <span className={`material-symbols-outlined ${cfg.spin ? 'animate-spin' : ''}`} style={{ fontSize: 12, fontVariationSettings: '"FILL" 1' }}>
        {cfg.icon}
      </span>
      {cfg.label}
    </span>
  );
}

function TestStatusBadge({ status }: { status: TestResult['status'] }) {
  if (status === 'passed') return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
      <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>check_circle</span>Passed
    </span>
  );
  if (status === 'skipped') return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-text-secondary">
      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>skip_next</span>Skipped
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-error">
      <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>cancel</span>Failed
    </span>
  );
}

export default function ExpandedTestResults({ execution, colSpan = 7 }: { execution: Execution; colSpan?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['execution-tests', execution.id],
    queryFn: () => executionsService.getTestResults(execution.id),
    refetchInterval: execution.status === 'running' ? 3000 : false,
    staleTime: 0,
  });

  const tests = data?.data ?? [];
  const isPending = data?.pending ?? execution.status === 'running';
  const showStepDetails = execution.status === 'failed' && !isLoading && tests.length === 0;

  const { data: detailData } = useQuery({
    queryKey: ['execution-detail', execution.id],
    queryFn: () => executionsService.getDetail(execution.id),
    enabled: showStepDetails,
    staleTime: 30_000,
  });

  const steps: ExecStep[] = detailData?.steps ?? [];
  const reportUrl = execution.reportDir ? `/reports/${execution.reportDir}/html/index.html` : null;

  return (
    <tr>
      <td colSpan={colSpan} className="px-0">
        <div className="bg-surface-muted/40 border-t border-b border-border-subtle">
          <div className="px-8 py-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {execution.status === 'running' && (
                  <div className="flex items-center gap-2 text-sm text-warning font-medium">
                    <div className="w-4 h-4 border-2 border-warning/30 border-t-warning rounded-full animate-spin" />
                    Running tests…
                  </div>
                )}
                {execution.status !== 'running' && tests.length > 0 && (
                  <div className="flex items-center gap-3 text-sm">
                    <span className="font-semibold text-text-primary">{tests.length} test{tests.length !== 1 ? 's' : ''}</span>
                    {execution.passCount > 0 && (
                      <span className="inline-flex items-center gap-1 text-success font-medium">
                        <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>check_circle</span>
                        {execution.passCount} passed
                      </span>
                    )}
                    {execution.failCount > 0 && (
                      <span className="inline-flex items-center gap-1 text-error font-medium">
                        <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>cancel</span>
                        {execution.failCount} failed
                      </span>
                    )}
                  </div>
                )}
                {execution.status !== 'running' && tests.length === 0 && !isLoading && (
                  <span className="text-sm text-text-secondary italic">
                    {execution.status === 'failed' ? 'Pipeline failed before tests ran.' : 'No test results yet.'}
                  </span>
                )}
                {isLoading && (
                  <div className="flex items-center gap-2 text-sm text-text-secondary">
                    <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                    Loading results…
                  </div>
                )}
              </div>
              {reportUrl && execution.status !== 'running' && tests.length > 0 && (
                <a href={reportUrl} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-semibold hover:bg-primary/20 transition-colors">
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>open_in_new</span>
                  Playwright Report
                </a>
              )}
            </div>

            {tests.length > 0 && (
              <div className="rounded-xl overflow-hidden border border-border-subtle">
                <table className="w-full">
                  <thead>
                    <tr className="bg-surface-muted border-b border-border-subtle">
                      <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">Test</th>
                      <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary w-[100px]">Result</th>
                      <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary w-[80px]">Duration</th>
                      <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">File</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle bg-surface-main">
                    {tests.map((t, i) => (
                      <tr key={i} className={t.status === 'failed' ? 'bg-error/3' : ''}>
                        <td className="px-4 py-3">
                          <div>
                            <span className="text-sm font-medium text-text-primary">{t.title}</span>
                            {t.error && (
                              <p className="mt-1 text-xs text-error font-mono-code leading-relaxed line-clamp-2">{t.error.split('\n')[0]}</p>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3"><TestStatusBadge status={t.status} /></td>
                        <td className="px-4 py-3">
                          <span className="text-sm text-text-secondary font-mono-code">{formatDuration(t.durationMs)}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-text-secondary font-mono-code truncate max-w-[260px] block">{t.file}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {showStepDetails && steps.length > 0 && (
              <div className="mt-3 space-y-2">
                {steps.map((step) => {
                  const isFailed = step.status === 'failed';
                  const isPassed = step.status === 'passed';
                  const borderCls = isFailed ? 'border-error/30 bg-error/5' : isPassed ? 'border-success/20 bg-success/5' : 'border-border-subtle bg-surface-muted';
                  const labelCls = isFailed ? 'text-error' : isPassed ? 'text-success' : 'text-text-secondary';
                  const icon = isFailed ? 'cancel' : isPassed ? 'check_circle' : 'radio_button_unchecked';
                  return (
                    <div key={step.id} className={`rounded-xl border p-3 ${borderCls}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`material-symbols-outlined ${labelCls}`} style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>{icon}</span>
                        <span className={`text-xs font-semibold uppercase tracking-wider ${labelCls}`}>{step.stepName}</span>
                      </div>
                      {step.log && (
                        <pre className="mt-1.5 text-[11px] text-text-secondary font-mono leading-relaxed whitespace-pre-wrap line-clamp-6 overflow-hidden">
                          {step.log.trim()}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {isPending && tests.length === 0 && !isLoading && (
              <div className="flex items-center gap-2 py-3 text-sm text-text-secondary">
                <div className="w-3 h-3 border-2 border-warning/30 border-t-warning rounded-full animate-spin" />
                Waiting for tests to start…
              </div>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}
