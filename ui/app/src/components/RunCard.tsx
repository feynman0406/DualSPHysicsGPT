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
      return '✓';
    case 'running':
      return '…';
    case 'failed':
      return '!';
    case 'pending':
    case 'idle':
      return '•';
    default:
      return '•';
  }
};

const RunCard = ({ run }: RunCardProps) => {
  const to = `/runs/${encodeURIComponent(run.runId)}`;
  const stages = run.stageCheckpoints ?? [];

  return (
    <Link className="run-card" to={to} aria-label={`Open run ${run.runId}`}>
      <div className="run-card-header">
        <RunStatusBadge status={run.status} />
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
          <dd>{run.summary?.artifactCount ?? '—'}</dd>
        </div>
      </dl>
    </Link>
  );
};

export default RunCard;
