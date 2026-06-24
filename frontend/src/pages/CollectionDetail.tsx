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
        <span className="material-symbols-outlined text-border-subtle" style={{ fontSize: 48 }}>folder_off</span>
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
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_back</span>
          </button>
          <div>
            <div className="flex items-center gap-2.5">
              <span
                className="material-symbols-outlined text-primary"
                style={{ fontSize: 20, fontVariationSettings: '"FILL" 1' }}
              >
                folder_open
              </span>
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
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_circle</span>
            Run Suite
          </button>
          <button
            onClick={() => setSlideOverOpen(true)}
            className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2.5 text-sm font-semibold hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0 active:scale-[0.98]"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span>
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
                  <span className="material-symbols-outlined text-border-subtle block mb-2" style={{ fontSize: 40 }}>folder_open</span>
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
                          <span
                            className={`material-symbols-outlined ${isTestOpen ? 'text-primary' : accent.icon}`}
                            style={{ fontSize: 17, fontVariationSettings: '"FILL" 1' }}
                          >
                            {test.specFile ? 'description' : 'draft'}
                          </span>
                        </div>
                        {test.specFile
                          ? <span className="font-mono-code text-xs text-text-secondary bg-surface-muted px-2 py-0.5 rounded break-all">{test.specFile.basename}</span>
                          : <span className="font-medium text-text-primary text-sm leading-snug line-clamp-2">{test.name}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      {test.planFile
                        ? <span className="font-mono-code text-xs text-text-secondary bg-surface-muted px-2 py-0.5 rounded">{test.planFile}</span>
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
                          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>play_arrow</span>
                        </button>
                        <button
                          onClick={() => setEditingTest(test)}
                          title="Edit test"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
                        >
                          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>edit</span>
                        </button>
                        {test.specFile && (
                          <button
                            onClick={() => setSpecEditing(test)}
                            title="Edit spec code"
                            className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:text-primary hover:bg-primary/5 transition-colors"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>code</span>
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteTest(test.id)}
                          title="Delete test"
                          className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error transition-colors"
                        >
                          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>delete</span>
                        </button>
                      </div>
                    </td>
                    <td className="pr-4 py-3.5">
                      <span
                        className={`material-symbols-outlined text-text-secondary transition-transform duration-200 ${isTestOpen ? 'rotate-180' : ''}`}
                        style={{ fontSize: 16 }}
                      >
                        expand_more
                      </span>
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
        <RunAllModal collectionId={id!} onClose={() => setRunAllOpen(false)} />
      )}
    </div>
  );
}
