import { api } from '../api/client';
import { ApiResponse, Collection, Test, SpecFile } from '../types';

export const collectionsService = {
  getAll: () =>
    api.get<ApiResponse<Collection[]>>('/collections'),

  create: (name: string) =>
    api.post<ApiResponse<Collection>>('/collections', { name }),

  rename: (id: string, name: string) =>
    api.patch<ApiResponse<{ id: string; name: string }>>(`/collections/${id}`, { name }),

  delete: (id: string) =>
    api.del<ApiResponse<unknown>>(`/collections/${id}`),

  getTests: (collectionId: string) =>
    api.get<ApiResponse<Test[]>>(`/collections/${collectionId}/tests`),

  createTest: (collectionId: string, payload: { name: string; prompt: string }) =>
    api.post<ApiResponse<{ id: string }>>(`/collections/${collectionId}/tests`, payload),

  getSpecs: (collectionId: string) =>
    api.get<ApiResponse<SpecFile[]>>(`/collections/${collectionId}/specs`),

  runAllSpecs: (collectionId: string, environmentId: string) =>
    api.post<ApiResponse<{ executionId: string }>>(
      `/collections/${collectionId}/run-all-specs`,
      { environmentId },
    ),
};
