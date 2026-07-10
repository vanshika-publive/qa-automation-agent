import { useState, useEffect } from 'react';
import { Test } from '../types';
import { useCollections } from '../hooks/useCollections';
import { useActiveEnvironments } from '../hooks/useActiveEnvironments';
import PlanningGuidancePanel from './PlanningGuidancePanel';
import { X, ChevronDown, CheckCircle, Plus } from 'lucide-react';

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="relative">
      <input type="checkbox" className="sr-only peer" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <div
        className="w-11 h-6 bg-border-subtle rounded-full peer peer-checked:bg-primary cursor-pointer
                   after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                   after:bg-white after:border after:border-gray-300 after:rounded-full
                   after:h-5 after:w-5 after:transition-all
                   peer-checked:after:translate-x-full peer-checked:after:border-white"
        onClick={() => onChange(!checked)}
      />
    </div>
  );
}

export default function EditTestSlideOver({
  test, loading, error, onClose, onSubmit,
}: {
  test: Test;
  loading: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (payload: {
    name: string; prompt: string; status: string;
    collectionId: string; environmentIds: string[]; duplicate: boolean;
  }) => void;
}) {
  const [name, setName]               = useState(test.name);
  const [prompt, setPrompt]           = useState(test.prompt);
  const [active, setActive]           = useState(test.status !== 'inactive');
  const [collectionId, setCollection] = useState(test.collectionId);
  const [envIds, setEnvIds]           = useState<string[]>(test.environmentIds ?? []);
  const [duplicate, setDuplicate]     = useState(false);

  const { collections }  = useCollections();
  const { environments: allEnvironments } = useActiveEnvironments();
  const allCollections   = collections;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  function toggleEnv(id: string) {
    setEnvIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  }

  function handleSave() {
    if (!name.trim()) return;
    onSubmit({ name: name.trim(), prompt, status: active ? 'active' : 'inactive', collectionId, environmentIds: envIds, duplicate });
  }

  return (
    <>
      <div className="fixed inset-0 bg-surface-sidebar/40 z-[60]" onClick={onClose} />
      <div
        className="fixed top-0 right-0 h-full w-[520px] bg-white z-[70] flex flex-col"
        style={{ boxShadow: '-10px 0 25px -5px rgba(0,0,0,0.15)' }}
      >
        <div className="px-6 py-4 border-b border-border-subtle flex justify-between items-center bg-white flex-shrink-0">
          <h3 className="font-semibold text-text-primary truncate">Edit Test: {test.name}</h3>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted hover:text-text-primary transition-all ml-3 flex-shrink-0"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          <div className="space-y-2">
            <label className="block text-sm font-semibold text-text-primary">Prompt</label>
            <textarea
              autoFocus
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Enter test instructions in plain English…"
              className="w-full border border-border-subtle rounded-xl px-4 py-3 font-mono-code text-xs text-text-primary placeholder:text-text-secondary focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all resize-none"
            />
            <p className="text-xs text-text-secondary">The AI uses this prompt to generate execution steps.</p>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-semibold text-text-primary">
              Test name <span className="text-error">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all"
            />
          </div>

          <div className="flex items-center justify-between p-4 bg-surface-muted rounded-xl border border-border-subtle">
            <div>
              <div className="text-sm font-semibold text-text-primary">Status</div>
              <div className="text-xs text-text-secondary mt-0.5">Active tests run in scheduled cycles</div>
            </div>
            <label className="flex items-center gap-3 cursor-pointer">
              <Toggle checked={active} onChange={setActive} />
              <span className="text-xs font-bold uppercase tracking-wide text-text-primary">
                {active ? 'Active' : 'Inactive'}
              </span>
            </label>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-semibold text-text-primary">Collection</label>
            <div className="relative">
              <select
                value={collectionId}
                onChange={(e) => setCollection(e.target.value)}
                className="w-full border border-border-subtle rounded-xl px-4 py-2.5 pr-10 text-sm text-text-primary bg-white focus:ring-2 focus:ring-primary focus:border-primary outline-none appearance-none cursor-pointer transition-all"
              >
                {allCollections.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <ChevronDown size={20} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-text-secondary" />
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-border-subtle">
            <div>
              <div className="text-sm font-semibold text-text-primary">Duplicate Test</div>
              <div className="text-xs text-text-secondary mt-0.5">Create a copy in the current collection</div>
            </div>
            <Toggle checked={duplicate} onChange={setDuplicate} />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-semibold text-text-primary">Environment</label>
            <div className="flex flex-wrap gap-2">
              {allEnvironments.map((env) => {
                const selected = envIds.includes(env.id);
                return (
                  <button
                    key={env.id}
                    type="button"
                    onClick={() => toggleEnv(env.id)}
                    className={[
                      'flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition-all',
                      selected
                        ? 'border-2 border-primary bg-primary/5 text-primary'
                        : 'border border-border-subtle text-text-secondary hover:border-primary/40 hover:text-primary',
                    ].join(' ')}
                  >
                    <CheckCircle
                      size={16}
                      style={{ color: selected ? '#3525cd' : undefined }}
                    />
                    {env.name}
                  </button>
                );
              })}
              <a
                href="/environments"
                onClick={onClose}
                className="flex items-center gap-1 px-4 py-1.5 rounded-full text-sm font-medium border border-dashed border-border-subtle text-text-secondary hover:border-primary hover:text-primary transition-all"
              >
                <Plus size={16} />
                Add
              </a>
            </div>
          </div>

          <div className="pt-2 border-t border-border-subtle">
            <PlanningGuidancePanel testId={test.id} />
          </div>

          {error && (
            <p className="text-sm text-error bg-error/5 border border-error/20 rounded-xl px-4 py-3">{error}</p>
          )}
        </div>

        <div className="p-6 border-t border-border-subtle bg-surface-muted/50 flex-shrink-0">
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-border-subtle bg-white text-text-primary text-sm font-medium rounded-lg py-2.5 hover:bg-surface-muted transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!name.trim() || loading}
              className="flex-1 bg-primary text-white text-sm font-semibold rounded-lg py-2.5 hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95 transition-all shadow-sm"
            >
              {loading ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
