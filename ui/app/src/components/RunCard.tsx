import clsx from 'clsx';
import { Link } from 'react-router-dom';
import type { RunSummary, RunStepStatus } from '../types/runs';
import { formatDuration, formatRelativeTime } from '../utils/time';
import RunStatusBadge from './RunStatusBadge';
import './RunCard.css';

interface RunCardProps {
  run: RunSummary;
}

const STAGE_LABELS: Record<string, string> = {
  init: 'Init',
  sim: 'Sim',
  post: 'Post',
};

const stateIcon = (state: RunStepStatus['state']) => {
  switch (state) {
    case 'completed':
      return 'OK';
    case 'running':
      return 'RUN';
    case 'failed':
      return 'ERR';
    case 'pending':
    case 'idle':
    default:
      return '--';
  }
};

const RunCard = ({ run }: RunCardProps) => {
  const to = `/runs/${encodeURIComponent(run.runId)}`;
  const stages = run.stageCheckpoints ?? [];
  const stlSummary = run.summary?.externalStl;
  const hasExternalStl =
    (stlSummary && typeof stlSummary === 'object') || run.summary?.externalStlAttached === true;
  const stlLabel =
    stlSummary && typeof stlSummary === 'object' ? stlSummary.filename : undefined;
  const reasoningLabel =
    run.reasoningLevel ??
    run.reasoningConfig?.effort ??
    run.reasoningConfig?.level ??
    run.reasoningConfig?.intensity ??
    undefined;
  const dependencyCount = run.summary?.dependencyCount;
  const dependencyWarnings = run.summary?.dependencyWarnings ?? 0;
  const hasDependencySummary =
    (typeof dependencyCount === 'number' && dependencyCount > 0) || dependencyWarnings > 0;
  const dependencyBadgeTitle = hasDependencySummary
    ? `Dependencies: ${dependencyCount ?? 0}${
        dependencyWarnings > 0
          ? ` (${dependencyWarnings} warning${dependencyWarnings > 1 ? 's' : ''})`
          : ''
      }`
    : 'Dependencies not reported';
  const dependencyMetaValue =
    typeof dependencyCount === 'number'
      ? `${dependencyCount}${dependencyWarnings > 0 ? ` (${dependencyWarnings}⚠)` : ''}`
      : dependencyWarnings > 0
        ? `${dependencyWarnings}⚠`
        : '—';

  return (
    <Link className="run-card" to={to} aria-label={`Open run ${run.runId}`}>
      <div className="run-card-header">
        <RunStatusBadge status={run.status} />
        <span className="run-id">{run.runId}</span>
      </div>

      {(hasDependencySummary || hasExternalStl) && (
        <div className="run-card-flags">
          {hasDependencySummary && (
            <span
              className={clsx('dependency-badge', { warning: dependencyWarnings > 0 })}
              title={dependencyBadgeTitle}
            >
              Deps {dependencyCount ?? 0}
              {dependencyWarnings > 0 ? ` • ${dependencyWarnings}⚠` : ''}
            </span>
          )}
          {hasExternalStl && (
            <span
              className="stl-badge"
              title={stlLabel ? `External STL: ${stlLabel}` : 'External STL attached'}
            >
              STL
            </span>
          )}
        </div>
      )}

      <p className="run-query">{run.query}</p>

      {stages.length > 0 && (
        <ul className="run-stage-summary" aria-label="Stage status">
          {stages.map(stage => {
            const label = STAGE_LABELS[stage.step] ?? stage.step.slice(0, 3);
            const icon = stateIcon(stage.state ?? 'pending');
            return (
              <li key={stage.step} className={`stage state-${stage.state ?? 'pending'}`}>
                <span className="stage-icon" aria-hidden="true">
                  {icon}
                </span>
                <span className="stage-label">{label}</span>
              </li>
            );
          })}
        </ul>
      )}

      <dl className="run-meta">
        <div>
          <dt>Triggered</dt>
          <dd>{formatRelativeTime(run.startedAt)}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatDuration(run.durationSeconds)}</dd>
        </div>
        {run.modelName && (
          <div>
            <dt>Model</dt>
            <dd>{run.modelName}</dd>
          </div>
        )}
        {reasoningLabel && (
          <div>
            <dt>Reasoning</dt>
            <dd>{reasoningLabel}</dd>
          </div>
        )}
        <div>
          <dt>Artifacts</dt>
          <dd>{run.summary?.artifactCount ?? 'N/A'}</dd>
        </div>
        <div>
          <dt>Dependencies</dt>
          <dd>{dependencyMetaValue}</dd>
        </div>
      </dl>
    </Link>
  );
};

export default RunCard;
