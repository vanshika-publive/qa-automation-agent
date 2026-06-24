import { useState, useEffect } from 'react';
import { Execution } from '../types';
import { useComparePanel } from '../hooks/useComparePanel';

type CompareStep = NonNullable<Awaited<ReturnType<typeof useComparePanel>>['stepsA']>[number];
import { COMPARE_PANEL_WIDTH, FONT_VARIATION_FILLED } from '../constants';
import { fmtMSS } from '../utils/formatters';


interface ComparePanelProps {
  executionIds: string[];
  executions: Execution[];
  onClose: () => void;
}

function RunHeader({ exec, steps }: { exec: Execution; steps: CompareStep[] }) {
  const passRate = exec.totalCount > 0 ? `${exec.passCount}/${exec.totalCount}` : '—';
  return (
    <div className="p-4 border-b border-border-subtle">
      <div className="font-semibold text-sm text-text-primary mb-1">
        {exec.collectionName} #{exec.runNumber}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <StatusChip status={exec.status} />
        <span className="text-xs text-text-secondary font-mono-code">{passRate} passed</span>
        {steps.length > 0 && (
          <span className="text-xs text-text-secondary font-mono-code">{fmtMSS(exec.durationMs)}</span>
        )}
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const cfgMap: Record<string, { cls: string; icon: string }> = {
    passed:  { cls: 'bg-success/10 text-success',            icon: 'check_circle' },
    failed:  { cls: 'bg-error/10 text-error',                icon: 'cancel' },
    running: { cls: 'bg-warning/10 text-warning',            icon: 'sync' },
    queued:  { cls: 'bg-surface-muted text-text-secondary',  icon: 'schedule' },
    skipped: { cls: 'bg-surface-muted text-text-secondary',  icon: 'skip_next' },
  };
  const cfg = cfgMap[status] ?? cfgMap.failed;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${cfg.cls}`}>
      <span className="material-symbols-outlined" style={{ fontSize: 12, fontVariationSettings: FONT_VARIATION_FILLED }}>{cfg.icon}</span>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function StepStatusIcon({ status }: { status: 'passed' | 'failed' | 'skipped' | null }) {
  if (!status) {
    return <span className="text-sm text-text-secondary font-mono-code">—</span>;
  }
  const cfg = {
    passed:  { cls: 'text-success', icon: 'check_circle' },
    failed:  { cls: 'text-error',   icon: 'cancel' },
    skipped: { cls: 'text-text-secondary', icon: 'skip_next' },
  }[status];
  return (
    <span className={`material-symbols-outlined ${cfg.cls}`} style={{ fontSize: 16, fontVariationSettings: FONT_VARIATION_FILLED }}>
      {cfg.icon}
    </span>
  );
}

export default function ComparePanel({ executionIds, executions, onClose }: ComparePanelProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const idA = executionIds[0];
  const idB = executionIds[1];
  const execA = executions[0];
  const execB = executions[1];

  const { stepsA, stepsB, isLoading } = useComparePanel(idA, idB);

  // Merge test names from both runs, preserving run A order first
  const mergedNames: string[] = [];
  const seenNames = new Set<string>();
  for (const s of stepsA) {
    if (!seenNames.has(s.test_name)) { seenNames.add(s.test_name); mergedNames.push(s.test_name); }
  }
  for (const s of stepsB) {
    if (!seenNames.has(s.test_name)) { seenNames.add(s.test_name); mergedNames.push(s.test_name); }
  }

  const mapA = new Map(stepsA.map((s) => [s.test_name, s]));
  const mapB = new Map(stepsB.map((s) => [s.test_name, s]));

  function handleClose() {
    setVisible(false);
    setTimeout(onClose, 300);
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/30 z-40 transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`}
        onClick={handleClose}
      />

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full bg-surface-main shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${
          visible ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ width: COMPARE_PANEL_WIDTH }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>compare_arrows</span>
            <span className="font-semibold text-text-primary">Compare runs</span>
          </div>
          <button
            onClick={handleClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>

        {/* Column headers */}
        {execA && execB && (
          <div className="grid grid-cols-2 divide-x divide-border-subtle border-b border-border-subtle flex-shrink-0">
            <RunHeader exec={execA} steps={stepsA} />
            <RunHeader exec={execB} steps={stepsB} />
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-5 space-y-3 animate-pulse">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-10 rounded-lg bg-surface-muted" />
              ))}
            </div>
          ) : mergedNames.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center px-6">
              <span className="material-symbols-outlined text-border-subtle mb-3" style={{ fontSize: 40 }}>info</span>
              <p className="text-sm text-text-secondary">No test results available for these runs.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="bg-surface-muted border-b border-border-subtle sticky top-0 z-10">
                  <th className="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary">Test</th>
                  <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary text-center w-16">A</th>
                  <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-secondary text-center w-16">B</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {mergedNames.map((name) => {
                  const sA = mapA.get(name) ?? null;
                  const sB = mapB.get(name) ?? null;
                  const isDiff =
                    sA !== null && sB !== null &&
                    ((sA.status === 'passed' && sB.status === 'failed') ||
                     (sA.status === 'failed' && sB.status === 'passed'));

                  return (
                    <tr
                      key={name}
                      className={`transition-colors ${isDiff ? 'bg-warning/8' : 'hover:bg-surface-muted/40'}`}
                    >
                      <td className="px-4 py-3">
                        <div className="text-sm text-text-primary leading-snug">{name}</div>
                        {(sA?.error_message || sB?.error_message) && (
                          <p className="mt-0.5 text-xs text-error font-mono-code line-clamp-1">
                            {sA?.error_message ?? sB?.error_message}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center w-16">
                        <StepStatusIcon status={sA?.status ?? null} />
                      </td>
                      <td className="px-4 py-3 text-center w-16">
                        <StepStatusIcon status={sB?.status ?? null} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
