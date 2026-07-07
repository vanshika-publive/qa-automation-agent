import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Check, X, ChevronDown, AlertTriangle, XCircle, CheckCircle2, ArrowRight, ArrowLeft, ExternalLink, FlaskConical, Lightbulb } from 'lucide-react';
import { Collection, StepName, StepStatus } from '../types';
import { collectionsService } from '../services/collections';
import { executionsService } from '../services/executions';
import { useActiveEnvironments } from '../hooks/useActiveEnvironments';
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

const INITIAL_STEPS: StepState[] = [
  { name: 'orchestrator', label: 'Orchestrator',    description: 'Parsing intent & building test plan',   status: 'pending', log: '' },
  { name: 'planner',      label: 'Planner Agent',   description: 'Exploring UI & mapping locators',       status: 'pending', log: '' },
  { name: 'generator',    label: 'Generator Agent', description: 'Writing Playwright test code',          status: 'pending', log: '' },
  { name: 'runner',       label: 'Test Runner',     description: 'Executing tests & collecting results',  status: 'pending', log: '' },
];

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

export default function CreateTestSlideOver({
  collections,
  defaultCollectionId,
  onClose,
  onTestCreated,
}: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [name, setName] = useState('');
  const [collectionId, setCollectionId] = useState(defaultCollectionId ?? collections[0]?.id ?? '');
  const [prompt, setPrompt] = useState('');
  const [formError, setFormError] = useState('');

  const [phase, setPhase] = useState<'form' | 'running' | 'done'>('form');
  const [steps, setSteps] = useState<StepState[]>(INITIAL_STEPS);
  const [expandedStep, setExpandedStep] = useState<StepName | null>(null);
  const [pipelineFailed, setPipelineFailed] = useState(false);
  const sseRef = useRef<EventSource | null>(null);
  const unmountedRef = useRef(false);

  const { environments: activeEnvs } = useActiveEnvironments();
  const [environmentId, setEnvironmentId] = useState('');

  const [visible, setVisible] = useState(false);
  useEffect(() => {
    unmountedRef.current = false;
    requestAnimationFrame(() => setVisible(true));
    return () => {
      unmountedRef.current = true;
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, []);

  useEffect(() => {
    if (defaultCollectionId) setCollectionId(defaultCollectionId);
  }, [defaultCollectionId]);

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

  async function reconcileStepsFromServer(executionId: string) {
    try {
      const detail = await executionsService.getDetail(executionId);
      detail.data?.steps.forEach((s) => applyStepUpdate(s.stepName, s.status, s.log));
      return detail.data?.status;
    } catch {
      return undefined;
    }
  }

  async function pollUntilFinished(executionId: string) {
    const POLL_MS = 2000;
    while (!unmountedRef.current) {
      const status = await reconcileStepsFromServer(executionId);
      if (status && status !== 'running') {
        if (status === 'failed') setPipelineFailed(true);
        qc.invalidateQueries({ queryKey: ['specs', collectionId] });
        setPhase('done');
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
  }

  async function handleGenerate() {
    if (!name.trim()) { setFormError('Test name is required.'); return; }
    if (!prompt.trim()) { setFormError('Test intent is required.'); return; }
    if (!collectionId) { setFormError('Select a collection.'); return; }
    if (!environmentId) { setFormError('Select an environment to run against.'); return; }
    setFormError('');

    try {
      const testRes = await collectionsService.createTest(collectionId, { name: name.trim(), prompt: prompt.trim() });
      if (!testRes.data?.id) throw new Error('Failed to create test');
      const testId = testRes.data.id;
      onTestCreated();

      const runRes = await executionsService.retry({ testId, environmentId });
      if (!runRes.data?.executionId) throw new Error('Failed to start execution');
      const executionId = runRes.data.executionId;

      setPhase('running');

      const es = new EventSource(sseStreamUrl(executionId));
      sseRef.current = es;

      es.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data) as {
            execution: { status: string } | null;
            steps: { stepName: StepName; status: StepStatus; log: string }[];
          };

          payload.steps.forEach((s) => {
            applyStepUpdate(s.stepName, s.status, s.log);
          });

          if (payload.execution && payload.execution.status !== 'running') {
            if (payload.execution.status === 'failed') setPipelineFailed(true);
            es.close();
            sseRef.current = null;
            reconcileStepsFromServer(executionId).then(() => {
              qc.invalidateQueries({ queryKey: ['specs', collectionId] });
              setPhase('done');
            });
          }
        } catch { /* ignore parse errors */ }
      };

      es.onerror = () => {
        es.close();
        sseRef.current = null;
        // The connection may have dropped mid-run (proxy/network hiccup) — keep
        // polling the execution detail until it actually finishes rather than
        // declaring the pipeline done prematurely.
        pollUntilFinished(executionId);
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
      <div
        className={`fixed inset-0 bg-black/30 z-40 transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`}
        onClick={phase === 'done' || phase === 'form' ? handleClose : undefined}
      />

      <div
        className={`fixed top-0 right-0 h-full bg-white shadow-2xl z-50 flex flex-col transition-[transform,width] duration-300 ease-out ${
          visible ? 'translate-x-0' : 'translate-x-full'
        } ${phase !== 'form' ? 'w-[900px]' : 'w-[680px]'}`}
      >
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

        {phase === 'form' ? (
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1.5">
                  Test Name <span className="text-error">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Create article and verify it appears in drafts"
                  className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors"
                />
              </div>

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
                    className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors appearance-none cursor-pointer"
                  >
                    {collections.map((col) => (
                      <option key={col.id} value={col.id}>{col.name}</option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-1.5">
                  Test Intent <span className="text-error">*</span>
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe what the test should do..."
                  rows={5}
                  className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm font-mono-code text-text-primary placeholder:text-text-secondary placeholder:font-sans bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors resize-none leading-relaxed"
                />
                <p className="text-xs text-text-secondary mt-1.5">
                  Plain English is fine — the AI will interpret intent and generate Playwright test steps.
                </p>
              </div>

              <div className="flex gap-3 bg-surface-container-low rounded-xl p-4 border border-surface-container">
                <Lightbulb size={18} className="text-primary flex-shrink-0 mt-0.5" />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <span className="font-semibold text-text-primary">Pro tip: </span>
                  Be specific about what to click, fill in, and verify. For example: "Navigate to posts,
                  click New Article, fill the title with a unique name, save as draft, then verify the
                  article appears in the drafts list."
                </div>
              </div>

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
                      className="w-full border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-colors appearance-none cursor-pointer"
                    >
                      {activeEnvs.map((env) => (
                        <option key={env.id} value={env.id}>{env.name} — {env.baseUrl}</option>
                      ))}
                    </select>
                    <ChevronDown size={20} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-text-secondary" />
                  </div>
                )}
              </div>

              {formError && (
                <p className="text-sm text-error bg-error/5 border border-error/20 rounded-xl px-4 py-3">
                  {formError}
                </p>
              )}

              <button
                onClick={handleGenerate}
                disabled={!environmentId}
                className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary/90 text-white rounded-xl py-3.5 text-sm font-semibold transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
              >
                Generate &amp; Run Tests
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex overflow-hidden">
            {/* Left column — read-only test configuration */}
            <div className="w-[380px] flex-shrink-0 overflow-y-auto px-6 py-6 border-r border-border-subtle space-y-5">
              <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Test Configuration</p>

              <div>
                <p className="text-xs text-text-secondary mb-1">Test Name</p>
                <p className="text-sm font-medium text-text-primary break-words">{name}</p>
              </div>

              <div>
                <p className="text-xs text-text-secondary mb-1">Collection</p>
                <p className="text-sm font-medium text-text-primary">
                  {collections.find((c) => c.id === collectionId)?.name ?? '—'}
                </p>
              </div>

              <div>
                <p className="text-xs text-text-secondary mb-1">Environment</p>
                <p className="text-sm font-medium text-text-primary">
                  {activeEnvs.find((e) => e.id === environmentId)?.name ?? '—'}
                </p>
              </div>

              <div>
                <p className="text-xs text-text-secondary mb-1">Test Intent</p>
                <div className="rounded-xl p-3" style={{ backgroundColor: EDITOR_BG }}>
                  <pre className="text-[11px] text-[#94A3B8] font-mono-code whitespace-pre-wrap break-words leading-relaxed max-h-64 overflow-y-auto">
                    {prompt}
                  </pre>
                </div>
              </div>
            </div>

            {/* Right column — pipeline status */}
            <div
              className="flex-1 overflow-y-auto px-6 py-6 space-y-4"
              style={{ animation: 'slideDown 0.4s ease-out both' }}
            >
              <style>{`
                @keyframes slideDown {
                  from { opacity: 0; transform: translateY(-8px); }
                  to   { opacity: 1; transform: translateY(0); }
                }
              `}</style>

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
                      : <CheckCircle2 size={18} className="text-success" />}
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
          </div>
        )}

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
