import { api } from '../api/client';
import { ApiResponse, PlanningMemoryEntry, CorrectionAdvisory } from '../types';

export interface CorrectionPayload {
  failedAtStep: number;
  correction: string;
  environmentId: string;
}

export const planningMemoryService = {
  list: (testId: string) =>
    api.get<ApiResponse<PlanningMemoryEntry[]>>(`/tests/${testId}/planning-memory`),

  create: (testId: string, content: string) =>
    api.post<ApiResponse<PlanningMemoryEntry & { advisory: CorrectionAdvisory }>>(
      `/tests/${testId}/planning-memory`,
      { content },
    ),

  update: (testId: string, id: string, content: string) =>
    api.patch<ApiResponse<PlanningMemoryEntry>>(
      `/tests/${testId}/planning-memory/${id}`,
      { content },
    ),

  remove: (testId: string, id: string) =>
    api.del<ApiResponse<{ id: string }>>(`/tests/${testId}/planning-memory/${id}`),

  submitCorrection: (testId: string, payload: CorrectionPayload) =>
    api.post<ApiResponse<{ executionId: string; advisory: CorrectionAdvisory }>>(
      `/tests/${testId}/corrections`,
      payload,
    ),
};
