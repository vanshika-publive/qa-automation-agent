import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiResponse, Environment } from '../types';
import { EDITOR_BG, EDITOR_BORDER, EDITOR_FONT_FAMILY, EDITOR_LINE_HEIGHT, sseStreamUrl } from '../constants';
import { Play, Save, CheckCircle2, XCircle, X, FileText } from 'lucide-react';

// Page-local types

interface SpecData {
  filename: string | null;
  content: string | null;
  lastModified: string | null;
}

interface RunnerStepState {
  status: 'running' | 'passed' | 'failed';
  log: string;
  passCount?: number;
  failCount?: number;
}

interface SpecResponse { data: SpecData; error: string | null }

export interface SpecEditorProps {
  test: { id: string; name: string } | null;
  isOpen: boolean;
  onClose: () => void;
  onRunStarted: (executionId: string) => void;
  /** When set, load this spec file directly by path instead of resolving via test id */
  overrideFilename?: string;
}

// Component

export default function SpecEditor({ test, isOpen, onClose, onRunStarted, overrideFilename }: SpecEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineNumRef  = useRef<HTMLDivElement>(null);
  const logRef      = useRef<HTMLDivElement>(null);

  const [content, setContent]               = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [filename, setFilename]             = useState<string | null>(null);
  const [specError, setSpecError]           = useState<string | null>(null);
  const [isLoadingSpec, setIsLoadingSpec]   = useState(false);

  const [isSaving, setIsSaving]             = useState(false);
  const [savedRecently, setSavedRecently]   = useState(false);

  const [selectedEnvId, setSelectedEnvId]   = useState('');
  const [isRunning, setIsRunning]           = useState(false);
  const [runPanelVisible, setRunPanelVisible] = useState(false);
  const [runnerStep, setRunnerStep]         = useState<RunnerStepState | null>(null);
  const [executionId, setExecutionId]       = useState<string | null>(null);

  const isModified = content !== originalContent;
  const lineCount = content.split('\n').length;

  // Environments query

  const { data: envsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.get<ApiResponse<Environment[]>>('/environments'),
    enabled: isOpen,
  });
  const environments = (envsData?.data ?? []).filter((e) => e.isActive);

  // Auto-select first env
  useEffect(() => {
    if (environments.length > 0 && !selectedEnvId) {
      setSelectedEnvId(environments[0].id);
    }
  }, [environments, selectedEnvId]);

  // Load spec when panel opens

  useEffect(() => {
    if (!isOpen || !test) return;

    setIsLoadingSpec(true);
    setContent('');
    setOriginalContent('');
    setFilename(null);
    setSpecError(null);
    setRunPanelVisible(false);
    setRunnerStep(null);
    setExecutionId(null);

    if (overrideFilename) {
      // Load spec file directly by relative path (used when opening from spec file table)
      api.get<{ data: { content: string }; error: string | null }>(
        `/specs/view?file=${encodeURIComponent(overrideFilename)}`,
      )
        .then((res) => {
          if (res.error || !res.data?.content) {
            setSpecError(res.error ?? 'Could not load spec file.');
          } else {
            setContent(res.data.content);
            setOriginalContent(res.data.content);
            setFilename(overrideFilename);
          }
        })
        .catch((e: Error) => setSpecError(e.message))
        .finally(() => setIsLoadingSpec(false));
    } else {
      api.get<SpecResponse>(`/tests/${test.id}/spec`)
        .then((res) => {
          if (res.error || !res.data.content) {
            setSpecError(res.error ?? 'No spec file generated yet for this test.');
          } else {
            setContent(res.data.content);
            setOriginalContent(res.data.content);
            setFilename(res.data.filename);
          }
        })
        .catch((e: Error) => setSpecError(e.message))
        .finally(() => setIsLoadingSpec(false));
    }
  }, [isOpen, test?.id, overrideFilename]); // eslint-disable-line react-hooks/exhaustive-deps

  // SSE stream for runner output

  useEffect(() => {
    if (!executionId) return;

    const es = new EventSource(sseStreamUrl(executionId));

    es.onmessage = (e: MessageEvent) => {
      try {
        const { execution, steps } = JSON.parse(e.data as string) as {
          execution: { status: string; passCount: number; failCount: number } | null;
          steps: Array<{ stepName: string; status: string; log: string }>;
        };
        const runner = steps?.find((s) => s.stepName === 'runner');
        if (runner) {
          setRunnerStep({
            status: runner.status as RunnerStepState['status'],
            log: runner.log,
            passCount: execution?.passCount,
            failCount: execution?.failCount,
          });
        }
        if (execution && execution.status !== 'running') {
          es.close();
          setIsRunning(false);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
      setIsRunning(false);
    };

    return () => es.close();
  }, [executionId]);

  // Auto-scroll log output
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [runnerStep?.log]);

  // Save handler

  const handleSave = useCallback(async () => {
    if (!filename || isSaving) return;
    setIsSaving(true);
    try {
      await api.put(`/tests/${test!.id}/spec`, { content, filename });
      setOriginalContent(content);
      setSavedRecently(true);
      setTimeout(() => setSavedRecently(false), 2000);
    } catch {
      // silent — user can retry
    } finally {
      setIsSaving(false);
    }
  }, [filename, content, isSaving, test]);

  // Run handler

  const handleRun = async () => {
    if (!filename || !selectedEnvId || isRunning) return;

    // Auto-save if modified
    if (isModified) await handleSave();

    setIsRunning(true);
    setRunPanelVisible(true);
    setRunnerStep({ status: 'running', log: '' });

    try {
      const res = await api.post<ApiResponse<{ executionId: string }>>(
        `/tests/${test!.id}/run-spec`,
        { environmentId: selectedEnvId, filename },
      );
      const execId = res.data?.executionId;
      if (execId) {
        setExecutionId(execId);
        onRunStarted(execId);
      }
    } catch (e: unknown) {
      setRunnerStep({ status: 'failed', log: (e as Error).message });
      setIsRunning(false);
    }
  };

  // Keyboard shortcuts

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, handleSave, onClose]);

  // Tab key in textarea

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Tab') {
      e.preventDefault();
      const el = e.currentTarget;
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const next = content.substring(0, start) + '  ' + content.substring(end);
      setContent(next);
      requestAnimationFrame(() => {
        el.selectionStart = start + 2;
        el.selectionEnd = start + 2;
      });
    }
  }

  // Scroll sync

  function syncScroll(e: React.UIEvent<HTMLTextAreaElement>) {
    if (lineNumRef.current) lineNumRef.current.scrollTop = e.currentTarget.scrollTop;
  }

  // Render

  const lines = content.split('\n');

  return (
    <div
      className={`fixed right-0 top-0 h-full w-[800px] z-[70] flex flex-col transition-transform duration-300 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
      style={{ backgroundColor: EDITOR_BG }}
    >
      {/* Header */}
      <div className="px-6 py-3.5 border-b border-white/10 flex items-center justify-between flex-shrink-0" style={{ backgroundColor: EDITOR_BORDER }}>
        <div className="min-w-0">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-0.5">
            SPEC FILE
          </p>
          {filename ? (
            <p className="text-white font-mono text-[13px] truncate max-w-[400px]">
              {filename}
            </p>
          ) : (
            <p className="text-slate-500 text-[13px]">
              {isLoadingSpec ? 'Loading…' : 'No spec generated yet'}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Environment selector */}
          <div className="flex items-center gap-2">
            <span className="text-slate-400 text-[12px]">Env:</span>
            <select
              value={selectedEnvId}
              onChange={(e) => setSelectedEnvId(e.target.value)}
              className="border border-white/10 text-white rounded-lg px-2.5 py-1.5 text-[12px] focus:outline-none focus:ring-1 focus:ring-primary/40 max-w-[140px]"
              style={{ backgroundColor: EDITOR_BG }}
            >
              {environments.map((env) => (
                <option key={env.id} value={env.id}>{env.name}</option>
              ))}
              {environments.length === 0 && (
                <option value="" disabled>No environments</option>
              )}
            </select>
          </div>

          {/* Run Spec button */}
          <button
            onClick={handleRun}
            disabled={!filename || !selectedEnvId || isRunning}
            className="inline-flex items-center gap-1.5 bg-primary text-white px-3.5 py-1.5 rounded-lg text-[13px] font-semibold hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? (
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Play size={15} />
            )}
            {isRunning ? 'Running…' : 'Run Spec'}
          </button>

          {/* Save button */}
          <button
            onClick={handleSave}
            disabled={!filename || isSaving || !isModified}
            className="inline-flex items-center gap-1.5 bg-white/10 hover:bg-white/20 text-white px-3.5 py-1.5 rounded-lg text-[13px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {savedRecently ? (
              <>
                <CheckCircle2 size={14} className="text-success" />
                Saved
              </>
            ) : (
              <>
                <Save size={14} />
                Save
              </>
            )}
          </button>

          {/* Close */}
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors ml-1"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Editor body */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">
        {isLoadingSpec ? (
          /* Loading skeleton */
          <div className="flex-1 p-6 space-y-2" style={{ backgroundColor: EDITOR_BG }}>
            {Array.from({ length: 18 }).map((_, i) => (
              <div
                key={i}
                className="h-[13px] bg-white/5 rounded animate-pulse"
                style={{ width: `${40 + Math.random() * 50}%` }}
              />
            ))}
          </div>
        ) : specError ? (
          /* No spec yet */
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-slate-400 p-8">
            <FileText size={56} className="text-slate-600" />
            <p className="text-white font-medium text-base">No spec file generated yet</p>
            <p className="text-slate-400 text-sm text-center max-w-xs leading-relaxed">
              Run the full pipeline first from the Collections page to generate a .spec.ts file for this test.
            </p>
          </div>
        ) : (
          /* Code editor */
          <div className="flex flex-1 overflow-hidden min-h-0">
            {/* Line numbers */}
            <div
              ref={lineNumRef}
              className="w-11 flex-shrink-0 overflow-hidden select-none border-r border-white/5 pt-6 pb-6"
              style={{ backgroundColor: '#0B1120', scrollbarWidth: 'none' }}
            >
              {lines.map((_, i) => (
                <div
                  key={i}
                  className="text-slate-600 text-right pr-2.5 font-mono text-[12px]"
                  style={{ lineHeight: '20.8px' }}
                >
                  {i + 1}
                </div>
              ))}
            </div>

            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              onScroll={syncScroll}
              spellCheck={false}
              className="flex-1 bg-transparent text-[#E2E8F0] font-mono text-[13px] px-4 py-6 resize-none outline-none border-none overflow-auto"
              style={{
                lineHeight: EDITOR_LINE_HEIGHT,
                tabSize: 2,
                fontFamily: EDITOR_FONT_FAMILY,
                caretColor: '#7C3AED',
              }}
            />
          </div>
        )}

        {/* Status bar */}
        {!isLoadingSpec && !specError && (
          <div className="h-6 border-t border-white/5 flex items-center px-4 gap-5 flex-shrink-0" style={{ backgroundColor: EDITOR_BORDER }}>
            <span className="text-[11px] text-slate-500">TypeScript</span>
            <span className="text-[11px] text-slate-500">{lineCount} lines</span>
            {isModified && !savedRecently && (
              <span className="flex items-center gap-1 text-[11px] text-warning">
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                Modified
              </span>
            )}
            {savedRecently && (
              <span className="flex items-center gap-1 text-[11px] text-success">
                <span className="w-1.5 h-1.5 rounded-full bg-success" />
                Saved
              </span>
            )}
            {filename && (
              <span className="text-[11px] text-slate-600 ml-auto truncate max-w-[300px]">{filename}</span>
            )}
          </div>
        )}
      </div>

      {/* Run panel (slides up from bottom) */}
      <div
        className={`border-t border-white/10 flex-shrink-0 overflow-hidden transition-all duration-300 ${
          runPanelVisible ? 'max-h-[200px]' : 'max-h-0'
        }`}
        style={{ backgroundColor: EDITOR_BORDER }}
      >
        <div className="p-4 h-full flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="text-white text-sm font-semibold">Runner Output</span>
            <button
              onClick={() => setRunPanelVisible(false)}
              className="text-slate-500 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Step status */}
          <div className="flex items-center gap-2 mb-2.5">
            <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${
              runnerStep?.status === 'passed' ? 'bg-success/20' :
              runnerStep?.status === 'failed' ? 'bg-error/20' :
              'bg-warning/20'
            }`}>
              {runnerStep?.status === 'running' ? (
                <div className="w-3 h-3 border-2 border-warning/40 border-t-warning rounded-full animate-spin" />
              ) : (
                runnerStep?.status === 'passed'
                  ? <CheckCircle2 size={14} className="text-success" />
                  : <XCircle size={14} className="text-error" />
              )}
            </div>
            <span className="text-slate-300 text-[13px] font-medium">Test Runner</span>

            {runnerStep && runnerStep.status !== 'running' && (
              <div className="ml-auto flex items-center gap-3">
                {(runnerStep.passCount ?? 0) > 0 && (
                  <span className="text-success text-[12px] font-semibold">
                    {runnerStep.passCount} passed
                  </span>
                )}
                {(runnerStep.failCount ?? 0) > 0 && (
                  <span className="text-error text-[12px] font-semibold">
                    {runnerStep.failCount} failed
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Log output */}
          <div
            ref={logRef}
            className="flex-1 rounded-lg p-3 overflow-y-auto font-mono text-[11px] leading-relaxed"
            style={{ backgroundColor: EDITOR_BG }}
          >
            {runnerStep?.log ? (
              <pre className="text-green-400 whitespace-pre-wrap break-words">{runnerStep.log.slice(-2000)}</pre>
            ) : (
              <span className="text-slate-600 italic">Waiting for output…</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
