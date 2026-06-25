import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { relTime, fmtTableDatetime } from '../utils/formatters';
import CollectionFilterDrawer from '../components/CollectionFilterDrawer';
import RunAllModal from '../components/RunAllModal';
import PaginationBar from '../components/PaginationBar';
import { useCollections } from '../hooks/useCollections';
import {
  Sparkles, Check, ArrowRight, CheckCircle2, FlaskConical,
  X, FolderPlus, Search, Calendar, Play, Trash2, Folder,
  Pencil, ListFilter,
} from 'lucide-react';

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 overflow-y-auto min-h-[calc(100vh-64px)]"
      style={{ animation: 'fadeUp 0.6s ease-out both' }}
    >
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes floatBounce1 {
          0%, 100% { transform: translateY(0); }
          50%       { transform: translateY(-10px); }
        }
        @keyframes floatBounce2 {
          0%, 100% { transform: translateY(0); }
          50%       { transform: translateY(-10px); }
        }
        .float-1 { animation: floatBounce1 4s ease-in-out infinite; }
        .float-2 { animation: floatBounce2 3s ease-in-out infinite 1s; }
      `}</style>

      <div className="max-w-4xl w-full grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        <div className="space-y-8 order-2 lg:order-1">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-label-sm font-label-sm">
              <Sparkles size={14} />
              AI-Powered Automation
            </div>
            <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight leading-tight">
              Welcome to PubLive! This is your first collection.
            </h2>
            <p className="text-text-secondary font-body-medium text-lg leading-relaxed">
              Collections are your starting point for building and managing AI-powered automated
              tests. You can use this one to:
            </p>
          </div>
          <ul className="space-y-4">
            {[
              'Group related test cases into logical suites',
              'Run real-world automation scenarios with our AI agent',
            ].map((text, i) => (
              <li key={i} className="flex items-start gap-4 group">
                <div className="mt-1 w-6 h-6 rounded-full bg-surface-container-highest flex items-center justify-center flex-shrink-0 group-hover:bg-primary/20 transition-colors">
                  <Check size={16} className="text-primary" />
                </div>
                <span className="text-text-primary font-body-base leading-snug">{text}</span>
              </li>
            ))}
          </ul>
          <div className="pt-4">
            <button
              onClick={onCreate}
              className="bg-primary hover:bg-primary/90 text-white px-8 py-4 rounded-xl font-headline-sm text-headline-sm transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/20 active:translate-y-0 flex items-center gap-3"
            >
              <span>Create Your First Test</span>
              <ArrowRight size={20} />
            </button>
          </div>
        </div>

        <div className="order-1 lg:order-2 flex justify-center lg:justify-end">
          <div className="relative w-full aspect-square max-w-[400px]">
            <div className="absolute inset-0 bg-gradient-to-tr from-primary/5 to-transparent rounded-full blur-3xl opacity-50" />
            <div className="absolute top-1/4 -right-4 w-24 h-24 bg-surface-container-highest rounded-full blur-2xl opacity-40 animate-pulse" />
            <div className="relative z-10 w-full h-full bg-white/40 backdrop-blur-sm rounded-[32px] border border-white/60 shadow-2xl flex items-center justify-center p-12 group overflow-hidden">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDP0Y83AhE1Nsc9z29jfgETAHJkc_S_knr3kisuTiVdmmjFYT9OOsrnpdmnn1x5MxXo7icC5Un8MaxMNjWYpCKPQUR_MGRxoyPP7lMKupqN1vd5EEnBe40jyFCpxLH1FOuYM6Zxz234qIRd1UUW32yRiVhbXc3SiV4iBqOyNK9weWl9GeYz80G_qSmsFVB8V8YydYc0JGrbyBZ-r-dt4FviwKu5f2eDRs3TTVjAsYAvTpOXb3sfhIPjUd0mO5ANZ1i2fk3LKKFZU6_G"
                alt="AI Test Automation Illustration"
                className="w-full h-auto object-contain transition-transform duration-700 group-hover:scale-105"
              />
              <div className="float-1 absolute top-8 left-8 bg-white shadow-lg rounded-xl p-3 border border-border-subtle">
                <CheckCircle2 size={24} className="text-success" />
              </div>
              <div className="float-2 absolute bottom-12 right-8 bg-white shadow-lg rounded-xl p-3 border border-border-subtle">
                <FlaskConical size={24} className="text-primary" />
              </div>
            </div>
            <div className="absolute -bottom-6 -left-12 bg-[#0F172A] text-[#94A3B8] p-4 rounded-xl border border-white/10 shadow-2xl font-mono-code text-[11px] max-w-[200px] hidden md:block">
              <div className="flex gap-1.5 mb-2">
                <div className="w-2 h-2 rounded-full bg-red-500/50" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
                <div className="w-2 h-2 rounded-full bg-green-500/50" />
              </div>
              <p className="text-primary-fixed">await agent.execute({'{'}</p>
              <p className="pl-4">context: <span className="text-success">"collection_01"</span>,</p>
              <p className="pl-4">mode: <span className="text-warning">"autonomous"</span></p>
              <p className="text-primary-fixed">{'}'});</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Modals ────────────────────────────────────────────────────────────────────

function CreateCollectionModal({
  loading, error, onClose, onSubmit,
}: {
  loading: boolean; error: string; onClose: () => void; onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState('');
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">New Collection</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <X size={20} />
          </button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()); }}
          className="px-6 py-5 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Collection name <span className="text-error">*</span>
            </label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Article Creation"
              className="w-full border border-border-subtle rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
            />
          </div>
          {error && <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RenameCollectionModal({
  initialName, loading, error, onClose, onSubmit,
}: {
  initialName: string; loading: boolean; error: string; onClose: () => void; onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState(initialName);
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">Rename Collection</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <X size={20} />
          </button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); if (name.trim() && name.trim() !== initialName) onSubmit(name.trim()); }}
          className="px-6 py-5 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Collection name</label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-border-subtle rounded-lg px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
            />
          </div>
          {error && <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || name.trim() === initialName || loading}
              className="flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function Collections() {
  const navigate = useNavigate();

  const [createOpen,     setCreateOpen]     = useState(false);
  const [selectedColIds, setSelectedColIds] = useState<Set<string>>(new Set());
  const [renamingCol,    setRenamingCol]    = useState<{ id: string; name: string } | null>(null);
  const [runAllColIds,   setRunAllColIds]   = useState<string[] | null>(null);
  const [colFilterOpen,  setColFilterOpen]  = useState(false);
  const selectAllRef = useRef<HTMLInputElement>(null);

  const {
    collections, filteredCollections, pagedCollections,
    page, setPage, totalPages, pageSize,
    isLoading,
    search, setSearch, colFilters, setColFilters,
    dateActive, filtersActive, dateRangeLabel, clearAllFilters,
    createMutation, deleteMutation: deleteCollectionMutation, renameMutation,
  } = useCollections();

  // Sync select-all checkbox indeterminate state
  useEffect(() => {
    if (!selectAllRef.current) return;
    const all = filteredCollections.length > 0 && filteredCollections.every((c) => selectedColIds.has(c.id));
    const some = filteredCollections.some((c) => selectedColIds.has(c.id));
    selectAllRef.current.indeterminate = some && !all;
    selectAllRef.current.checked = all;
  }, [selectedColIds, filteredCollections]);

  function handleDeleteSelected() {
    const count = selectedColIds.size;
    if (!window.confirm(`Delete ${count} collection${count === 1 ? '' : 's'} and all their tests?`)) return;
    selectedColIds.forEach((id) => deleteCollectionMutation.mutate(id));
    setSelectedColIds(new Set());
  }

  function handleDeleteSingle(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm('Delete this collection and all its tests?')) return;
    deleteCollectionMutation.mutate(id);
    setSelectedColIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }

  function toggleColSelection(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    setSelectedColIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    const allSelected = filteredCollections.every((c) => selectedColIds.has(c.id));
    setSelectedColIds(allSelected ? new Set() : new Set(filteredCollections.map((c) => c.id)));
  }

  function handleCreateCollection(name: string) {
    createMutation.mutate(name, {
      onSuccess: (res) => {
        setCreateOpen(false);
        if (res.data?.id) navigate(`/collections/${res.data.id}`);
      },
    });
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (collections.length === 0) {
    return (
      <>
        <EmptyState onCreate={() => setCreateOpen(true)} />
        {createOpen && (
          <CreateCollectionModal
            loading={createMutation.isPending}
            error={createMutation.error?.message ?? ''}
            onClose={() => { setCreateOpen(false); createMutation.reset(); }}
            onSubmit={handleCreateCollection}
          />
        )}
      </>
    );
  }

  return (
    <div className="p-8 max-w-7xl">

      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Collections</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {filteredCollections.length} {filteredCollections.length === 1 ? 'collection' : 'collections'}
            {filtersActive ? ' matching filters' : ''}
          </p>
        </div>
        <button
          onClick={() => { setCreateOpen(true); createMutation.reset(); }}
          className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0 active:scale-[0.98]"
        >
          <FolderPlus size={18} />
          New Collection
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap mb-5">
        <div className="relative">
          <Search size={18} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search collections…"
            className="w-64 border border-border-subtle rounded-xl pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
          />
        </div>

        {dateActive && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
            <Calendar size={12} />
            {dateRangeLabel}
            <button onClick={() => setColFilters((f) => ({ ...f, from: '', to: '' }))} className="hover:text-primary/60 transition-colors">
              <X size={12} />
            </button>
          </span>
        )}

        {filtersActive && (
          <button onClick={clearAllFilters} className="text-xs text-text-secondary hover:text-error transition-colors">
            Clear all
          </button>
        )}

        <div className="ml-auto flex items-center gap-2">
          {selectedColIds.size > 0 && (
            <>
              <button
                onClick={() => setRunAllColIds(Array.from(selectedColIds))}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border border-success/30 bg-success/5 text-success hover:bg-success/10 transition-all duration-150 active:scale-[0.98]"
              >
                <Play size={16} />
                Run {selectedColIds.size} selected
              </button>
              <button
                onClick={handleDeleteSelected}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border border-error/30 bg-error/5 text-error hover:bg-error/10 transition-all duration-150 active:scale-[0.98]"
              >
                <Trash2 size={16} />
                Delete {selectedColIds.size} selected
              </button>
            </>
          )}
          <button
            onClick={() => setColFilterOpen(true)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
              dateActive ? 'border-primary bg-primary/10 text-primary' : 'border-border-subtle text-text-secondary hover:bg-surface-muted'
            }`}
          >
            <ListFilter size={16} />
            Filters
            {dateActive && (
              <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white text-[10px] font-bold leading-none">1</span>
            )}
          </button>
        </div>
      </div>

      {/* Collections table */}
      <div className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-surface-muted border-b border-border-subtle">
              <th className="px-4 py-3.5" style={{ width: 44 }}>
                <input
                  ref={selectAllRef}
                  type="checkbox"
                  onClick={(e) => e.stopPropagation()}
                  onChange={toggleSelectAll}
                  className="w-4 h-4 rounded accent-primary cursor-pointer"
                />
              </th>
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary">Collection</th>
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 200 }}>Created at</th>
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 120 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCollections.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-16 text-center text-sm text-text-secondary">
                  {collections.length === 0 ? 'No collections yet.' : 'No collections match your filters.'}
                </td>
              </tr>
            ) : (
              pagedCollections.map((col) => {
                const isChecked = selectedColIds.has(col.id);
                return (
                  <tr
                    key={col.id}
                    onClick={() => navigate(`/collections/${col.id}`)}
                    className={`group cursor-pointer transition-all duration-150 border-b border-border-subtle ${
                      isChecked ? 'bg-primary/5' : 'hover:bg-surface-muted/50'
                    }`}
                  >
                    <td className="px-4 py-3.5" onClick={(e) => toggleColSelection(col.id, e)}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}}
                        className="w-4 h-4 rounded accent-primary cursor-pointer"
                      />
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <Folder size={18} className="text-text-secondary" />
                        <span className="font-medium text-text-primary text-sm">{col.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      {(() => {
                        const { date, time } = fmtTableDatetime(col.createdAt);
                        return (
                          <time title={relTime(col.createdAt)} dateTime={col.createdAt} className="flex flex-col">
                            <span className="text-sm text-text-primary">{date}</span>
                            <span className="text-xs text-text-secondary mt-0.5">{time}</span>
                          </time>
                        );
                      })()}
                    </td>
                    <td className="px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-0.5 opacity-40 group-hover:opacity-100 transition-opacity duration-150">
                        <button
                          onClick={() => setRunAllColIds([col.id])}
                          title="Run all specs"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-success hover:bg-success/10 transition-colors"
                        >
                          <Play size={17} />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setRenamingCol({ id: col.id, name: col.name }); renameMutation.reset(); }}
                          title="Rename collection"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
                        >
                          <Pencil size={17} />
                        </button>
                        <button
                          onClick={(e) => handleDeleteSingle(col.id, e)}
                          title="Delete collection"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error transition-colors"
                        >
                          <Trash2 size={17} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={filteredCollections.length}
          pageSize={pageSize}
          onPage={setPage}
          alwaysShow
        />
      </div>

      {/* Modals */}

      {createOpen && (
        <CreateCollectionModal
          loading={createMutation.isPending}
          error={createMutation.error?.message ?? ''}
          onClose={() => { setCreateOpen(false); createMutation.reset(); }}
          onSubmit={handleCreateCollection}
        />
      )}

      {renamingCol && (
        <RenameCollectionModal
          initialName={renamingCol.name}
          loading={renameMutation.isPending}
          error={renameMutation.error?.message ?? ''}
          onClose={() => { setRenamingCol(null); renameMutation.reset(); }}
          onSubmit={(name) => renameMutation.mutate(
            { id: renamingCol.id, name },
            { onSuccess: () => { setRenamingCol(null); renameMutation.reset(); } },
          )}
        />
      )}

      {runAllColIds && (
        <RunAllModal collectionIds={runAllColIds} onClose={() => setRunAllColIds(null)} />
      )}

      <CollectionFilterDrawer
        open={colFilterOpen}
        onClose={() => setColFilterOpen(false)}
        value={colFilters}
        onApply={setColFilters}
      />
    </div>
  );
}
