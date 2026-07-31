export interface ApiResponse<T> { data: T; error: string | null }

export interface Collection {
  id: string;
  name: string;
  testCount: number;
  createdAt: string;
}

export interface Test {
  id: string;
  collectionId: string;
  name: string;
  prompt: string;
  status: string;
  environmentIds: string[];
  createdAt: string;
  specFile: { basename: string; filename: string } | null;
  planFile: string | null;
}

export interface Environment {
  id: string;
  name: string;
  baseUrl: string;
  description: string;
  isActive: boolean;
  createdAt: string;
  loginEmail: string;
  publisher: string;
  hasPassword: boolean;
}

export interface SpecFile {
  filename: string;
  basename: string;
  lastModified: string;
  sizeBytes: number;
}

export interface Execution {
  id: string;
  testId: string;
  collectionId: string;
  collectionName: string;
  environmentId: string;
  status: 'running' | 'queued' | 'passed' | 'failed';
  startedAt: string;
  completedAt: string | null;
  durationMs: number | null;
  passCount: number;
  failCount: number;
  totalCount: number;
  runNumber: number;
  testName: string;
  environmentName: string;
  environmentUrl: string;
  reportDir: string | null;
}

export type StepName = 'orchestrator' | 'planner' | 'generator' | 'runner';
export type StepStatus = 'pending' | 'running' | 'passed' | 'failed';

export interface ExecStep {
  id: string;
  executionId: string;
  stepName: StepName;
  status: StepStatus;
  log: string;
  startedAt: string;
  completedAt: string | null;
}

export interface TestResult {
  title: string;
  file: string;
  status: 'passed' | 'failed' | 'skipped';
  durationMs: number;
  error: string | null;
}

export interface ExecutionDetail extends Execution {
  steps: ExecStep[];
  failureCategory?: string | null;
  failureReason?: string | null;
  failureLocator?: string | null;
}

export interface ExecutionFiles {
  specFilename: string | null;
  specContent: string | null;
  planContent: string | null;
  screenshots: string[];
}

export interface PlanningMemoryEntry {
  id: string;
  testId: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}

/** Non-blocking hint — does not block or reject the action. */
export interface CorrectionAdvisory {
  kind: 'navigation' | 'scope';
}

export const PLANNING_MEMORY_MAX = 4;
