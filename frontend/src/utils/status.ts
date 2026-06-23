export const ACCENTS = [
  { bg: 'bg-warning/10',    icon: 'text-warning'        },
  { bg: 'bg-primary/10',    icon: 'text-primary'        },
  { bg: 'bg-success/10',    icon: 'text-success'        },
  { bg: 'bg-purple-500/10', icon: 'text-purple-500'     },
];

export const STATUS_BG: Record<string, { bg: string; icon: string }> = {
  passed:  { bg: 'bg-success/10',    icon: 'text-success'         },
  failed:  { bg: 'bg-error/10',      icon: 'text-error'           },
  running: { bg: 'bg-warning/10',    icon: 'text-warning'         },
  queued:  { bg: 'bg-surface-muted', icon: 'text-text-secondary'  },
};
