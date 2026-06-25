import { useState, useEffect } from 'react';
import { useEnvironments } from '../hooks/useEnvironments';
import { useRunAll } from '../hooks/useRunActions';
import { X } from 'lucide-react';

export default function RunAllModal({ collectionIds, onClose }: { collectionIds: string[]; onClose: () => void }) {
  const { environments: allEnvironments } = useEnvironments();
  const environments = allEnvironments.filter((e) => e.isActive);
  const [envId, setEnvId] = useState(environments[0]?.id ?? '');

  useEffect(() => {
    if (environments.length > 0 && !envId) setEnvId(environments[0].id);
  }, [environments, envId]);

  const runMutation = useRunAll(collectionIds);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">{collectionIds.length > 1 ? `Run ${collectionIds.length} Collections` : 'Run All Specs'}</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors">
            <X size={20} />
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
            <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">{runMutation.error.message}</p>
          )}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
              Cancel
            </button>
            <button
              onClick={() => envId && runMutation.mutate(envId, { onSuccess: onClose })}
              disabled={!envId || runMutation.isPending}
              className="flex-1 bg-success text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-success/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-1.5"
            >
              {runMutation.isPending
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Running…</>
                : 'Run All'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
