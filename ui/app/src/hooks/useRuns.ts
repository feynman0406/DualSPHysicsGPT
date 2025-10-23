import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import type { CreateRunRequest, RunSummary } from '../types/runs';

export const runsQueryKeys = {
  all: ['runs'] as const,
  list: () => ['runs', 'list'] as const,
  detail: (runId: string) => ['runs', 'detail', runId] as const,
  logs: (runId: string) => ['runs', runId, 'logs'] as const,
  metrics: (runId: string) => ['runs', runId, 'metrics'] as const,
  artifacts: (runId: string) => ['runs', runId, 'artifacts'] as const,
  step: (runId: string, step: string) => ['runs', runId, 'step', step] as const,
};

export const useRuns = () => {
  return useQuery({
    queryKey: runsQueryKeys.list(),
    queryFn: () => apiClient.listRuns(),
    refetchInterval: query => {
      const runs = query.state.data as RunSummary[] | undefined;
      if (!runs) {
        return 30_000;
      }
      const hasActiveRun = runs.some(run => run.status === 'running' || run.status === 'queued');
      return hasActiveRun ? 15_000 : 60_000;
    },
  });
};

export const useRun = (runId: string | undefined) => {
  return useQuery({
    queryKey: runId ? runsQueryKeys.detail(runId) : ['runs', 'detail', 'unknown'],
    queryFn: () => {
      if (!runId) {
        throw new Error('runId is required');
      }
      return apiClient.getRun(runId);
    },
    enabled: Boolean(runId),
    refetchInterval: query => {
      const run = query.state.data as RunSummary | undefined;
      if (!run) {
        return 15_000;
      }
      const isRunning = run.status === 'running' || run.status === 'queued';
      return isRunning ? 10_000 : false;
    },
  });
};

export const useCreateRun = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateRunRequest) => apiClient.createRun(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: runsQueryKeys.list() });
    },
  });
};


export const useDeleteRun = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (runId: string) => apiClient.deleteRun(runId),
    onSuccess: (_data, runId) => {
      queryClient.invalidateQueries({ queryKey: runsQueryKeys.list() });
      queryClient.removeQueries({ queryKey: runsQueryKeys.detail(runId) });
      queryClient.removeQueries({ queryKey: runsQueryKeys.logs(runId) });
      queryClient.removeQueries({ queryKey: runsQueryKeys.metrics(runId) });
      queryClient.removeQueries({ queryKey: runsQueryKeys.artifacts(runId) });
      queryClient.removeQueries({
        predicate: query =>
          Array.isArray(query.queryKey) &&
          query.queryKey.length > 3 &&
          query.queryKey[0] === 'runs' &&
          query.queryKey[1] === runId &&
          query.queryKey[2] === 'step',
      });
    },
  });
};

export const useRunsByStatus = (status: string | 'all') => {
  const { data, ...rest } = useRuns();

  const filtered = useMemo(() => {
    if (!data) {
      return [] as RunSummary[];
    }
    if (status === 'all') {
      return data;
    }
    return data.filter(run => run.status === status);
  }, [data, status]);

  return {
    data: filtered,
    allRuns: data,
    ...rest,
  };
};
