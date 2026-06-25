import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiResponse, Environment } from '../types';
import { X, Play } from 'lucide-react';

interface RunTestModalProps {
  testId: string;
  testName: string;
  onClose: () => void;
}

export default function RunTestModal({ testId, testName, onClose }: RunTestModalProps) {
  const navigate = useNavigate();
  const [selectedEnvId, setSelectedEnvId] = useState('');
  const [headless, setHeadless] = useState(true);
  const [overrideUrl, setOverrideUrl] = useState('');
  const [error, setError] = useState('');

  const envQuery = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.get<ApiResponse<Environment[]>>('/environments'),
  });
  const environments = (envQuery.data?.data ?? []).filter((e) => e.isActive);

  // Auto-select first environment
  useEffect(() => {
    if (environments.length && !selectedEnvId) {
      setSelectedEnvId(environments[0].id);
    }
  }, [environments, selectedEnvId]);

  const runMutation = useMutation({
    mutationFn: () =>
      api.post<ApiResponse<{ executionId: string }>>(`/executions/tests/${testId}/run`, {
        environmentId: selectedEnvId,
      }),
    onSuccess: () => {
      onClose();
      navigate('/executions');
    },
    onError: (err: Error) => setError(err.message),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedEnvId) { setError('Select an environment to continue.'); return; }
    setError('');
    runMutation.mutate();
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
          <div>
            <h2 className="font-semibold text-text-primary">Run Test</h2>
            <p className="text-xs text-text-secondary mt-0.5 truncate max-w-[300px]">{testName}</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* Environment */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Environment <span className="text-error">*</span>
            </label>
            {envQuery.isLoading ? (
              <div className="h-10 bg-surface-muted rounded-lg animate-pulse" />
            ) : environments.length === 0 ? (
              <p className="text-sm text-text-secondary p-3 bg-warning/5 border border-warning/20 rounded-lg">
                No active environments.{' '}
                <a href="/environments" className="text-primary underline" onClick={onClose}>
                  Create one first.
                </a>
              </p>
            ) : (
              <select
                value={selectedEnvId}
                onChange={(e) => setSelectedEnvId(e.target.value)}
                className="w-full border border-border-subtle rounded-lg px-3 py-2.5 text-sm text-text-primary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
              >
                {environments.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name} — {env.baseUrl}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Override URL */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Override base URL
              <span className="ml-1.5 text-xs font-normal text-text-secondary">(optional)</span>
            </label>
            <input
              type="url"
              value={overrideUrl}
              onChange={(e) => setOverrideUrl(e.target.value)}
              placeholder="https://staging.example.com"
              className="w-full border border-border-subtle rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40"
            />
          </div>

          {/* Headless */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={headless}
              onChange={(e) => setHeadless(e.target.checked)}
              className="w-4 h-4 rounded border-border-subtle text-primary accent-primary"
            />
            <div>
              <div className="text-sm font-medium text-text-primary">Run headless</div>
              <div className="text-xs text-text-secondary">No browser window will open during the run</div>
            </div>
          </label>

          {/* Error */}
          {error && (
            <p className="text-sm text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={runMutation.isPending || !selectedEnvId}
              className="flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {runMutation.isPending ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Play size={18} />
              )}
              {runMutation.isPending ? 'Starting…' : 'Run now'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
