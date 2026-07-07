import { useState, useEffect } from 'react';
import FilterDrawerShell, { FILTER_INPUT_CLS, FILTER_LABEL_CLS } from './FilterDrawerShell';

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

  return (
    <FilterDrawerShell open={open} onClose={onClose} title="Filter Collections" onClear={handleClear} onApply={handleApply}>
      {/* Date range (created) */}
      <div>
        <label className={FILTER_LABEL_CLS}>Created At</label>
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
