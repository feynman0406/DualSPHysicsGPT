import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import RunMetadata from '../components/RunMetadata';
import RunStepper from '../components/RunStepper';
import StageProgress from '../components/StageProgress';
import TabNav from '../components/TabNav';
import OverviewPanel from '../components/OverviewPanel';
import LogViewer from '../components/LogViewer';
import MetricsPanel from '../components/MetricsPanel';
import ArtifactViewer from '../components/ArtifactViewer';
import DependencyList from '../components/DependencyList';
import { apiClient } from '../services/api';
import type { RunStepStatus } from '../types/runs';
import { useCreateRun, useDeleteRun, useRun } from '../hooks/useRuns';
import {
  useLogStreams,
  useRunArtifacts,
  useRunLogs,
  useRunMetrics,
  useRunStepDetail,
} from '../hooks/useRunResources';
import './RunDetailPage.css';

type TabId = 'overview' | 'logs' | 'metrics' | 'artifacts';

interface RunDetailPageProps {
  initialTab?: TabId;
}

const DEFAULT_STEPS: RunStepStatus[] = [
  { step: 'reference_search', state: 'idle' },
  { step: 'config_generation', state: 'idle' },
  { step: 'execution', state: 'idle' },
];

const RunDetailPage = ({ initialTab = 'overview' }: RunDetailPageProps) => {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);
  const { data: run, isLoading, error } = useRun(runId);
  const [selectedStep, setSelectedStep] = useState<string>('reference_search');

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const stages = run?.stageCheckpoints ?? [];

  const steps = run?.stepStatus ?? DEFAULT_STEPS;

  useEffect(() => {
    if (steps.length === 0) {
      return;
    }
    setSelectedStep(prev => {
      if (prev && steps.some(step => step.step === prev)) {
        return prev;
      }
      const firstActionable = steps.find(step => step.state !== 'idle') ?? steps[0];
      return firstActionable.step;
    });
  }, [steps]);

  const logsQuery = useRunLogs(runId, {
    refetchInterval: run && (run.status === 'running' || run.status === 'queued') ? 4_000 : 15_000,
  });
  const logStreams = useLogStreams(logsQuery.entries);

  const metricsQuery = useRunMetrics(runId);
  const artifactsQuery = useRunArtifacts(runId);
  const stepDetailQuery = useRunStepDetail(runId, selectedStep);

  const createRun = useCreateRun();
  const deleteRun = useDeleteRun();

  const handleRerun = async () => {
    if (!run) {
      return;
    }
    try {
      await createRun.mutateAsync({
        query: run.query,
        execute: false,
        pauseAfterAgent1: false,
      });
    } catch (err) {
      window.alert('Failed to queue rerun: ' + String((err as Error).message ?? 'Unknown error'));
    }
  };

  const handleDownloadLog = () => {
    if (!runId) {
      return;
    }
    const url = `/api/runs/${encodeURIComponent(runId)}/logs/download`;
    window.open(url, '_blank');
  };

  const handleDelete = async () => {
    if (!run) {
      return;
    }
    const confirmed = window.confirm(`Delete run ${run.runId}? This removes its history and artifacts.`);
    if (!confirmed) {
      return;
    }
    try {
      await deleteRun.mutateAsync(run.runId);
      navigate('/runs', { replace: true });
    } catch (err) {
      window.alert(`Failed to delete run: ${String((err as Error).message ?? 'Unknown error')}`);
    }
  };

  const tabOptions = useMemo(
    () => [
      { id: 'overview' as TabId, label: 'Overview' },
      {
        id: 'logs' as TabId,
        label: 'Logs',
        badge: logsQuery.entries.length > 0 ? String(logsQuery.entries.length) : undefined,
      },
      { id: 'metrics' as TabId, label: 'Metrics' },
      {
        id: 'artifacts' as TabId,
        label: 'Artifacts',
        badge:
          (artifactsQuery.data?.length ?? 0) > 0
            ? String(artifactsQuery.data?.length ?? 0)
            : undefined,
      },
    ],
    [logsQuery.entries.length, artifactsQuery.data?.length],
  );

  if (isLoading || !runId) {
    return (
      <section className="run-detail-page">
        <div className="loading">Loading run details...</div>
      </section>
    );
  }

  if (error || !run) {
    return (
      <section className="run-detail-page">
        <div className="error" role="alert">
          <strong>Unable to load run.</strong>
          <div>{String((error as Error)?.message ?? 'Unknown error')}</div>
        </div>
      </section>
    );
  }

  return (
    <section className="run-detail-page">
      <RunMetadata
        run={run}
        onRerun={handleRerun}
        onDownloadLog={handleDownloadLog}
        onDelete={handleDelete}
        rerunDisabled={createRun.isPending || deleteRun.isPending}
        deleteDisabled={deleteRun.isPending}
      />

      <StageProgress stages={stages} />

      <RunStepper
        steps={steps}
        currentStep={selectedStep}
        onStepSelect={step => setSelectedStep(step.step)}
      />

      <div className="run-tabs">
        <TabNav<TabId>
          tabs={tabOptions}
          active={activeTab}
          onChange={(tabId: TabId) => setActiveTab(tabId)}
        />
      </div>

      {activeTab === 'overview' && <OverviewPanel run={run} stepDetail={stepDetailQuery.data} />}

      {activeTab === 'logs' && (
        <LogViewer
          entries={logsQuery.entries}
          isLoading={logsQuery.isFetching && logsQuery.entries.length === 0}
          error={logsQuery.error}
          onRetry={() => logsQuery.refetch()}
          availableStreams={logStreams}
        />
      )}

      {activeTab === 'metrics' && (
        <MetricsPanel
          metrics={metricsQuery.data}
          isLoading={metricsQuery.isLoading}
          error={metricsQuery.error}
          onRetry={() => metricsQuery.refetch()}
        />
      )}

      {activeTab === 'artifacts' && (
        <div className="artifact-and-dependencies">
          <ArtifactViewer
            artifacts={artifactsQuery.data ?? []}
            isLoading={artifactsQuery.isLoading}
            error={artifactsQuery.error}
            onRefresh={() => artifactsQuery.refetch()}
            loadContent={artifact => apiClient.fetchArtifactContent(artifact, run.runId)}
          />
          <DependencyList
            runId={run.runId}
            manifest={run.dependencyManifest}
            summaryCount={run.summary?.dependencyCount}
            summaryWarnings={run.summary?.dependencyWarnings}
            buildDownloadUrl={(id, path) => apiClient.buildDependencyDownloadUrl(id, path)}
          />
        </div>
      )}
    </section>
  );
};

export default RunDetailPage;







