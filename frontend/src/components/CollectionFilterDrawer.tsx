import { useState, useEffect } from 'react';
import { ListFilter, X } from 'lucide-react';

export interface CollectionFilterState {
  from: string;   // YYYY-MM-DD or ''
  to: string;     // YYYY-MM-DD or ''
}

export const DEFAULT_COLLECTION_FILTERS: CollectionFilterState = { from: '', to: '' };

export default function CollectionFilterDrawer({
  open,
  onClose,
  value,
  onApply,
}: {
  open: boolean;
  onClose: () => void;
  value: CollectionFilterState;
  onApply: (f: CollectionFilterState) => void;
}) {
  const [draft, setDraft] = useState<CollectionFilterState>(value);

  useEffect(() => {
    if (open) setDraft(value);
  }, [open, value]);

  function set<K extends keyof CollectionFilterState>(key: K, val: CollectionFilterState[K]) {
    setDraft((d) => ({ ...d, [key]: val }));
  }

  function handleApply() {
    onApply(draft);
    onClose();
  }

  function handleClear() {
    setDraft(DEFAULT_COLLECTION_FILTERS);
    onApply(DEFAULT_COLLECTION_FILTERS);
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
            <span className="font-semibold text-text-primary text-sm">Filter Collections</span>
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
          {/* Date range (created) */}
          <div>
            <label className={labelCls}>Created At</label>
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
