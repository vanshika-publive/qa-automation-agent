import { api } from '../api/client';
import { ApiResponse, Execution, ExecutionDetail, ExecutionFiles, TestResult } from '../types';

interface Pagination { page: number; pageSize: number; total: number; totalPages: number; }
export interface PaginatedExecs { data: Execution[]; pagination: Pagination; error: string | null; }

export interface ExecFilters {
  collectionId?: string;
  status?: string;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
  testId?: string;
}

export const executionsService = {
  getAll: (filters: ExecFilters = {}) => {
    const qs = new URLSearchParams();
    if (filters.collectionId) qs.set('collection_id', filters.collectionId);
    if (filters.status)       qs.set('status', filters.status);
    if (filters.from)         qs.set('from', filters.from);
    if (filters.to)           qs.set('to', filters.to);
    if (filters.testId)       qs.set('testId', filters.testId);
    if (filters.page)         qs.set('page', String(filters.page));
    if (filters.pageSize)     qs.set('pageSize', String(filters.pageSize));
    return api.get<PaginatedExecs>(`/executions?${qs}`);
  },

  getDetail: (id: string) =>
    api.get<ApiResponse<ExecutionDetail>>(`/executions/${id}`),

  getTestResults: (id: string) =>
    api.get<{ data: TestResult[]; pending: boolean; error: string | null }>(`/executions/${id}/tests`),

  getSteps: (id: string) =>
    api.get<{ data: { id: string; test_name: string; status: 'passed' | 'failed' | 'skipped'; duration_ms: number; error_message: string | null }[]; error: string | null }>(`/executions/${id}/steps`),

  getFiles: (id: string) =>
    api.get<ApiResponse<ExecutionFiles>>(`/executions/${id}/files`),

  delete: (id: string) =>
    api.del<ApiResponse<{ id: string }>>(`/executions/${id}`),

  retry: (exec: Pick<Execution, 'testId' | 'environmentId'>) =>
    api.post<ApiResponse<{ executionId: string }>>(
      `/executions/tests/${exec.testId}/run`,
      { environmentId: exec.environmentId },
    ),
};
