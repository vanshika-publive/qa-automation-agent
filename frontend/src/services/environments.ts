import { api } from '../api/client';
import { ApiResponse, Environment } from '../types';

export interface EnvironmentSaveBody {
  name: string;
  baseUrl: string;
  description: string;
  isActive: boolean;
  loginEmail: string;
  loginPassword?: string;
}

export const environmentsService = {
  getAll: () =>
    api.get<ApiResponse<Environment[]>>('/environments'),

  create: (body: EnvironmentSaveBody) =>
    api.post<ApiResponse<Environment>>('/environments', body),

  update: (id: string, body: EnvironmentSaveBody) =>
    api.put<ApiResponse<Environment>>(`/environments/${id}`, body),

  delete: (id: string) =>
    api.del<ApiResponse<{ id: string }>>(`/environments/${id}`),
};
