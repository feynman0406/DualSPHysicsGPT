import type { RunStepStatus } from '../types/runs';
import { formatDuration, formatRelativeTime, formatUtc } from '../utils/time';
import './StageProgress.css';

interface StageProgressProps {
  stages?: RunStepStatus[];
}

const LABELS: Record<string, string> = {
  init: 'Initialization',
  sim: 'Simulation',
  post: 'Post-Processing',
};

const PROGRESS_WIDTH: Record<string, string> = {
  idle: '0%',
  pending: '15%',
  running: '60%',
  completed: '100%',
  failed: '100%',
  skipped: '0%',
};

const StageProgress = ({ stages }: StageProgressProps) => {
  if (!stages || stages.length === 0) {
    return null;
  }

  return (
    <section className="stage-progress" aria-label="Run stage progress">
      {stages.map(stage => {
        const label = LABELS[stage.step] ?? stage.step.replace(/_/g, ' ');
        const state = stage.state ?? 'pending';
        const width = PROGRESS_WIDTH[state] ?? '0%';
        const duration =
          stage.startedAt && stage.finishedAt
            ? formatDuration((Date.parse(stage.finishedAt) - Date.parse(stage.startedAt)) / 1000)
            : undefined;

        return (
          <article key={stage.step} className={`stage-progress-item state-${state}`}>
            <header className="stage-progress-header">
              <div>
                <h3>{label}</h3>
                <span className="stage-state">{state}</span>
              </div>
              {duration && <span className="stage-duration">{duration}</span>}
            </header>
            <div
              className="stage-progress-bar"
              role="progressbar"
              aria-valuetext={`${label} ${state}`}
            >
              <div className="stage-progress-fill" style={{ width }} />
            </div>
            <dl className="stage-progress-timestamps">
              <div>
                <dt>Started</dt>
                <dd>
                  {stage.startedAt
                    ? `${formatRelativeTime(stage.startedAt)} | ${formatUtc(stage.startedAt)}`
                    : '--'}
                </dd>
              </div>
              <div>
                <dt>Finished</dt>
                <dd>
                  {stage.finishedAt
                    ? `${formatRelativeTime(stage.finishedAt)} | ${formatUtc(stage.finishedAt)}`
                    : state === 'running'
                      ? 'In progress'
                      : '--'}
                </dd>
              </div>
            </dl>
            {stage.message && <p className="stage-progress-message">{stage.message}</p>}
          </article>
        );
      })}
    </section>
  );
};

export default StageProgress;
