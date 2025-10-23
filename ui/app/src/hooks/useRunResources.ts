import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import type { ArtifactMetadata, LogEntry } from '../types/runs';
import { runsQueryKeys } from './useRuns';

export const useRunLogs = (runId: string | undefined, options?: { refetchInterval?: number }) => {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const pollInterval = options?.refetchInterval ?? 7_500;

  const query = useQuery({
    queryKey: runId ? runsQueryKeys.logs(runId) : ['runs', 'logs', 'unknown'],
    queryFn: async () => {
      if (!runId) {
        return [] as LogEntry[];
      }
      const lastEntry = entries.length > 0 ? entries[entries.length - 1] : undefined;
      const fromSequence = lastEntry?.sequence;
      const payload = await apiClient.getRunLogs(runId, {
        fromSequence: fromSequence !== undefined ? fromSequence + 1 : undefined,
      });
      return payload;
    },
    enabled: Boolean(runId),
    refetchInterval: pollInterval,
  });

  useEffect(() => {
    if (query.data && query.data.length > 0) {
      setEntries(prev => {
        const next = [...prev];
        for (const entry of query.data) {
          if (!next.some(existing => existing.sequence === entry.sequence)) {
            next.push(entry);
          }
        }
        return next.sort((a, b) => a.sequence - b.sequence);
      });
    }
  }, [query.data]);

  useEffect(() => {
    if (!runId) {
      setEntries([]);
    }
  }, [runId]);

  return { entries, ...query };
};

export const useRunMetrics = (runId: string | undefined) => {
  return useQuery({
    queryKey: runId ? runsQueryKeys.metrics(runId) : ['runs', 'metrics', 'unknown'],
    queryFn: () => {
      if (!runId) {
        throw new Error('runId is required');
      }
      return apiClient.getRunMetrics(runId);
    },
    enabled: Boolean(runId),
    staleTime: 20_000,
  });
};

export const useRunArtifacts = (runId: string | undefined) => {
  return useQuery({
    queryKey: runId ? runsQueryKeys.artifacts(runId) : ['runs', 'artifacts', 'unknown'],
    queryFn: async () => {
      if (!runId) {
        return [] as ArtifactMetadata[];
      }
      return apiClient.getRunArtifacts(runId);
    },
    enabled: Boolean(runId),
  });
};

export const useRunStepDetail = (runId: string | undefined, step: string | undefined) => {
  return useQuery({
    queryKey: runId && step ? runsQueryKeys.step(runId, step) : ['runs', 'step', 'unknown'],
    queryFn: () => {
      if (!runId || !step) {
        throw new Error('runId and step are required');
      }
      return apiClient.getStepDetail(runId, step);
    },
    enabled: Boolean(runId && step),
    staleTime: 10_000,
  });
};

export const useLogStreams = (entries: LogEntry[]) => {
  return useMemo(() => {
    const streams = new Set<string>();
    for (const entry of entries) {
      if (entry.stream) {
        streams.add(entry.stream);
      }
    }
    return Array.from(streams);
  }, [entries]);
};
