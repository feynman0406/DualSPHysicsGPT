import type { MetricsSnapshot, ResourceUsageSample } from '../types/runs';
import './MetricsPanel.css';

interface MetricsPanelProps {
  metrics: MetricsSnapshot | null | undefined;
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
}

const formatPercent = (value?: number) => {
  if (value === undefined || Number.isNaN(value)) {
    return '--';
  }
  return `${(value * 100).toFixed(1)}%`;
};

const formatPercentValue = (value?: number) => {
  if (value === undefined || Number.isNaN(value)) {
    return '--';
  }
  return `${value.toFixed(1)}%`;
};

const formatMemory = (used?: number, total?: number) => {
  if (used === undefined) {
    return '--';
  }
  if (total === undefined) {
    return `${used.toFixed(0)} MB`;
  }
  return `${used.toFixed(0)} / ${total.toFixed(0)} MB`;
};

const latestResourceSample = (usage?: ResourceUsageSample[] | null) => {
  if (!usage || usage.length === 0) {
    return undefined;
  }
  return usage[usage.length - 1];
};

const MetricsPanel = ({ metrics, isLoading, error, onRetry }: MetricsPanelProps) => {
  if (error) {
    return (
      <div className="metrics-panel error" role="alert">
        <strong>Unable to load metrics.</strong>
        <div>{String((error as Error).message ?? 'Unknown error')}</div>
        <button type="button" className="ghost" onClick={onRetry} disabled={isLoading}>
          Retry
        </button>
      </div>
    );
  }

  if (isLoading && !metrics) {
    return (
      <div className="metrics-panel loading">
        <p>Loading metrics...</p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="metrics-panel empty">
        <p>Metrics are not yet available for this run.</p>
      </div>
    );
  }

  const resource = latestResourceSample(metrics.resourceUsage);
  const resourceNotes =
    resource?.notes ?? metrics.resourceUsage?.flatMap(sample => sample.notes ?? []) ?? [];

  return (
    <div className="metrics-panel">
      <div className="metric-card">
        <h3>Duration</h3>
        <p>{metrics.durationSeconds ? `${metrics.durationSeconds.toFixed(1)}s` : '--'}</p>
        <span>Compared to baseline: {formatPercent(metrics.baselineDelta?.durationPercent)}</span>
      </div>

      <div className="metric-card">
        <h3>Resource Usage</h3>
        {resource ? (
          <>
            <p>CPU {formatPercentValue(resource.cpuPercent)}</p>
            <p>
              Memory {formatPercentValue(resource.memoryPercent)} (
              {formatMemory(resource.memoryUsedMb, resource.memoryTotalMb)})
            </p>
            {resource.gpu && resource.gpu.length > 0 ? (
              <ul className="gpu-metrics">
                {resource.gpu.map(device => (
                  <li key={device.name}>
                    <strong>{device.name}</strong>  |  {formatPercentValue(device.utilizationPercent)}{' '}
                     | {` ${formatMemory(device.memoryUsedMb, device.memoryTotalMb)}`}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="metric-note">GPU metrics unavailable</span>
            )}
          </>
        ) : (
          <p className="metric-note">Resource telemetry has not been collected yet.</p>
        )}
        {resourceNotes.length > 0 && (
          <ul className="metric-note-list">
            {resourceNotes.map((note, index) => (
              <li key={`${note}-${index}`}>{note}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="metric-card">
        <h3>Token usage</h3>
        <p>
          Input {metrics.tokenUsage?.input ?? '--'}  |  Output {metrics.tokenUsage?.output ?? '--'}
        </p>
        <span>
          Cost {metrics.tokenUsage?.costUsd ? `$${metrics.tokenUsage.costUsd.toFixed(2)}` : '--'}
        </span>
      </div>

      <div className="metric-card">
        <h3>Retrieval</h3>
        <p>Recall@5 {formatPercent(metrics.retrieval?.recallAt5)}</p>
        <span>Total sources {metrics.retrieval?.totalSources ?? '--'}</span>
      </div>

      <div className="metric-card">
        <h3>Step Durations</h3>
        <ul>
          {metrics.stepDurations ? (
            Object.entries(metrics.stepDurations).map(([step, value]) => (
              <li key={step}>
                <strong>{step.replace(/_/g, ' ')}:</strong> {value.toFixed(1)}s
              </li>
            ))
          ) : (
            <li>No step timing available.</li>
          )}
        </ul>
      </div>
    </div>
  );
};

export default MetricsPanel;
