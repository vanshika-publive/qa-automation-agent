import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function PaginationBar({
  page,
  totalPages,
  total,
  pageSize,
  onPage,
  alwaysShow = false,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
  alwaysShow?: boolean;
}) {
  if (totalPages <= 1 && !alwaysShow) return null;

  const from = (page - 1) * pageSize + 1;
  const to   = Math.min(page * pageSize, total);

  // Build page numbers with ellipsis
  function pageNumbers(): (number | '…')[] {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const pages: (number | '…')[] = [];
    if (page <= 4) {
      pages.push(1, 2, 3, 4, 5, '…', totalPages);
    } else if (page >= totalPages - 3) {
      pages.push(1, '…', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
    } else {
      pages.push(1, '…', page - 1, page, page + 1, '…', totalPages);
    }
    return pages;
  }

  const btnBase = 'inline-flex items-center justify-center min-w-[32px] h-8 px-2 rounded-lg text-xs font-medium transition-colors';

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-border-subtle bg-surface-muted">
      <span className="text-xs text-text-secondary">
        Showing {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          disabled={page === 1}
          onClick={() => onPage(page - 1)}
          className={`${btnBase} border border-border-subtle text-text-secondary hover:bg-surface-main disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          <ChevronLeft size={14} />
        </button>
        {pageNumbers().map((p, i) =>
          p === '…' ? (
            <span key={`ellipsis-${i}`} className="text-xs text-text-secondary px-1">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onPage(p as number)}
              className={`${btnBase} ${
                p === page
                  ? 'bg-primary text-white border border-primary'
                  : 'border border-border-subtle text-text-secondary hover:bg-surface-main'
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          className={`${btnBase} border border-border-subtle text-text-secondary hover:bg-surface-main disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
