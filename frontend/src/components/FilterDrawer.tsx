import { useState, useEffect } from 'react';
import { Collection } from '../types';
import { ListFilter, X } from 'lucide-react';

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

  const inputCls = 'w-full border border-border-subtle rounded-xl px-3 py-2.5 text-sm text-text-primary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20';
  const labelCls = 'block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1.5';

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/20 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 h-full w-80 bg-surface-main shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle flex-shrink-0">
          <div className="flex items-center gap-2">
            <ListFilter size={20} className="text-text-secondary" />
            <span className="font-semibold text-text-primary text-sm">Filter Executions</span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">

          {/* Collection */}
          <div>
            <label className={labelCls}>Collection</label>
            <select
              value={draft.collectionId}
              onChange={(e) => set('collectionId', e.target.value)}
              className={inputCls}
            >
              <option value="">All collections</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div>
            <label className={labelCls}>Status</label>
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
            <label className={labelCls}>Date Range</label>
            <div className="space-y-2">
              <div>
                <span className="text-xs text-text-secondary mb-1 block">From</span>
                <input
                  type="date"
                  value={draft.from}
                  onChange={(e) => set('from', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <span className="text-xs text-text-secondary mb-1 block">To</span>
                <input
                  type="date"
                  value={draft.to}
                  onChange={(e) => set('to', e.target.value)}
                  max={new Date().toISOString().slice(0, 10)}
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-5 py-4 border-t border-border-subtle flex-shrink-0">
          <button
            onClick={handleClear}
            className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors"
          >
            Clear All
          </button>
          <button
            onClick={handleApply}
            className="flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-primary/90 transition-colors"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </>
  );
}
