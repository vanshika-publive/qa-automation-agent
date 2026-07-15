import { ListFilter, X } from 'lucide-react';

export const FILTER_INPUT_CLS =
  'w-full border border-border-subtle rounded-xl px-3 py-2.5 text-sm text-text-primary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20';
export const FILTER_LABEL_CLS =
  'block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1.5';

export default function FilterDrawerShell({
  open,
  onClose,
  title,
  onClear,
  onApply,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  onClear: () => void;
  onApply: () => void;
  children: React.ReactNode;
}) {
  return (
    <>
      {open && (
        <div className="fixed inset-0 bg-black/20 z-40 transition-opacity" onClick={onClose} />
      )}

      <div
        className={`fixed top-0 right-0 h-full w-80 bg-surface-main shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle flex-shrink-0">
          <div className="flex items-center gap-2">
            <ListFilter size={20} className="text-text-secondary" />
            <span className="font-semibold text-text-primary text-sm">{title}</span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">{children}</div>

        <div className="flex items-center gap-3 px-5 py-4 border-t border-border-subtle flex-shrink-0">
          <button
            onClick={onClear}
            className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors"
          >
            Clear All
          </button>
          <button
            onClick={onApply}
            className="flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-primary/90 transition-colors"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </>
  );
}
