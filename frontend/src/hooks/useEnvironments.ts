import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { environmentsService, EnvironmentDetail, EnvironmentSaveBody } from '../services/environments';

export type EnvironmentModalState =
  | { type: 'create' }
  | { type: 'edit'; env: EnvironmentDetail }
  | { type: 'delete'; env: EnvironmentDetail }
  | null;

export function useEnvironments() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<EnvironmentModalState>(null);
  const [serverError, setServerError] = useState('');

  const query = useQuery({
    queryKey: ['environments'],
    queryFn: environmentsService.getAll,
  });

  const environments = query.data?.data ?? [];

  function invalidate() {
    qc.invalidateQueries({ queryKey: ['environments'] });
  }

  const createMutation = useMutation({
    mutationFn: (body: EnvironmentSaveBody) => environmentsService.create(body),
    onSuccess: () => { invalidate(); setModal(null); setServerError(''); },
    onError: (err: Error) => setServerError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: EnvironmentSaveBody }) =>
      environmentsService.update(id, body),
    onSuccess: () => { invalidate(); setModal(null); setServerError(''); },
    onError: (err: Error) => setServerError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => environmentsService.delete(id),
    onSuccess: () => { invalidate(); setModal(null); },
    onError: (err: Error) => setServerError(err.message),
  });

  function openCreate() { setServerError(''); setModal({ type: 'create' }); }
  function openEdit(env: EnvironmentDetail) { setServerError(''); setModal({ type: 'edit', env }); }
  function openDelete(env: EnvironmentDetail) { setServerError(''); setModal({ type: 'delete', env }); }
  function closeModal() { setModal(null); setServerError(''); }

  return {
    environments,
    isLoading: query.isLoading,
    modal,
    serverError,
    createMutation,
    updateMutation,
    deleteMutation,
    openCreate, openEdit, openDelete, closeModal,
  };
}
