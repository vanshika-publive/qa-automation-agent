import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CollectionFilterState, DEFAULT_COLLECTION_FILTERS } from '../components/CollectionFilterDrawer';
import { collectionsService } from '../services/collections';
import { fmtDate } from '../utils/formatters';

export function useCollections() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [colFilters, setColFilters] = useState<CollectionFilterState>(DEFAULT_COLLECTION_FILTERS);

  const query = useQuery({
    queryKey: ['collections'],
    queryFn: collectionsService.getAll,
  });

  const collections = query.data?.data ?? [];

  const dateActive = !!(colFilters.from || colFilters.to);
  const filtersActive = !!search.trim() || dateActive;

  const filteredCollections = useMemo(() => {
    const q = search.trim().toLowerCase();
    return collections.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q)) return false;
      const day = c.createdAt.slice(0, 10);
      if (colFilters.from && day < colFilters.from) return false;
      if (colFilters.to && day > colFilters.to) return false;
      return true;
    });
  }, [collections, search, colFilters]);

  const dateRangeLabel = [
    colFilters.from ? fmtDate(`${colFilters.from}T12:00:00Z`) : null,
    colFilters.to   ? fmtDate(`${colFilters.to}T12:00:00Z`)   : null,
  ].filter(Boolean).join(' – ');

  const createMutation = useMutation({
    mutationFn: collectionsService.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collections'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: collectionsService.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collections'] }),
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => collectionsService.rename(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collections'] }),
  });

  return {
    collections,
    filteredCollections,
    isLoading: query.isLoading,
    search, setSearch,
    colFilters, setColFilters,
    dateActive, filtersActive, dateRangeLabel,
    clearAllFilters: () => { setSearch(''); setColFilters(DEFAULT_COLLECTION_FILTERS); },
    createMutation,
    deleteMutation,
    renameMutation,
  };
}
