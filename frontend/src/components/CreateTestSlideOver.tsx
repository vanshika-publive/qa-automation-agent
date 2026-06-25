import { useState, useEffect, useRef } from 'react';
import { Check, X, ChevronDown, AlertTriangle, XCircle, CheckCircle2, ArrowRight, ArrowLeft, ExternalLink, FlaskConical, Lightbulb } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiResponse, Collection, Environment, StepName, StepStatus } from '../types';
import { EDITOR_BG, sseStreamUrl } from '../constants';

interface StepState {
  name: StepName;
  label: string;
  description: string;
  status: StepStatus;
  log: string;
}

interface Props {
  collections: Collection[];
  defaultCollectionId?: string;
  onClose: () => void;
  onTestCreated: () => void;
}

// Constants

const INITIAL_STEPS: StepState[] = [
  { name: 'orchestrator', label: 'Orchestrator',    description: 'Parsing intent & building test plan',   status: 'pending', log: '' },
  { name: 'planner',      label: 'Planner Agent',   description: 'Exploring UI & mapping locators',       status: 'pending', log: '' },
  { name: 'generator',    label: 'Generator Agent', description: 'Writing Playwright test code',          status: 'pending', log: '' },
  { name: 'runner',       label: 'Test Runner',     description: 'Executing tests & collecting results',  status: 'pending', log: '' },
];

// Sub-components 

function StepCircle({ status }: { status: StepStatus }) {
  if (status === 'passed') {
    return (
      <div className="w-8 h-8 rounded-full bg-success flex items-center justify-center flex-shrink-0 ring-4 ring-success/10">
        <Check size={16} className="text-white" />
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="w-8 h-8 rounded-full bg-error flex items-center justify-center flex-shrink-0 ring-4 ring-error/10">
        <X size={16} className="text-white" />
      </div>
    );
  }
  if (status === 'running') {
    return (
      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 ring-4 ring-primary/10">
        <div className="w-3 h-3 rounded-full bg-primary animate-pulse" />
      </div>
    );
  }
  // pending
  return (
    <div className="w-8 h-8 rounded-full border-2 border-border-subtle bg-surface-muted flex items-center justify-center flex-shrink-0">
      <div className="w-2 h-2 rounded-full bg-border-subtle" />
    </div>
  );
}

