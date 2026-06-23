import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Test, SpecFile } from '../types';
import { collectionsService } from '../services/collections';
import RunTestModal from '../components/RunTestModal';
import CreateTestSlideOver from '../components/CreateTestSlideOver';
import SpecEditor from '../components/SpecEditor';
import TestExecutionDetail from '../components/TestExecutionDetail';
import EditTestSlideOver from '../components/EditTestSlideOver';
import { relTime, fmtTableDatetime } from '../utils/formatters';
import { ACCENTS } from '../utils/status';
import CollectionFilterDrawer from '../components/CollectionFilterDrawer';
import { environmentsService } from '../services/environments';
import { useCollections } from '../hooks/useCollections';
import { useCollectionTests } from '../hooks/useCollectionTests';

// ── Inline page-local components ────────────────────────────────────────────

function RunAllModal({ collectionId, onClose }: { collectionId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: envsData } = useQuery({
    queryKey: ['environments'],
    queryFn: environmentsService.getAll,
  });
  const environments = (envsData?.data ?? []).filter((e) => e.isActive);
  const [envId, setEnvId] = useState(environments[0]?.id ?? '');

  useEffect(() => {
    if (environments.length > 0 && !envId) setEnvId(environments[0].id);
  }, [environments, envId]);

  const runMutation = useMutation({
    mutationFn: (environmentId: string) => collectionsService.runAllSpecs(collectionId, environmentId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['executions'] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">Run All Specs</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Environment</label>
            <select
              value={envId}
              onChange={(e) => setEnvId(e.target.value)}
              className="w-full border border-border-subtle rounded-lg px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
            >
              {environments.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              {environments.length === 0 && <option disabled>No environments configured</option>}
            </select>
          </div>
          {runMutation.error && (
            <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">
              {runMutation.error.message}
            </p>
          )}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
              Cancel
            </button>
            <button
              onClick={() => envId && runMutation.mutate(envId)}
              disabled={!envId || runMutation.isPending}
              className="flex-1 bg-success text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-success/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-1.5"
            >
              {runMutation.isPending ? (
                <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Running…</>
              ) : (
                'Run All'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function findMatchingSpec(testName: string, specs: SpecFile[]): SpecFile | null {
  const kebab = testName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  const kebabMatch = specs.find((s) => s.basename.startsWith(kebab));
  if (kebabMatch) return kebabMatch;
  const words = testName.toLowerCase().split(/\s+/).filter((w) => w.length >= 3);
  return specs.find((s) => words.some((w) => s.basename.toLowerCase().includes(w))) ?? null;
}

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
              <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>auto_awesome</span>
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
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: 16, fontVariationSettings: '"wght" 600' }}>check</span>
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
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_forward</span>
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
                <span className="material-symbols-outlined text-success" style={{ fontVariationSettings: '"FILL" 1' }}>check_circle</span>
              </div>
              <div className="float-2 absolute bottom-12 right-8 bg-white shadow-lg rounded-xl p-3 border border-border-subtle">
                <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: '"FILL" 1' }}>science</span>
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

function CreateCollectionModal({
  loading, error, onClose, onSubmit,
}: {
  loading: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState('');
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">New Collection</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
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
          {error && (
            <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">{error}</p>
          )}
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
  initialName: string;
  loading: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState(initialName);
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">Rename Collection</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
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
          {error && (
            <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">{error}</p>
          )}
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
  const [searchParams, setSearchParams] = useSearchParams();
  const expandedColId = searchParams.get('col'); // which collection folder is open

  // UI state
  const [createOpen,      setCreateOpen]      = useState(false);
  const [slideOverOpen,   setSlideOverOpen]   = useState(false);
  const [selectedColIds,  setSelectedColIds]  = useState<Set<string>>(new Set());
  const [expandedTestId,  setExpandedTestId]  = useState<string | null>(null);
  const [renamingCol,     setRenamingCol]     = useState<{ id: string; name: string } | null>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const [runModal,        setRunModal]        = useState<{ testId: string; testName: string } | null>(null);
  const [editingTest,     setEditingTest]     = useState<Test | null>(null);
  const [specFileEditing, setSpecFileEditing] = useState<SpecFile | null>(null);
  const [runAllColId,     setRunAllColId]     = useState<string | null>(null);
  const [colFilterOpen,   setColFilterOpen]   = useState(false);

  // Data layer — hooks encapsulate all queries + mutations
  const {
    collections, filteredCollections, isLoading,
    search, setSearch, colFilters, setColFilters,
    dateActive, filtersActive, dateRangeLabel, clearAllFilters,
    createMutation, deleteMutation: deleteCollectionMutation, renameMutation,
  } = useCollections();

  const {
    tests, specs,
    isLoadingTests, isLoadingSpecs,
    deleteTestMutation, updateTestMutation,
    invalidateTests,
  } = useCollectionTests(expandedColId);

  // Close accordion if the expanded collection gets deleted
  useEffect(() => {
    if (expandedColId && collections.length > 0 && !collections.find((c) => c.id === expandedColId)) {
      setSearchParams({}, { replace: true });
    }
  }, [collections, expandedColId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync select-all checkbox indeterminate state
  useEffect(() => {
    if (!selectAllRef.current) return;
    const all = filteredCollections.length > 0 && filteredCollections.every((c) => selectedColIds.has(c.id));
    const some = filteredCollections.some((c) => selectedColIds.has(c.id));
    selectAllRef.current.indeterminate = some && !all;
    selectAllRef.current.checked = all;
  }, [selectedColIds, filteredCollections]);

  // Handlers
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

  function handleDeleteTest(id: string) {
    if (!window.confirm('Delete this test case?')) return;
    deleteTestMutation.mutate(id);
  }

  function handleCreateCollection(name: string) {
    createMutation.mutate(name, {
      onSuccess: (res) => {
        setCreateOpen(false);
        if (res.data?.id) setSearchParams({ col: res.data.id }, { replace: true });
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
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>create_new_folder</span>
          New Collection
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap mb-5">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" style={{ fontSize: 18 }}>search</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search collections…"
            className="w-64 border border-border-subtle rounded-xl pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
          />
        </div>

        {dateActive && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>calendar_today</span>
            {dateRangeLabel}
            <button onClick={() => setColFilters((f) => ({ ...f, from: '', to: '' }))} className="hover:text-primary/60 transition-colors">
              <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
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
            <button
              onClick={handleDeleteSelected}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border border-error/30 bg-error/5 text-error hover:bg-error/10 transition-all duration-150 active:scale-[0.98]"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
              Delete {selectedColIds.size} selected
            </button>
          )}
          <button
            onClick={() => setColFilterOpen(true)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
              dateActive ? 'border-primary bg-primary/10 text-primary' : 'border-border-subtle text-text-secondary hover:bg-surface-muted'
            }`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>filter_list</span>
            Filters
            {dateActive && (
              <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white text-[10px] font-bold leading-none">1</span>
            )}
          </button>
        </div>
      </div>

      {/* Collections table with inline folder expansion */}
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
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 140 }}>Tests</th>
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 200 }}>Created</th>
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 120 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCollections.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-16 text-center text-sm text-text-secondary">
                  {collections.length === 0 ? 'No collections yet.' : 'No collections match your filters.'}
                </td>
              </tr>
            ) : (
              filteredCollections.map((col) => {
                const isChecked  = selectedColIds.has(col.id);
                const isExpanded = expandedColId === col.id;
                return (
                  <tbody key={col.id} className="[&+tbody]:border-t [&+tbody]:border-border-subtle">
                    {/* Collection row */}
                    <tr
                      onClick={() => {
                        setExpandedTestId(null);
                        setSearchParams(isExpanded ? {} : { col: col.id });
                      }}
                      className={`group cursor-pointer transition-all duration-150 border-b border-border-subtle ${
                        isChecked ? 'bg-primary/5' : isExpanded ? 'bg-surface-muted/60' : 'hover:bg-surface-muted/50'
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
                          <span
                            className={`material-symbols-outlined transition-all duration-200 ${
                              isExpanded ? 'text-primary' : 'text-text-secondary'
                            }`}
                            style={{ fontSize: 18, fontVariationSettings: isExpanded ? '"FILL" 1' : '"FILL" 0' }}
                          >
                            {isExpanded ? 'folder_open' : 'folder'}
                          </span>
                          <span className="font-medium text-text-primary text-sm">{col.name}</span>
                          <span
                            className={`material-symbols-outlined text-text-secondary transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                            style={{ fontSize: 16 }}
                          >
                            expand_more
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-sm text-text-secondary">
                        {col.testCount} {col.testCount === 1 ? 'test' : 'tests'}
                      </td>
                      <td className="px-4 py-3.5">
                        {(() => { const { date, time } = fmtTableDatetime(col.createdAt); return (
                          <time title={relTime(col.createdAt)} dateTime={col.createdAt} className="flex flex-col">
                            <span className="text-sm text-text-primary">{date}</span>
                            <span className="text-xs text-text-secondary mt-0.5">{time}</span>
                          </time>
                        ); })()}
                      </td>
                      <td className="px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-0.5 opacity-40 group-hover:opacity-100 transition-opacity duration-150">
                          <button
                            onClick={() => setRunAllColId(col.id)}
                            title="Run all specs"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-success hover:bg-success/10 transition-colors"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 17 }}>play_arrow</span>
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); setRenamingCol({ id: col.id, name: col.name }); renameMutation.reset(); }}
                            title="Rename collection"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 17 }}>edit</span>
                          </button>
                          <button
                            onClick={(e) => handleDeleteSingle(col.id, e)}
                            title="Delete collection"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error transition-colors"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 17 }}>delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Inline tests panel */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={5} className="p-0 bg-surface-muted/20">
                          {/* Tests sub-header */}
                          <div className="flex items-center justify-between px-6 py-3 border-b border-border-subtle">
                            <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                              {isLoadingTests ? 'Loading…' : `${tests.length} ${tests.length === 1 ? 'test' : 'tests'}`}
                            </span>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => specs.length > 0 && setRunAllColId(col.id)}
                                disabled={specs.length === 0}
                                title={specs.length === 0 ? 'No spec files yet' : `Run all ${specs.length} spec file${specs.length === 1 ? '' : 's'}`}
                                className={`inline-flex items-center gap-1.5 border border-border-subtle rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                                  specs.length === 0 ? 'text-text-secondary opacity-40 cursor-not-allowed' : 'text-text-secondary hover:bg-surface-main'
                                }`}
                              >
                                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>play_circle</span>
                                Run suite
                              </button>
                              <button
                                onClick={() => setSlideOverOpen(true)}
                                className="inline-flex items-center gap-1.5 bg-primary text-white rounded-lg px-3 py-1.5 text-xs font-semibold hover:bg-primary/90 transition-colors"
                              >
                                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>add</span>
                                Add Test
                              </button>
                            </div>
                          </div>

                          {/* Tests table */}
                          <table className="w-full">
                            <tbody className="divide-y divide-border-subtle">
                              {isLoadingTests || isLoadingSpecs ? (
                                Array.from({ length: 2 }).map((_, i) => (
                                  <tr key={i} className="animate-pulse">
                                    <td className="px-6 py-4" colSpan={4}><div className="h-5 bg-surface-muted rounded" /></td>
                                  </tr>
                                ))
                              ) : tests.length === 0 ? (
                                <tr>
                                  <td colSpan={4} className="px-6 py-10 text-center">
                                    <span className="material-symbols-outlined text-border-subtle block mb-2" style={{ fontSize: 32 }}>folder_open</span>
                                    <p className="text-sm text-text-primary font-medium">No tests yet</p>
                                    <p className="text-xs text-text-secondary mt-1">Click "Add Test" to get started</p>
                                  </td>
                                </tr>
                              ) : (
                                tests.flatMap((test, idx) => {
                                  const spec       = findMatchingSpec(test.name, specs);
                                  const accent     = ACCENTS[idx % ACCENTS.length];
                                  const isTestOpen = expandedTestId === test.id;
                                  return [
                                    <tr
                                      key={test.id}
                                      onClick={() => setExpandedTestId(isTestOpen ? null : test.id)}
                                      className={`group cursor-pointer transition-colors ${isTestOpen ? 'bg-primary/5' : 'hover:bg-surface-muted/40'}`}
                                    >
                                      <td className="pl-6 pr-4 py-3">
                                        <div className="flex items-center gap-3">
                                          <div className={`w-8 h-8 ${isTestOpen ? 'bg-primary/10' : accent.bg} rounded-lg flex items-center justify-center flex-shrink-0`}>
                                            <span
                                              className={`material-symbols-outlined ${isTestOpen ? 'text-primary' : accent.icon}`}
                                              style={{ fontSize: 17, fontVariationSettings: '"FILL" 1' }}
                                            >
                                              {spec ? 'description' : 'draft'}
                                            </span>
                                          </div>
                                          <span className="font-medium text-text-primary text-sm leading-snug line-clamp-1">{test.name}</span>
                                        </div>
                                      </td>
                                      <td className="px-4 py-3 text-sm">
                                        {spec
                                          ? <span className="font-mono-code text-xs text-text-secondary bg-surface-muted px-2 py-0.5 rounded">{spec.basename}</span>
                                          : <span className="italic text-xs text-text-secondary">No spec yet</span>
                                        }
                                      </td>
                                      <td className="px-4 py-3">
                                        <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                                          <button
                                            onClick={() => setRunModal({ testId: test.id, testName: test.name })}
                                            title={spec ? 'Re-run pipeline' : 'Run pipeline'}
                                            className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${spec ? 'text-success hover:bg-success/10' : 'text-warning hover:bg-warning/10'}`}
                                          >
                                            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>play_arrow</span>
                                          </button>
                                          <button onClick={() => setEditingTest(test)} title="Edit test" className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
                                            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>edit</span>
                                          </button>
                                          {spec && (
                                            <button onClick={() => setSpecFileEditing(spec)} title="Edit spec code" className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:text-primary hover:bg-primary/5 transition-colors">
                                              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>code</span>
                                            </button>
                                          )}
                                          <button onClick={() => handleDeleteTest(test.id)} title="Delete test" className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error transition-colors">
                                            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>delete</span>
                                          </button>
                                        </div>
                                      </td>
                                      <td className="pr-4 py-3 w-10">
                                        <span className={`material-symbols-outlined text-text-secondary transition-transform duration-200 ${isTestOpen ? 'rotate-180' : ''}`} style={{ fontSize: 16 }}>
                                          expand_more
                                        </span>
                                      </td>
                                    </tr>,
                                    ...(isTestOpen ? [<TestExecutionDetail key={`detail-${test.id}`} testId={test.id} colSpan={4} />] : []),
                                  ];
                                })
                              )}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </tbody>
                );
              })
            )}
          </tbody>
        </table>
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

      {editingTest && (
        <EditTestSlideOver
          test={editingTest}
          loading={updateTestMutation.isPending}
          error={updateTestMutation.error?.message ?? ''}
          onClose={() => setEditingTest(null)}
          onSubmit={(payload) => {
            updateTestMutation.mutate(
              { id: editingTest.id, ...payload },
              { onSuccess: () => setEditingTest(null) },
            );
          }}
        />
      )}

      {runModal && (
        <RunTestModal
          testId={runModal.testId}
          testName={runModal.testName}
          onClose={() => setRunModal(null)}
        />
      )}

      {slideOverOpen && (
        <CreateTestSlideOver
          collections={collections}
          defaultCollectionId={expandedColId ?? undefined}
          onClose={() => setSlideOverOpen(false)}
          onTestCreated={invalidateTests}
        />
      )}

      {!!specFileEditing && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60]" onClick={() => setSpecFileEditing(null)} />
      )}
      <SpecEditor
        test={specFileEditing && tests[0] ? { id: tests[0].id, name: specFileEditing.basename } : null}
        isOpen={!!specFileEditing}
        onClose={() => setSpecFileEditing(null)}
        overrideFilename={specFileEditing?.filename}
        onRunStarted={() => invalidateTests()}
      />

      {runAllColId && (
        <RunAllModal
          collectionId={runAllColId}
          onClose={() => setRunAllColId(null)}
        />
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
