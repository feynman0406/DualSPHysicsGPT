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

  return (
    <Link className="run-card" to={to} aria-label={`Open run ${run.runId}`}>
      <div className="run-card-header">
        <RunStatusBadge status={run.status} />
        {hasExternalStl && (
          <span className="stl-badge" title={stlLabel ? `External STL: ${stlLabel}` : 'External STL attached'}>
            STL
          </span>
        )}
        <span className="run-id">{run.runId}</span>
      </div>
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
        <div>
          <dt>Artifacts</dt>
          <dd>{run.summary?.artifactCount ?? 'N/A'}</dd>
        </div>
      </dl>
    </Link>
  );
};

export default RunCard;