function StepRow({
  step,
  isLast,
  expanded,
  onToggle,
}: {
  step: StepState;
  isLast: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const labelColor =
    step.status === 'passed' ? 'text-success' :
    step.status === 'failed' ? 'text-error' :
    step.status === 'running' ? 'text-primary' :
    'text-text-secondary';

  const statusText =
    step.status === 'passed' ? 'Completed' :
    step.status === 'failed' ? 'Failed' :
    step.status === 'running' ? 'Running…' :
    'Waiting';

  return (
    <div className="flex gap-3">
      {/* Left: circle + connector line */}
      <div className="flex flex-col items-center">
        <StepCircle status={step.status} />
        {!isLast && (
          <div className={`w-0.5 flex-1 mt-1 min-h-[28px] transition-colors duration-500 ${
            step.status === 'passed' ? 'bg-success/30' :
            step.status === 'running' ? 'bg-primary/20' :
            'bg-border-subtle'
          }`} />
        )}
      </div>

      {/* Right: content */}
      <div className={`flex-1 pb-5 ${isLast ? '' : ''}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-text-primary">{step.label}</span>
              {step.status === 'running' && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary uppercase tracking-wide">
                  Live
                </span>
              )}
            </div>
            <p className="text-xs text-text-secondary mt-0.5">{step.description}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`text-xs font-medium ${labelColor}`}>{statusText}</span>
            {step.log && (
              <button
                onClick={onToggle}
                className="w-6 h-6 flex items-center justify-center rounded text-text-secondary hover:bg-surface-muted transition-colors"
                title={expanded ? 'Hide log' : 'Show log'}
              >
                <ChevronDown
                  size={14}
                  className="transition-transform duration-200"
                  style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
                />
              </button>
            )}
          </div>
        </div>

        {/* Log output */}
        {expanded && step.log && (
          <div className="mt-2 rounded-lg p-3 overflow-x-auto" style={{ backgroundColor: EDITOR_BG }}>
            <pre className="text-[11px] text-[#94A3B8] font-mono-code whitespace-pre-wrap break-words leading-relaxed max-h-40 overflow-y-auto">
              {step.log}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

// Main Component 

export default function CreateTestSlideOver({
  collections,
  defaultCollectionId,
  onClose,
  onTestCreated,
}: Props) {
  const navigate = useNavigate();

  // Form state
  const [name, setName] = useState('');
  const [collectionId, setCollectionId] = useState(defaultCollectionId ?? collections[0]?.id ?? '');
  const [prompt, setPrompt] = useState('');
  const [formError, setFormError] = useState('');

  // Pipeline state
  const [phase, setPhase] = useState<'form' | 'running' | 'done'>('form');
  const [steps, setSteps] = useState<StepState[]>(INITIAL_STEPS);
  const [expandedStep, setExpandedStep] = useState<StepName | null>(null);
  const [pipelineFailed, setPipelineFailed] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  // Environments (for the run call)
  const { data: envData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.get<ApiResponse<Environment[]>>('/environments'),
  });
  const activeEnvs = (envData?.data ?? []).filter((e) => e.isActive);
  const [environmentId, setEnvironmentId] = useState('');

  // Slide-in animation on mount
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    return () => {
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, []);

  // Sync collectionId if defaultCollectionId changes
  useEffect(() => {
    if (defaultCollectionId) setCollectionId(defaultCollectionId);
  }, [defaultCollectionId]);

  // Auto-select first active environment when data loads
  useEffect(() => {
    if (activeEnvs.length && !environmentId) setEnvironmentId(activeEnvs[0].id);
  }, [activeEnvs.length]);

  function handleClose() {
    setVisible(false);
    setTimeout(onClose, 300);
  }

  function applyStepUpdate(stepName: StepName, status: StepStatus, log?: string) {
    setSteps((prev) =>
      prev.map((s) =>
        s.name === stepName
          ? { ...s, status, log: log ?? s.log }
          : s
      )
    );
  }

  async function handleGenerate() {
    if (!name.trim()) { setFormError('Test name is required.'); return; }
    if (!prompt.trim()) { setFormError('Test intent is required.'); return; }
    if (!collectionId) { setFormError('Select a collection.'); return; }
    if (!environmentId) { setFormError('Select an environment to run against.'); return; }
    setFormError('');

    try {
      // 1. Create the test
      const testRes = await api.post<ApiResponse<{ id: string }>>(
        `/collections/${collectionId}/tests`,
        { name: name.trim(), prompt: prompt.trim() }
      );
      if (!testRes.data?.id) throw new Error('Failed to create test');
      const testId = testRes.data.id;
      onTestCreated(); // refresh sidebar/table

      // 2. Start the execution
      const runRes = await api.post<ApiResponse<{ executionId: string }>>(
        `/executions/tests/${testId}/run`,
        { environmentId }
      );
      if (!runRes.data?.executionId) throw new Error('Failed to start execution');
      const executionId = runRes.data.executionId;

      // 3. Switch to pipeline view
      setPhase('running');

      // 4. Open SSE stream
      const es = new EventSource(sseStreamUrl(executionId));
      sseRef.current = es;

      es.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data) as {
            execution: { status: string } | null;
            steps: { stepName: StepName; status: StepStatus; log: string }[];
          };

          // Update each step from the stream snapshot
          payload.steps.forEach((s) => {
            applyStepUpdate(s.stepName, s.status, s.log);
          });

          // If execution is done
          if (!payload.execution || payload.execution.status !== 'running') {
            if (payload.execution?.status === 'failed') setPipelineFailed(true);
            es.close();
            sseRef.current = null;
            setPhase('done');
          }
        } catch { /* ignore parse errors */ }
      };

      es.onerror = () => {
        es.close();
        sseRef.current = null;
        setPhase('done');
      };
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  const overallStatus = steps.every((s) => s.status === 'passed')
    ? 'passed'
    : steps.some((s) => s.status === 'failed')
    ? 'failed'
    : 'running';

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/30 z-40 transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`}
        onClick={phase === 'done' || phase === 'form' ? handleClose : undefined}
      />

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[680px] bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${
          visible ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-border-subtle flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
              <FlaskConical size={20} className="text-primary" />
            </div>
            <div>
              <h2 className="font-semibold text-text-primary text-headline-sm">Create New Test</h2>
              <p className="text-xs text-text-secondary mt-0.5">
                {phase === 'form' ? 'Describe your test and let the AI do the rest' :
                 phase === 'running' ? 'Pipeline running…' :
                 pipelineFailed ? 'Pipeline completed with errors' :
                 'Pipeline complete'}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            disabled={phase === 'running'}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

          {/* Form fields (always visible) */}
          <div className={`space-y-5 transition-opacity duration-300 ${phase !== 'form' ? 'opacity-40 pointer-events-none' : ''}`}>
            {/* Test Name */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Test Name <span className="text-error">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Create article and verify it appears in drafts"
                disabled={phase !== 'form'}
                className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors disabled:bg-surface-muted"
              />
            </div>

            {/* Collection */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Collection <span className="text-error">*</span>
              </label>
              {collections.length === 0 ? (
                <p className="text-sm text-text-secondary p-3 bg-warning/5 border border-warning/20 rounded-xl">
                  No collections found. Create a collection first.
                </p>
              ) : (
                <select
                  value={collectionId}
                  onChange={(e) => setCollectionId(e.target.value)}
                  disabled={phase !== 'form'}
                  className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors disabled:bg-surface-muted appearance-none cursor-pointer"
                >
                  {collections.map((col) => (
                    <option key={col.id} value={col.id}>{col.name}</option>
                  ))}
                </select>
              )}
            </div>

            {/* Test Intent */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Test Intent <span className="text-error">*</span>
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe what the test should do..."
                rows={5}
                disabled={phase !== 'form'}
                className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm font-mono-code text-text-primary placeholder:text-text-secondary placeholder:font-sans bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors resize-none disabled:bg-surface-muted leading-relaxed"
              />
              <p className="text-xs text-text-secondary mt-1.5">
                Plain English is fine — the AI will interpret intent and generate Playwright test steps.
              </p>
            </div>

            {/* Pro tip */}
            <div className="flex gap-3 bg-surface-container-low rounded-xl p-4 border border-surface-container">
              <Lightbulb size={18} className="text-primary flex-shrink-0 mt-0.5" />
              <div className="text-xs text-text-secondary leading-relaxed">
                <span className="font-semibold text-text-primary">Pro tip: </span>
                Be specific about what to click, fill in, and verify. For example: "Navigate to posts,
                click New Article, fill the title with a unique name, save as draft, then verify the
                article appears in the drafts list."
              </div>
            </div>

            {/* Environment selector */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Environment <span className="text-error">*</span>
              </label>
              {activeEnvs.length === 0 ? (
                <div className="flex items-center gap-2 text-xs text-warning p-3 bg-warning/5 border border-warning/20 rounded-xl">
                  <AlertTriangle size={14} />
                  No active environments. Go to{' '}
                  <a href="/environments" className="underline font-medium">Environments</a>{' '}
                  to create one.
                </div>
              ) : (
                <div className="relative">
                  <select
                    value={environmentId}
                    onChange={(e) => setEnvironmentId(e.target.value)}
                    disabled={phase !== 'form'}
                    className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors disabled:bg-surface-muted appearance-none cursor-pointer"
                  >
                    {activeEnvs.map((env) => (
                      <option key={env.id} value={env.id}>{env.name} — {env.baseUrl}</option>
                    ))}
                  </select>
                  <ChevronDown size={20} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-text-secondary" />
                </div>
              )}
            </div>

            {/* Form error */}
            {formError && phase === 'form' && (
              <p className="text-sm text-error bg-error/5 border border-error/20 rounded-xl px-4 py-3">
                {formError}
              </p>
            )}

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={phase !== 'form' || !environmentId}
              className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary/90 text-white rounded-xl py-3.5 text-sm font-semibold transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
            >
              Generate &amp; Run Tests
            </button>
          </div>

          {/* Pipeline Status */}
          {phase !== 'form' && (
            <div
              className="space-y-4"
              style={{ animation: 'slideDown 0.4s ease-out both' }}
            >
              <style>{`
                @keyframes slideDown {
                  from { opacity: 0; transform: translateY(-8px); }
                  to   { opacity: 1; transform: translateY(0); }
                }
              `}</style>

              {/* Section header */}
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-border-subtle" />
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    phase === 'running' ? 'bg-primary animate-pulse' :
                    overallStatus === 'passed' ? 'bg-success' : 'bg-error'
                  }`} />
                  <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                    Pipeline Status
                  </span>
                </div>
                <div className="h-px flex-1 bg-border-subtle" />
              </div>

              {/* Step summary bar */}
              <div className="flex gap-1 h-1.5 rounded-full overflow-hidden bg-surface-muted">
                {steps.map((s) => (
                  <div
                    key={s.name}
                    className={`flex-1 transition-colors duration-500 ${
                      s.status === 'passed' ? 'bg-success' :
                      s.status === 'failed' ? 'bg-error' :
                      s.status === 'running' ? 'bg-primary animate-pulse' :
                      'bg-transparent'
                    }`}
                  />
                ))}
              </div>

              {/* Steps timeline */}
              <div className="pt-2">
                {steps.map((step, i) => (
                  <StepRow
                    key={step.name}
                    step={step}
                    isLast={i === steps.length - 1}
                    expanded={expandedStep === step.name}
                    onToggle={() => setExpandedStep(expandedStep === step.name ? null : step.name)}
                  />
                ))}
              </div>

              {/* Completion message */}
              {phase === 'done' && (
                <div
                  className={`rounded-xl px-4 py-4 border ${
                    pipelineFailed
                      ? 'bg-error/5 border-error/20'
                      : 'bg-success/5 border-success/20'
                  }`}
                  style={{ animation: 'slideDown 0.3s ease-out both' }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {pipelineFailed
                      ? <XCircle size={18} className="text-error" />
                      : <CheckCircle2 size={18} className="text-success" />
                    }
                    <span className={`text-sm font-semibold ${pipelineFailed ? 'text-error' : 'text-success'}`}>
                      {pipelineFailed ? 'Pipeline failed' : 'All tests generated and run!'}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary ml-6">
                    {pipelineFailed
                      ? 'One or more pipeline stages failed. Check the logs above for details.'
                      : 'Your tests have been created and executed. View the full report in Executions.'}
                  </p>
                  <button
                    onClick={() => navigate('/executions')}
                    className={`mt-3 ml-6 inline-flex items-center gap-1.5 text-xs font-semibold underline underline-offset-2 ${
                      pipelineFailed ? 'text-error' : 'text-success'
                    }`}
                  >
                    View Results
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border-subtle flex-shrink-0 bg-surface-muted/50">
          <button
            onClick={handleClose}
            disabled={phase === 'running'}
            className="inline-flex items-center gap-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ArrowLeft size={18} />
            {phase === 'done' ? 'Close' : 'Back'}
          </button>

          {phase === 'running' && (
            <div className="flex items-center gap-2 text-xs text-text-secondary">
              <div className="w-3.5 h-3.5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              Running pipeline — please wait
            </div>
          )}

          {phase === 'done' && (
            <button
              onClick={() => navigate('/executions')}
              className="inline-flex items-center gap-2 bg-primary text-white rounded-xl px-4 py-2 text-sm font-semibold hover:bg-primary/90 transition-colors"
            >
              View Results
              <ExternalLink size={16} />
            </button>
          )}
        </div>
      </div>
    </>
  );
}
