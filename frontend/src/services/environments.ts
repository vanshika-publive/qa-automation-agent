import { api } from '../api/client';
import { ApiResponse } from '../types';

export interface EnvironmentDetail {
  id: string;
  name: string;
  baseUrl: string;
  description: string;
  isActive: boolean;
  createdAt: string;
  loginEmail: string;
  publisher: string;
  publisherId: string;
  hasPassword: boolean;
}

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
    api.get<ApiResponse<EnvironmentDetail[]>>('/environments'),

  create: (body: EnvironmentSaveBody) =>
    api.post<ApiResponse<EnvironmentDetail>>('/environments', body),

  update: (id: string, body: EnvironmentSaveBody) =>
    api.put<ApiResponse<EnvironmentDetail>>(`/environments/${id}`, body),

  delete: (id: string) =>
    api.del<ApiResponse<{ id: string }>>(`/environments/${id}`),
};
