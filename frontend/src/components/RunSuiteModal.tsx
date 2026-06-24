import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { collectionsService } from '../services/collections';
import { executionsService } from '../services/executions';
import { useCollections } from '../hooks/useCollections';
import { useCollectionTests } from '../hooks/useCollectionTests';
import { useEnvironments } from '../hooks/useEnvironments';

export default function RunSuiteModal({ onClose, onRun }: { onClose: () => void; onRun: () => void }) {
  const [collectionId, setCollectionId] = useState('');
  const [testId, setTestId] = useState('');
  const [envId, setEnvId] = useState('');
  const [error, setError] = useState('');

  const { collections, isLoading: collectionsLoading } = useCollections();
  const { tests } = useCollectionTests(collectionId || null);
  const { environments: allEnvironments, isLoading: envsLoading } = useEnvironments();

  const environments = allEnvironments.filter((e) => e.isActive);
  const effectiveEnvId = envId || environments[0]?.id || '';

  const runMut = useMutation({
    mutationFn: () => testId
      ? executionsService.retry({ testId, environmentId: effectiveEnvId })
      : collectionsService.runAllSpecs(collectionId, effectiveEnvId),
    onSuccess: () => { onClose(); onRun(); },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-md overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-primary" style={{ fontSize: 18, fontVariationSettings: '"FILL" 1' }}>play_circle</span>
            </div>
            <div>
              <h2 className="font-semibold text-text-primary text-sm">Run a Suite</h2>
              <p className="text-xs text-text-secondary mt-0.5">Pick a collection or specific test to run</p>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!collectionId) { setError('Select a collection to run.'); return; }
            if (!effectiveEnvId) { setError('No active environment available.'); return; }
            setError('');
            runMut.mutate();
          }}
          className="px-6 py-5 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Collection <span className="text-error">*</span></label>
            {collectionsLoading ? (
              <div className="h-10 bg-surface-muted rounded-xl animate-pulse" />
            ) : (
              <select
                value={collectionId}
                onChange={(e) => { setCollectionId(e.target.value); setTestId(''); }}
                className="w-full border border-border-subtle rounded-xl px-3 py-2.5 text-sm text-text-primary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="">— Select collection —</option>
                {collections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Test
              <span className="ml-1.5 text-xs font-normal text-text-secondary">(optional — leave blank to run entire collection)</span>
            </label>
            <select
              value={testId}
              onChange={(e) => setTestId(e.target.value)}
              disabled={!collectionId}
              className="w-full border border-border-subtle rounded-xl px-3 py-2.5 text-sm text-text-primary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
            >
              <option value="">— Run entire collection —</option>
              {tests.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Environment <span className="text-error">*</span></label>
            {envsLoading ? (
              <div className="h-10 bg-surface-muted rounded-xl animate-pulse" />
            ) : environments.length === 0 ? (
              <p className="text-sm text-warning flex items-center gap-1.5">
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>warning</span>
                No active environments. <a href="/environments" className="underline" onClick={onClose}>Create one.</a>
              </p>
            ) : (
              <select
                value={effectiveEnvId}
                onChange={(e) => setEnvId(e.target.value)}
                className="w-full border border-border-subtle rounded-xl px-3 py-2.5 text-sm text-text-primary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {environments.map((env) => <option key={env.id} value={env.id}>{env.name} — {env.baseUrl}</option>)}
              </select>
            )}
          </div>
          {error && <p className="text-sm text-error bg-error/5 border border-error/20 rounded-xl px-3 py-2">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={runMut.isPending || !collectionId || !effectiveEnvId}
              className="flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {runMut.isPending
                ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                : <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1' }}>play_arrow</span>}
              {runMut.isPending ? 'Starting…' : 'Run'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
