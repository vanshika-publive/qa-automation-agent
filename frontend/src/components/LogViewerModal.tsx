import { useState, useEffect, useRef } from 'react';
import { StepName, StepStatus } from '../types';
import { EDITOR_BG, FONT_VARIATION_FILLED, sseStreamUrl } from '../constants';

interface StepState {
  name: StepName;
  label: string;
  description: string;
  status: StepStatus;
  log: string;
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
        <span className="material-symbols-outlined text-white" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1, "wght" 600' }}>check</span>
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="w-8 h-8 rounded-full bg-error flex items-center justify-center flex-shrink-0 ring-4 ring-error/10">
        <span className="material-symbols-outlined text-white" style={{ fontSize: 16, fontVariationSettings: FONT_VARIATION_FILLED }}>close</span>
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

function StepRow({ step, isLast, expanded, onToggle }: { step: StepState; isLast: boolean; expanded: boolean; onToggle: () => void }) {
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
      <div className={`flex-1 pb-5`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-text-primary">{step.label}</span>
              {step.status === 'running' && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary uppercase tracking-wide">Live</span>
              )}
            </div>
            <p className="text-xs text-text-secondary mt-0.5">{step.description}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`text-xs font-medium ${labelColor}`}>{statusText}</span>
            {step.log && (
              <button onClick={onToggle} className="w-6 h-6 flex items-center justify-center rounded text-text-secondary hover:bg-surface-muted transition-colors" title={expanded ? 'Hide log' : 'Show log'}>
                <span className="material-symbols-outlined transition-transform duration-200" style={{ fontSize: 14, transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>expand_more</span>
              </button>
            )}
          </div>
        </div>
        {expanded && step.log && (
          <div className="mt-2 rounded-lg p-3 overflow-x-auto" style={{ backgroundColor: EDITOR_BG }}>
            <pre className="text-[11px] text-[#94A3B8] font-mono-code whitespace-pre-wrap break-words leading-relaxed max-h-40 overflow-y-auto">{step.log}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  executionId: string;
  testName: string;
  onClose: () => void;
}

export default function LogViewerModal({ executionId, testName, onClose }: Props) {
  const [steps, setSteps] = useState<StepState[]>(INITIAL_STEPS);
  const [expandedStep, setExpandedStep] = useState<StepName | null>(null);
  const [done, setDone] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(sseStreamUrl(executionId));
    sseRef.current = es;

    es.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data) as {
          execution: { status: string } | null;
          steps: { stepName: StepName; status: StepStatus; log: string }[];
        };

        setSteps((prev) =>
          prev.map((s) => {
            const update = payload.steps.find((u) => u.stepName === s.name);
            return update ? { ...s, status: update.status, log: update.log || s.log } : s;
          })
        );

        if (!payload.execution || payload.execution.status !== 'running') {
          es.close();
          sseRef.current = null;
          setDone(true);
        }
      } catch { /* ignore parse errors */ }
    };

    es.onerror = () => {
      es.close();
      sseRef.current = null;
      setDone(true);
    };

    return () => {
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, [executionId]);

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-[560px] max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>terminal</span>
              </div>
              <div>
                <h2 className="font-semibold text-text-primary text-sm">Pipeline Log</h2>
                <p className="text-xs text-text-secondary mt-0.5">{testName}</p>
              </div>
            </div>
            <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-text-secondary hover:bg-surface-muted transition-colors">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            {steps.map((step, i) => (
              <StepRow
                key={step.name}
                step={step}
                isLast={i === steps.length - 1}
                expanded={expandedStep === step.name}
                onToggle={() => setExpandedStep((prev) => (prev === step.name ? null : step.name))}
              />
            ))}
          </div>

          {done && (
            <div className="px-6 py-4 border-t border-border-subtle flex-shrink-0">
              <button onClick={onClose} className="w-full py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors">
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
