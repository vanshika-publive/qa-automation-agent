import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Test } from '../types';
import TestExecutionDetail from '../components/TestExecutionDetail';
import RunTestModal from '../components/RunTestModal';
import CreateTestSlideOver from '../components/CreateTestSlideOver';
import EditTestSlideOver from '../components/EditTestSlideOver';
import SpecEditor from '../components/SpecEditor';
import RunAllModal from '../components/RunAllModal';
import { ACCENTS } from '../utils/status';
import { useCollections } from '../hooks/useCollections';
import { useCollectionTests } from '../hooks/useCollectionTests';
import { testsService } from '../services/tests';
import {
  FolderX, ArrowLeft, FolderOpen, PlayCircle, Plus,
  Play, Pencil, Code2, Trash2, ChevronDown, FileText, Folder, X,
} from 'lucide-react';


export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { collections, isLoading: isLoadingCollections } = useCollections();
  const collection = collections.find((c) => c.id === id);

  const {
    tests, specs,
    isLoadingTests, isLoadingSpecs,
    deleteTestMutation, updateTestMutation,
    invalidateTests,
  } = useCollectionTests(id ?? null);

  const [expandedTestId, setExpandedTestId] = useState<string | null>(null);
  const [slideOverOpen,  setSlideOverOpen]  = useState(false);
  const [runModal,       setRunModal]       = useState<{ testId: string; testName: string } | null>(null);
  const [editingTest,    setEditingTest]    = useState<Test | null>(null);
  const [specEditing,    setSpecEditing]    = useState<Test | null>(null);
  const [runAllOpen,     setRunAllOpen]     = useState(false);
  const [planModal,      setPlanModal]      = useState<{ testName: string; content: string } | null>(null);
  const [planLoading,    setPlanLoading]    = useState<string | null>(null);

  async function handleOpenPlan(e: React.MouseEvent, test: Test) {
    e.stopPropagation();
    setPlanLoading(test.id);
    try {
      const res = await testsService.getPlan(test.id);
      if (res.data?.content) {
        setPlanModal({ testName: test.name, content: res.data.content });
      }
    } finally {
      setPlanLoading(null);
    }
  }

  function handleDeleteTest(testId: string) {
    if (!window.confirm('Delete this test case?')) return;
    deleteTestMutation.mutate(testId);
  }

  if (isLoadingCollections) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-64px)] gap-4">
        <FolderX size={48} className="text-border-subtle" />
        <p className="text-text-secondary text-sm">Collection not found.</p>
        <button onClick={() => navigate('/')} className="text-primary text-sm hover:underline">
          ← Back to Collections
        </button>
      </div>
    );
  }

  const isLoading = isLoadingTests || isLoadingSpecs;

  return (
    <div className="p-8 max-w-7xl">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="w-9 h-9 flex items-center justify-center rounded-xl border border-border-subtle text-text-secondary hover:bg-surface-muted transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="flex items-center gap-2.5">
              <FolderOpen size={20} className="text-primary" />
              <h1 className="text-2xl font-bold text-text-primary">{collection.name}</h1>
            </div>
            <p className="text-sm text-text-secondary mt-0.5">
              {isLoading ? 'Loading…' : `${tests.length} ${tests.length === 1 ? 'test' : 'tests'}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => specs.length > 0 && setRunAllOpen(true)}
            disabled={specs.length === 0}
            title={specs.length === 0 ? 'No spec files yet' : `Run all ${specs.length} spec file${specs.length === 1 ? '' : 's'}`}
            className={`inline-flex items-center gap-1.5 border border-border-subtle rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
              specs.length === 0
                ? 'text-text-secondary opacity-40 cursor-not-allowed'
                : 'text-text-secondary hover:bg-surface-muted'
            }`}
          >
            <PlayCircle size={16} />
            Run Suite
          </button>
          <button
            onClick={() => setSlideOverOpen(true)}
            className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0 active:scale-[0.98]"
          >
            <Plus size={16} />
            Add Test
          </button>
        </div>
      </div>

      {/* Tests table */}
      <div className="bg-surface-main rounded-2xl border border-border-subtle overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-surface-muted border-b border-border-subtle">
              <th className="text-left px-6 py-3.5 text-sm font-semibold text-text-primary">Test</th>
              <th className="text-left px-4 py-3.5 text-sm font-semibold text-text-primary" style={{ width: 220 }}>Plan</th>
              <th style={{ width: 130 }} />
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-border-subtle">
                  <td className="px-6 py-4"><div className="h-5 bg-surface-muted rounded w-48" /></td>
                  <td className="px-4 py-4"><div className="h-5 bg-surface-muted rounded w-32" /></td>
                  <td /><td />
                </tr>
              ))
            ) : tests.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-16 text-center">
                  <FolderOpen size={40} className="text-border-subtle mx-auto mb-2" />
                  <p className="text-sm text-text-primary font-medium">No tests yet</p>
                  <p className="text-xs text-text-secondary mt-1">Click "Add Test" to get started</p>
                </td>
              </tr>
            ) : (
              tests.flatMap((test, idx) => {
                const accent     = ACCENTS[idx % ACCENTS.length];
                const isTestOpen = expandedTestId === test.id;
                return [
                  <tr
                    key={test.id}
                    onClick={() => setExpandedTestId(isTestOpen ? null : test.id)}
                    className={`group cursor-pointer transition-colors border-b border-border-subtle ${
                      isTestOpen ? 'bg-primary/5' : 'hover:bg-surface-muted/40'
                    }`}
                  >
                    <td className="px-6 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 ${isTestOpen ? 'bg-primary/10' : accent.bg} rounded-lg flex items-center justify-center flex-shrink-0`}>
                          {test.specFile
                            ? <FileText size={17} className={isTestOpen ? 'text-primary' : accent.icon} />
                            : <Folder size={17} className={isTestOpen ? 'text-primary' : accent.icon} />
                          }
                        </div>
                        {test.specFile
                          ? <span className="font-mono-code text-xs text-text-secondary bg-surface-muted px-2 py-0.5 rounded break-all">{test.specFile.basename}</span>
                          : <span className="font-medium text-text-primary text-sm leading-snug line-clamp-2">{test.name}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      {test.planFile
                        ? (
                          <button
                            onClick={(e) => handleOpenPlan(e, test)}
                            disabled={planLoading === test.id}
                            className="font-mono-code text-xs text-primary bg-primary/10 hover:bg-primary/20 px-2 py-0.5 rounded transition-colors disabled:opacity-50"
                          >
                            {planLoading === test.id ? 'Loading…' : test.planFile}
                          </button>
                        )
                        : <span className="italic text-xs text-text-secondary">No plan yet</span>}
                    </td>
                    <td className="px-4 py-3.5">
                      <div
                        className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() => setRunModal({ testId: test.id, testName: test.name })}
                          title={test.specFile ? 'Re-run pipeline' : 'Run pipeline'}
                          className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${
                            test.specFile ? 'text-success hover:bg-success/10' : 'text-warning hover:bg-warning/10'
                          }`}
                        >
                          <Play size={15} />
                        </button>
                        <button
                          onClick={() => setEditingTest(test)}
                          title="Edit test"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
                        >
                          <Pencil size={15} />
                        </button>
                        {test.specFile && (
                          <button
                            onClick={() => setSpecEditing(test)}
                            title="Edit spec code"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:text-primary hover:bg-primary/5 transition-colors"
                          >
                            <Code2 size={15} />
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteTest(test.id)}
                          title="Delete test"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error transition-colors"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                    <td className="pr-4 py-3.5">
                      <ChevronDown
                        size={16}
                        className={`text-text-secondary transition-transform duration-200 ${isTestOpen ? 'rotate-180' : ''}`}
                      />
                    </td>
                  </tr>,
                  ...(isTestOpen
                    ? [<TestExecutionDetail key={`detail-${test.id}`} testId={test.id} colSpan={4} />]
                    : []),
                ];
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Modals */}

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
          defaultCollectionId={id}
          onClose={() => setSlideOverOpen(false)}
          onTestCreated={invalidateTests}
        />
      )}

      {editingTest && (
        <EditTestSlideOver
          test={editingTest}
          loading={updateTestMutation.isPending}
          error={updateTestMutation.error?.message ?? ''}
          onClose={() => setEditingTest(null)}
          onSubmit={(payload) =>
            updateTestMutation.mutate(
              { id: editingTest.id, ...payload },
              { onSuccess: () => setEditingTest(null) },
            )
          }
        />
      )}

      {!!specEditing && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60]"
          onClick={() => setSpecEditing(null)}
        />
      )}
      <SpecEditor
        test={specEditing ? { id: specEditing.id, name: specEditing.specFile?.basename ?? specEditing.name } : null}
        isOpen={!!specEditing}
        onClose={() => setSpecEditing(null)}
        overrideFilename={specEditing?.specFile?.filename}
        onRunStarted={() => invalidateTests()}
      />

      {runAllOpen && (
        <RunAllModal collectionIds={[id!]} onClose={() => setRunAllOpen(false)} />
      )}

      {planModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6"
          onClick={() => setPlanModal(null)}
        >
          <div
            className="bg-surface-main rounded-2xl border border-border-subtle w-full max-w-3xl max-h-[80vh] flex flex-col shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle shrink-0">
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-text-secondary" />
                <h2 className="text-sm font-semibold text-text-primary">plan.md</h2>
                <span className="text-xs text-text-secondary truncate max-w-xs">{planModal.testName}</span>
              </div>
              <button
                onClick={() => setPlanModal(null)}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4">
              <pre className="text-sm text-text-primary font-mono leading-relaxed whitespace-pre-wrap">
                {planModal.content}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
