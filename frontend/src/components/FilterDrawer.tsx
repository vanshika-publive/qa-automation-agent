import { useState, useEffect } from 'react';
import { Collection } from '../types';
import FilterDrawerShell, { FILTER_INPUT_CLS, FILTER_LABEL_CLS } from './FilterDrawerShell';

export interface FilterState {
  collectionId: string;
  status: string;
  from: string;   // YYYY-MM-DD or ''
  to: string;     // YYYY-MM-DD or ''
}

export const DEFAULT_FILTERS: FilterState = { collectionId: '', status: '', from: '', to: '' };

export const STATUS_OPTIONS = [
  { value: '',        label: 'All statuses' },
  { value: 'passed',  label: 'Passed' },
  { value: 'failed',  label: 'Failed' },
  { value: 'running', label: 'Running' },
  { value: 'queued',  label: 'Queued' },
];

export default function FilterDrawer({
  open,
  onClose,
  value,
  onApply,
  collections,
}: {
  open: boolean;
  onClose: () => void;
  value: FilterState;
  onApply: (f: FilterState) => void;
  collections: Collection[];
}) {
  const [draft, setDraft] = useState<FilterState>(value);

  useEffect(() => {
    if (open) setDraft(value);
  }, [open, value]);

  function set<K extends keyof FilterState>(key: K, val: FilterState[K]) {
    setDraft((d) => ({ ...d, [key]: val }));
  }

  function handleApply() {
    onApply(draft);
    onClose();
  }

  function handleClear() {
    const cleared = DEFAULT_FILTERS;
    setDraft(cleared);
    onApply(cleared);
    onClose();
  }

  return (
    <FilterDrawerShell open={open} onClose={onClose} title="Filter Executions" onClear={handleClear} onApply={handleApply}>
      {/* Collection */}
      <div>
        <label className={FILTER_LABEL_CLS}>Collection</label>
        <select
          value={draft.collectionId}
          onChange={(e) => set('collectionId', e.target.value)}
          className={FILTER_INPUT_CLS}
        >
          <option value="">All collections</option>
          {collections.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Status */}
      <div>
        <label className={FILTER_LABEL_CLS}>Status</label>
        <div className="space-y-2">
          {STATUS_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2.5 cursor-pointer group">
              <input
                type="radio"
                name="status"
                value={opt.value}
                checked={draft.status === opt.value}
                onChange={() => set('status', opt.value)}
                className="accent-primary"
              />
              <span className="text-sm text-text-primary group-hover:text-primary transition-colors">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Date range */}
      <div>
        <label className={FILTER_LABEL_CLS}>Date Range</label>
        <div className="space-y-2">
          <div>
            <span className="text-xs text-text-secondary mb-1 block">From</span>
            <input
              type="date"
              value={draft.from}
              onChange={(e) => set('from', e.target.value)}
              className={FILTER_INPUT_CLS}
            />
          </div>
          <div>
            <span className="text-xs text-text-secondary mb-1 block">To</span>
            <input
              type="date"
              value={draft.to}
              onChange={(e) => set('to', e.target.value)}
              max={new Date().toISOString().slice(0, 10)}
              className={FILTER_INPUT_CLS}
            />
          </div>
        </div>
      </div>
    </FilterDrawerShell>
  );
}
