import { CheckCircle2, XCircle, SkipForward, RefreshCw, Circle, HelpCircle, type LucideIcon } from 'lucide-react';
import { Execution, TestResult } from '../types';

const STATUS_ICON_MAP: Record<string, LucideIcon> = {
  check_circle: CheckCircle2,
  cancel: XCircle,
  sync: RefreshCw,
  radio_button_unchecked: Circle,
  skip_next: SkipForward,
};

const PILL_SIZES = {
  sm: { box: 'px-2.5 py-1 text-xs', icon: 12 },
  md: { box: 'px-3 py-1 text-sm',   icon: 14 },
} as const;

/** Execution-level status pill (passed / failed / running / queued). */
export function StatusPill({ status, size = 'sm' }: { status: Execution['status']; size?: keyof typeof PILL_SIZES }) {
  const cfgMap: Record<Execution['status'], { cls: string; icon: string; label: string; spin: boolean }> = {
    passed:  { cls: 'bg-success/10 text-success border-success/20',               icon: 'check_circle', label: 'Passed',  spin: false },
    failed:  { cls: 'bg-error/10 text-error border-error/20',                     icon: 'cancel',       label: 'Failed',  spin: false },
    running: { cls: 'bg-warning/10 text-warning border-warning/20',               icon: 'sync',         label: 'Running', spin: true  },
    queued:  { cls: 'bg-surface-muted text-text-secondary border-border-subtle',  icon: 'schedule',     label: 'Queued',  spin: false },
  };
  const cfg = cfgMap[status] ?? cfgMap.failed;
  const sz = PILL_SIZES[size];

  const StatusIcon = STATUS_ICON_MAP[cfg.icon] ?? HelpCircle;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-semibold ${sz.box} ${cfg.cls}`}>
      <StatusIcon size={sz.icon} className={cfg.spin ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  );
}

/** Per-test result badge (passed / failed / skipped). */
export function TestStatusBadge({ status }: { status: TestResult['status'] }) {
  if (status === 'passed') return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
      <CheckCircle2 size={14} />Passed
    </span>
  );
  if (status === 'skipped') return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-text-secondary">
      <SkipForward size={14} />Skipped
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-error">
      <XCircle size={14} />Failed
    </span>
  );
}
