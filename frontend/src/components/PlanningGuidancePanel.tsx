import { useState } from 'react';
import { Compass, Pencil, Trash2, Check, X, Plus, Info } from 'lucide-react';
import { PLANNING_MEMORY_MAX } from '../types';
import { usePlanningMemory } from '../hooks/usePlanningMemory';

export default function PlanningGuidancePanel({ testId }: { testId: string }) {
  const { entries, createMutation, updateMutation, deleteMutation } = usePlanningMemory(testId);
  const [draft, setDraft] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [scopeHint, setScopeHint] = useState(false);

  const full = entries.length >= PLANNING_MEMORY_MAX;

  function handleAdd() {
    const content = draft.trim();
    if (!content || full) return;
    createMutation.mutate(content, {
      onSuccess: (res) => {
        setDraft('');
        setScopeHint(res.data?.advisory?.kind === 'scope');
      },
    });
  }

  function startEdit(id: string, content: string) {
    setEditingId(id);
    setEditValue(content);
  }

  function saveEdit(id: string) {
    const content = editValue.trim();
    if (!content) return;
    updateMutation.mutate({ id, content }, { onSuccess: () => setEditingId(null) });
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Compass size={15} className="text-text-secondary" />
        <label className="block text-sm font-semibold text-text-primary">Planning Guidance</label>
        <span className="text-[11px] text-text-secondary">{entries.length}/{PLANNING_MEMORY_MAX}</span>
      </div>
      <p className="text-xs text-text-secondary">
        Navigation corrections the planner must follow (how to reach the UI — not what to test).
      </p>

      {entries.map((e) => (
        <div key={e.id} className="border border-border-subtle rounded-xl px-3 py-2 bg-surface-muted/40">
          {editingId === e.id ? (
            <div className="space-y-2">
              <textarea
                value={editValue}
                onChange={(ev) => setEditValue(ev.target.value)}
                rows={2}
                className="w-full border border-border-subtle rounded-lg px-3 py-2 text-xs text-text-primary focus:ring-2 focus:ring-primary focus:border-primary outline-none resize-none"
              />
              <div className="flex justify-end gap-1">
                <button
                  onClick={() => setEditingId(null)}
                  className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted"
                  title="Cancel"
                >
                  <X size={15} />
                </button>
                <button
                  onClick={() => saveEdit(e.id)}
                  disabled={!editValue.trim() || updateMutation.isPending}
                  className="w-7 h-7 flex items-center justify-center rounded-lg text-primary hover:bg-primary/10 disabled:opacity-40"
                  title="Save"
                >
                  <Check size={15} />
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-2">
              <p className="flex-1 text-xs text-text-primary whitespace-pre-wrap">{e.content}</p>
              <button
                onClick={() => startEdit(e.id, e.content)}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:text-primary hover:bg-primary/10 flex-shrink-0"
                title="Edit"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => deleteMutation.mutate(e.id)}
                disabled={deleteMutation.isPending}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-text-secondary hover:text-error hover:bg-error/10 flex-shrink-0 disabled:opacity-40"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            </div>
          )}
        </div>
      ))}

      {scopeHint && (
        <div className="flex items-start gap-2 text-xs bg-warning/5 border border-warning/20 rounded-xl px-3 py-2">
          <Info size={14} className="text-warning flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="text-text-primary">
              This looks like it might change what's being tested. If so, edit the test description
              instead — it's kept as navigation guidance either way.
            </span>
            <button onClick={() => setScopeHint(false)} className="ml-2 text-text-secondary hover:text-text-primary underline">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {full ? (
        <p className="text-xs text-text-secondary bg-surface-muted rounded-xl px-3 py-2 border border-border-subtle">
          Planning memory is full ({PLANNING_MEMORY_MAX}). Edit or delete an entry to add another.
        </p>
      ) : (
        <div className="flex items-start gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            placeholder="e.g. Go to Posts → Create, don't click Assets"
            className="flex-1 border border-border-subtle rounded-xl px-3 py-2 text-xs text-text-primary placeholder:text-text-secondary focus:ring-2 focus:ring-primary focus:border-primary outline-none resize-none"
          />
          <button
            onClick={handleAdd}
            disabled={!draft.trim() || createMutation.isPending}
            className="flex items-center gap-1 px-3 py-2 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 flex-shrink-0"
          >
            <Plus size={14} />
            Add
          </button>
        </div>
      )}

      {(createMutation.isError || updateMutation.isError || deleteMutation.isError) && (
        <p className="text-xs text-error">
          {(createMutation.error as Error)?.message ||
            (updateMutation.error as Error)?.message ||
            (deleteMutation.error as Error)?.message}
        </p>
      )}
    </div>
  );
}
