import { api } from '../api/client';

export const specsService = {
  getContent: (filename: string) =>
    api.get<{ data: { content: string }; error: string | null }>(
      `/specs/view?file=${encodeURIComponent(filename)}`,
    ),
};
