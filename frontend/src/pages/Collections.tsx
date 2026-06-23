import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiResponse, Collection, Test, SpecFile } from '../types';
import RunTestModal from '../components/RunTestModal';
import CreateTestSlideOver from '../components/CreateTestSlideOver';
import SpecEditor from '../components/SpecEditor';
import TestExecutionDetail from '../components/TestExecutionDetail';
import EditTestSlideOver from '../components/EditTestSlideOver';
import { relTime, fmtDate } from '../utils/formatters';
import { ACCENTS } from '../utils/status';
import CollectionFilterDrawer, { CollectionFilterState, DEFAULT_COLLECTION_FILTERS } from '../components/CollectionFilterDrawer';

// Spec View Modal

function SpecViewModal({ filename, onClose }: { filename: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['specContent', filename],
    queryFn: () => api.get<{ data: { content: string }; error: string | null }>(`/specs/view?file=${encodeURIComponent(filename)}`),
    enabled: !!filename,
  });

  const lines = (data?.data?.content ?? '').split('\n');

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-[#0F172A] rounded-2xl shadow-2xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <span className="font-mono-code text-xs text-[#94A3B8] truncate">{filename}</span>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg text-[#94A3B8] hover:text-white transition-colors ml-4 flex-shrink-0">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>
        {/* Code */}
        <div className="overflow-auto flex-1 p-4">
          {isLoading ? (
            <div className="flex justify-center py-10">
              <div className="w-5 h-5 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
            </div>
          ) : (
            <table className="w-full border-collapse">
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i} className="hover:bg-white/5">
                    <td className="select-none text-right pr-4 text-[#4B5563] font-mono-code text-xs w-10 leading-5">{i + 1}</td>
                    <td className="font-mono-code text-xs text-[#E2E8F0] leading-5 whitespace-pre">{line || ' '}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// Run All Modal

function RunAllModal({
  onClose, onRun, isPending,
}: {
  onClose: () => void;
  onRun: (envId: string) => void;
  isPending: boolean;
}) {
  const { data: envsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.get<{ data: Array<{ id: string; name: string; isActive: boolean }>; error: string | null }>('/environments'),
  });
  const environments = (envsData?.data ?? []).filter((e) => e.isActive);
  const [envId, setEnvId] = useState(environments[0]?.id ?? '');

  useEffect(() => {
    if (environments.length > 0 && !envId) setEnvId(environments[0].id);
  }, [environments, envId]);

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
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
              Cancel
            </button>
            <button
              onClick={() => envId && onRun(envId)}
              disabled={!envId || isPending}
              className="flex-1 bg-success text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-success/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-1.5"
            >
              {isPending ? (
                <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Running…</>
              ) : (
                <><span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span>Run All</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helpers

function findMatchingSpec(testName: string, specs: SpecFile[]): SpecFile | null {
  const kebab = testName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  const kebabMatch = specs.find((s) => s.basename.startsWith(kebab));
  if (kebabMatch) return kebabMatch;
  const words = testName.toLowerCase().split(/\s+/).filter((w) => w.length >= 3);
  return specs.find((s) => words.some((w) => s.basename.toLowerCase().includes(w))) ?? null;
}

// Empty State

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 overflow-y-auto min-h-[calc(100vh-64px)]"
      style={{
        animation: 'fadeUp 0.6s ease-out both',
      }}
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

        {/* Left: content */}
        <div className="space-y-8 order-2 lg:order-1">
          <div className="space-y-4">
            {/* AI badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-label-sm font-label-sm">
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}
              >
                auto_awesome
              </span>
              AI-Powered Automation
            </div>

            {/* Heading */}
            <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight leading-tight">
              Welcome to PubLive! This is your first collection.
            </h2>

            {/* Description */}
            <p className="text-text-secondary font-body-medium text-lg leading-relaxed">
              Collections are your starting point for building and managing AI-powered automated
              tests. You can use this one to:
            </p>
          </div>

          {/* Bullet list */}
          <ul className="space-y-4">
            {[
              'Group related test cases into logical suites',
              'Run real-world automation scenarios with our AI agent',
            ].map((text, i) => (
              <li key={i} className="flex items-start gap-4 group">
                <div className="mt-1 w-6 h-6 rounded-full bg-surface-container-highest flex items-center justify-center flex-shrink-0 group-hover:bg-primary/20 transition-colors">
                  <span
                    className="material-symbols-outlined text-primary"
                    style={{ fontSize: 16, fontVariationSettings: '"wght" 600' }}
                  >
                    check
                  </span>
                </div>
                <span className="text-text-primary font-body-base leading-snug">{text}</span>
              </li>
            ))}
          </ul>

          {/* CTA */}
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

        {/* Right: illustration */}
        <div className="order-1 lg:order-2 flex justify-center lg:justify-end">
          <div className="relative w-full aspect-square max-w-[400px]">
            {/* Decorative blurs */}
            <div className="absolute inset-0 bg-gradient-to-tr from-primary/5 to-transparent rounded-full blur-3xl opacity-50" />
            <div className="absolute top-1/4 -right-4 w-24 h-24 bg-surface-container-highest rounded-full blur-2xl opacity-40 animate-pulse" />

            {/* Main card */}
            <div className="relative z-10 w-full h-full bg-white/40 backdrop-blur-sm rounded-[32px] border border-white/60 shadow-2xl flex items-center justify-center p-12 group overflow-hidden">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDP0Y83AhE1Nsc9z29jfgETAHJkc_S_knr3kisuTiVdmmjFYT9OOsrnpdmnn1x5MxXo7icC5Un8MaxMNjWYpCKPQUR_MGRxoyPP7lMKupqN1vd5EEnBe40jyFCpxLH1FOuYM6Zxz234qIRd1UUW32yRiVhbXc3SiV4iBqOyNK9weWl9GeYz80G_qSmsFVB8V8YydYc0JGrbyBZ-r-dt4FviwKu5f2eDRs3TTVjAsYAvTpOXb3sfhIPjUd0mO5ANZ1i2fk3LKKFZU6_G"
                alt="AI Test Automation Illustration"
                className="w-full h-auto object-contain transition-transform duration-700 group-hover:scale-105"
              />

              {/* Floating badge — top left */}
              <div className="float-1 absolute top-8 left-8 bg-white shadow-lg rounded-xl p-3 border border-border-subtle">
                <span
                  className="material-symbols-outlined text-success"
                  style={{ fontVariationSettings: '"FILL" 1' }}
                >
                  check_circle
                </span>
              </div>

              {/* Floating badge — bottom right */}
              <div className="float-2 absolute bottom-12 right-8 bg-white shadow-lg rounded-xl p-3 border border-border-subtle">
                <span
                  className="material-symbols-outlined text-primary"
                  style={{ fontVariationSettings: '"FILL" 1' }}
                >
                  science
                </span>
              </div>
            </div>

            {/* Code snippet — bottom left */}
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

// Create Collection Modal

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
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
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

// Collections Page

export default function Collections() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedColId = searchParams.get('col');

  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState('');
  const [slideOverOpen, setSlideOverOpen] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [expandedTestId, setExpandedTestId] = useState<string | null>(null);
  const [runModal, setRunModal] = useState<{ testId: string; testName: string } | null>(null);
  const [editingTest, setEditingTest] = useState<Test | null>(null);
  const [editError, setEditError] = useState('');
  const [specEditorTest] = useState<Test | null>(null);
  const [specEditorOpen, setSpecEditorOpen] = useState(false);
  const [viewingSpec, setViewingSpec] = useState<string | null>(null);
  // spec file opened directly in SpecEditor (not via test object)
  const [specFileEditing, setSpecFileEditing] = useState<SpecFile | null>(null);
  const [runAllOpen, setRunAllOpen] = useState(false);

  // Collections filter (root view): inline name search + date-range drawer
  const [search, setSearch] = useState('');
  const [colFilters, setColFilters] = useState<CollectionFilterState>(DEFAULT_COLLECTION_FILTERS);
  const [colFilterOpen, setColFilterOpen] = useState(false);

  // Queries

  const collectionsQ = useQuery({
    queryKey: ['collections'],
    queryFn: () => api.get<ApiResponse<Collection[]>>('/collections'),
  });
  const testsQ = useQuery({
    queryKey: ['tests', selectedColId],
    queryFn: () => api.get<ApiResponse<Test[]>>(`/collections/${selectedColId}/tests`),
    enabled: !!selectedColId,
  });
  const specsQ = useQuery({
    queryKey: ['specs', selectedColId],
    queryFn: () => api.get<ApiResponse<SpecFile[]>>(`/collections/${selectedColId}/specs`),
    enabled: !!selectedColId,
    refetchInterval: 5000,
  });

  const collections = collectionsQ.data?.data ?? [];
  const tests = testsQ.data?.data ?? [];
  const specs = specsQ.data?.data ?? [];
  const selectedCollection = collections.find((c) => c.id === selectedColId);

  // Root-view filtering (client-side over the loaded collections list)
  const dateActive = !!(colFilters.from || colFilters.to);
  const filtersActive = !!search.trim() || dateActive;
  const filteredCollections = useMemo(() => {
    const q = search.trim().toLowerCase();
    return collections.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q)) return false;
      const day = c.createdAt.slice(0, 10);
      if (colFilters.from && day < colFilters.from) return false;
      if (colFilters.to && day > colFilters.to) return false;
      return true;
    });
  }, [collections, search, colFilters]);

  const dateRangeLabel = [
    colFilters.from ? fmtDate(`${colFilters.from}T12:00:00Z`) : null,
    colFilters.to ? fmtDate(`${colFilters.to}T12:00:00Z`) : null,
  ].filter(Boolean).join(' – ');

  function clearAllFilters() {
    setSearch('');
    setColFilters(DEFAULT_COLLECTION_FILTERS);
  }

  // If selected collection was deleted, go back to root
  useEffect(() => {
    if (selectedColId && collections.length > 0 && !collections.find((c) => c.id === selectedColId)) {
      setSearchParams({}, { replace: true });
    }
  }, [collections, selectedColId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close card menu on outside click
  useEffect(() => {
    if (!openMenu) return;
    const close = () => setOpenMenu(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [openMenu]);

  // Mutations

  const createCollectionMut = useMutation({
    mutationFn: (name: string) => api.post<ApiResponse<Collection>>('/collections', { name }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setCreateOpen(false);
      setCreateError('');
      if (res.data?.id) setSearchParams({ col: res.data.id }, { replace: true });
    },
    onError: (err: Error) => setCreateError(err.message),
  });

  const deleteCollectionMut = useMutation({
    mutationFn: (id: string) => api.del(`/collections/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collections'] }),
  });

  const deleteTestMut = useMutation({
    mutationFn: (id: string) => api.del(`/tests/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tests', selectedColId] }),
  });

  const updateTestMut = useMutation({
    mutationFn: ({
      id, name, prompt, status, collection_id, environment_ids, duplicate,
    }: {
      id: string; name: string; prompt: string; status: string;
      collection_id: string; environment_ids: string[]; duplicate: boolean;
    }) => api.put(`/tests/${id}`, { name, prompt, status, collection_id, environment_ids, duplicate }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', selectedColId] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setEditingTest(null);
      setEditError('');
    },
    onError: (err: Error) => setEditError(err.message),
  });

  const runAllSpecsMut = useMutation({
    mutationFn: ({ colId, envId }: { colId: string; envId: string }) =>
      api.post<ApiResponse<{ executionId: string }>>(`/collections/${colId}/run-all-specs`, { environmentId: envId }),
    onSuccess: () => {
      setRunAllOpen(false);
      queryClient.invalidateQueries({ queryKey: ['executions'] });
    },
  });

  // Handlers

  function handleDeleteCollection(id: string) {
    if (!window.confirm('Delete this collection and all its tests?')) return;
    deleteCollectionMut.mutate(id);
  }

  function handleDeleteTest(id: string) {
    if (!window.confirm('Delete this test case?')) return;
    deleteTestMut.mutate(id);
  }

  if (collectionsQ.isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  // Empty

  if (collections.length === 0) {
    return (
      <>
        <EmptyState onCreate={() => setCreateOpen(true)} />
        {createOpen && (
          <CreateCollectionModal
            loading={createCollectionMut.isPending}
            error={createError}
            onClose={() => { setCreateOpen(false); setCreateError(''); }}
            onSubmit={(name) => createCollectionMut.mutate(name)}
          />
        )}
      </>
    );
  }

  function handleTestCreated() {
    queryClient.invalidateQueries({ queryKey: ['tests', selectedColId] });
    queryClient.invalidateQueries({ queryKey: ['collections'] });
  }

  // Loaded

  return (
    <div className="p-8 max-w-7xl">

      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        {selectedCollection ? (
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setExpandedTestId(null); setSearchParams({}); }}
              className="w-9 h-9 flex items-center justify-center rounded-xl border border-border-subtle hover:bg-surface-muted transition-colors"
            >
              <span className="material-symbols-outlined text-text-secondary" style={{ fontSize: 18 }}>arrow_back</span>
            </button>
            <div>
              <nav className="flex items-center gap-1 text-xs text-text-secondary mb-0.5">
                <button
                  onClick={() => { setExpandedTestId(null); setSearchParams({}); }}
                  className="hover:text-primary transition-colors"
                >Collections</button>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
                <span className="text-text-primary font-medium">{selectedCollection.name}</span>
              </nav>
              <h1 className="text-xl font-bold text-text-primary">{selectedCollection.name}</h1>
            </div>
          </div>
        ) : (
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Collections</h1>
            <p className="text-sm text-text-secondary mt-0.5">
              {filteredCollections.length} {filteredCollections.length === 1 ? 'collection' : 'collections'}
              {filtersActive ? ' matching filters' : ''}
            </p>
          </div>
        )}
        <div className="flex items-center gap-3">
          {selectedCollection ? (
            <>
              <button
                onClick={() => specs.length > 0 && setRunAllOpen(true)}
                disabled={specs.length === 0}
                title={specs.length === 0 ? 'No spec files yet' : `Run all ${specs.length} spec file${specs.length === 1 ? '' : 's'}`}
                className={`inline-flex items-center gap-2 border border-border-subtle rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                  specs.length === 0 ? 'text-text-secondary opacity-40 cursor-not-allowed' : 'text-text-secondary hover:bg-surface-muted'
                }`}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>play_circle</span>
                Run suite
              </button>
              <button
                onClick={() => setSlideOverOpen(true)}
                className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0"
              >
                Add Test
              </button>
            </>
          ) : (
            <button
              onClick={() => { setCreateOpen(true); setCreateError(''); }}
              className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>create_new_folder</span>
              New Collection
            </button>
          )}
        </div>
      </div>

      {selectedCollection ? (
        /* Tests table (inside a collection) */
        <div className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-muted border-b border-border-subtle">
                <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary">Test</th>
                <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary">Spec</th>
                <th className="px-4 py-3.5" style={{ width: 160 }} />
                <th className="px-4 py-3.5" style={{ width: 48 }} />
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {testsQ.isLoading || specsQ.isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-4 py-4" colSpan={4}><div className="h-6 bg-surface-muted rounded" /></td>
                  </tr>
                ))
              ) : tests.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-16 text-center">
                    <span className="material-symbols-outlined text-border-subtle block mb-2" style={{ fontSize: 40 }}>folder_open</span>
                    <p className="text-text-primary font-medium">No tests yet</p>
                    <p className="text-sm text-text-secondary mt-1">Click "Add Test" to get started</p>
                  </td>
                </tr>
              ) : (
                tests.flatMap((test, idx) => {
                  const spec = findMatchingSpec(test.name, specs);
                  const accent = ACCENTS[idx % ACCENTS.length];
                  const isExpanded = expandedTestId === test.id;
                  return [
                    <tr
                      key={test.id}
                      onClick={() => setExpandedTestId(isExpanded ? null : test.id)}
                      className={`group cursor-pointer transition-colors ${isExpanded ? 'bg-primary/5' : 'hover:bg-surface-muted/50'}`}
                    >
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 ${isExpanded ? 'bg-primary/10' : accent.bg} rounded-lg flex items-center justify-center flex-shrink-0`}>
                            <span
                              className={`material-symbols-outlined ${isExpanded ? 'text-primary' : accent.icon}`}
                              style={{ fontSize: 20, fontVariationSettings: '"FILL" 1' }}
                            >
                              {spec ? 'folder' : 'folder_open'}
                            </span>
                          </div>
                          <span className="font-medium text-text-primary text-sm leading-snug line-clamp-1">{test.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-sm">
                        {spec
                          ? <span className="font-mono-code text-xs text-text-secondary">{spec.basename}</span>
                          : <span className="italic text-text-secondary">No spec generated yet</span>
                        }
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setRunModal({ testId: test.id, testName: test.name })}
                            title={spec ? 'Re-run pipeline' : 'Run pipeline'}
                            className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${spec ? 'text-success hover:bg-success/10' : 'text-warning hover:bg-warning/10'}`}
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span>
                          </button>
                          <button
                            onClick={() => { setEditingTest(test); setEditError(''); }}
                            title="Edit test"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>edit</span>
                          </button>
                          {spec && (
                            <button
                              onClick={() => setSpecFileEditing(spec)}
                              title="Edit spec code"
                              className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:text-primary hover:bg-primary/5 transition-colors"
                            >
                              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>code</span>
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteTest(test.id)}
                            title="Delete test"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error transition-colors"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`material-symbols-outlined text-text-secondary transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} style={{ fontSize: 18 }}>
                          expand_more
                        </span>
                      </td>
                    </tr>,
                    ...(isExpanded ? [<TestExecutionDetail key={`detail-${test.id}`} testId={test.id} colSpan={4} />] : []),
                  ];
                })
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* Collections table (root view) */
        <>
          {/* Filter bar */}
          <div className="flex items-center gap-2 flex-wrap mb-5">
            {/* Name search */}
            <div className="relative">
              <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" style={{ fontSize: 18 }}>search</span>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search collections…"
                className="w-64 border border-border-subtle rounded-xl pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
              />
            </div>

            {/* Active date-range chip */}
            {dateActive && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                <span className="material-symbols-outlined" style={{ fontSize: 12 }}>calendar_today</span>
                {dateRangeLabel}
                <button onClick={() => setColFilters(DEFAULT_COLLECTION_FILTERS)} className="hover:text-primary/60 transition-colors">
                  <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
                </button>
              </span>
            )}

            {filtersActive && (
              <button onClick={clearAllFilters} className="text-xs text-text-secondary hover:text-error transition-colors">
                Clear all
              </button>
            )}

            {/* Filters button */}
            <button
              onClick={() => setColFilterOpen(true)}
              className={`ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
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

          {/* Table */}
          <div className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-muted border-b border-border-subtle">
                  <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary">Collection</th>
                  <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 140 }}>Tests</th>
                  <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 200 }}>Created</th>
                  <th className="px-4 py-3.5" style={{ width: 64 }} />
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {filteredCollections.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-16 text-center text-sm text-text-secondary">
                      {collections.length === 0 ? 'No collections yet.' : 'No collections match your filters.'}
                    </td>
                  </tr>
                ) : (
                  filteredCollections.map((col) => {
                    const accent = ACCENTS[collections.indexOf(col) % ACCENTS.length];
                    return (
                      <tr
                        key={col.id}
                        onClick={() => { setExpandedTestId(null); setSearchParams({ col: col.id }); }}
                        className="group cursor-pointer hover:bg-surface-muted/50 transition-colors"
                      >
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-3">
                            <div className={`w-9 h-9 ${accent.bg} rounded-lg flex items-center justify-center flex-shrink-0`}>
                              <span className={`material-symbols-outlined ${accent.icon}`} style={{ fontSize: 20, fontVariationSettings: '"FILL" 1' }}>folder</span>
                            </div>
                            <span className="font-medium text-text-primary text-sm">{col.name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3.5 text-sm text-text-secondary">
                          {col.testCount} {col.testCount === 1 ? 'test' : 'tests'}
                        </td>
                        <td className="px-4 py-3.5 text-sm text-text-secondary">{relTime(col.createdAt)}</td>
                        <td className="px-4 py-3.5">
                          <div className="relative flex justify-end" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => setOpenMenu(openMenu === col.id ? null : col.id)}
                              className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary opacity-0 group-hover:opacity-100 hover:bg-surface-muted transition-all"
                            >
                              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>more_vert</span>
                            </button>
                            {openMenu === col.id && (
                              <div className="absolute top-9 right-0 bg-surface-main rounded-xl shadow-lg border border-border-subtle py-1 z-20 min-w-[140px]">
                                <button
                                  onClick={() => { setOpenMenu(null); handleDeleteCollection(col.id); }}
                                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-error hover:bg-error/5 transition-colors"
                                >
                                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Modals */}

      {createOpen && (
        <CreateCollectionModal
          loading={createCollectionMut.isPending}
          error={createError}
          onClose={() => { setCreateOpen(false); setCreateError(''); }}
          onSubmit={(name) => createCollectionMut.mutate(name)}
        />
      )}

      {editingTest && (
        <EditTestSlideOver
          test={editingTest}
          loading={updateTestMut.isPending}
          error={editError}
          onClose={() => { setEditingTest(null); setEditError(''); }}
          onSubmit={(payload) => updateTestMut.mutate({ id: editingTest.id, ...payload })}
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
          defaultCollectionId={selectedColId ?? undefined}
          onClose={() => setSlideOverOpen(false)}
          onTestCreated={handleTestCreated}
        />
      )}

      {/* SpecEditor for test objects (opened via code button on test rows) */}
      {specEditorOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60]"
          onClick={() => setSpecEditorOpen(false)}
        />
      )}
      <SpecEditor
        test={specEditorTest}
        isOpen={specEditorOpen}
        onClose={() => setSpecEditorOpen(false)}
        onRunStarted={(_execId) => queryClient.invalidateQueries({ queryKey: ['tests', selectedColId] })}
      />

      {/* SpecEditor for spec files (opened via run/edit buttons on spec file rows) */}
      {!!specFileEditing && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60]"
          onClick={() => setSpecFileEditing(null)}
        />
      )}
      <SpecEditor
        test={specFileEditing && tests[0] ? { id: tests[0].id, name: specFileEditing.basename } : null}
        isOpen={!!specFileEditing}
        onClose={() => setSpecFileEditing(null)}
        overrideFilename={specFileEditing?.filename}
        onRunStarted={(_execId) => {
          queryClient.invalidateQueries({ queryKey: ['executions'] });
          queryClient.invalidateQueries({ queryKey: ['specs', selectedColId] });
        }}
      />

      {/* Run All modal */}
      {runAllOpen && (
        <RunAllModal
          onClose={() => setRunAllOpen(false)}
          onRun={(envId) => runAllSpecsMut.mutate({ colId: selectedColId!, envId })}
          isPending={runAllSpecsMut.isPending}
        />
      )}

      {viewingSpec && (
        <SpecViewModal filename={viewingSpec} onClose={() => setViewingSpec(null)} />
      )}

      {/* Collections filter drawer (created date range) — always mounted for slide animation */}
      <CollectionFilterDrawer
        open={colFilterOpen}
        onClose={() => setColFilterOpen(false)}
        value={colFilters}
        onApply={setColFilters}
      />
    </div>
  );
}
