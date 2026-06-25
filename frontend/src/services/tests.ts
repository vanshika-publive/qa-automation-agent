import { api } from '../api/client';
import { ApiResponse, Test } from '../types';

export interface TestUpdatePayload {
  name: string;
  prompt: string;
  status: string;
  collectionId: string;
  environmentIds: string[];
  duplicate: boolean;
}

export const testsService = {
  update: (id: string, payload: TestUpdatePayload) =>
    api.put<ApiResponse<Test>>(`/tests/${id}`, payload),

  delete: (id: string) =>
    api.del<ApiResponse<unknown>>(`/tests/${id}`),

  getSpec: (testId: string) =>
    api.get<ApiResponse<{ filename: string | null; content: string | null; lastModified: string | null }>>(
      `/tests/${testId}/spec`,
    ),

  viewSpecFile: (file: string) =>
    api.get<ApiResponse<{ content: string }>>(`/specs/view?file=${encodeURIComponent(file)}`),

  saveSpec: (testId: string, payload: { content: string; filename: string }) =>
    api.put<ApiResponse<{ ok: boolean }>>(`/tests/${testId}/spec`, payload),

  runSpec: (testId: string, payload: { environmentId: string; filename: string }) =>
    api.post<ApiResponse<{ executionId: string }>>(`/tests/${testId}/run-spec`, payload),
};
