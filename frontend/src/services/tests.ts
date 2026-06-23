import { api } from '../api/client';
import { ApiResponse, Test } from '../types';

export interface TestUpdatePayload {
  name: string;
  prompt: string;
  status: string;
  collection_id: string;
  environment_ids: string[];
  duplicate: boolean;
}

export const testsService = {
  update: (id: string, payload: TestUpdatePayload) =>
    api.put<ApiResponse<Test>>(`/tests/${id}`, payload),

  delete: (id: string) =>
    api.del<ApiResponse<unknown>>(`/tests/${id}`),
};
