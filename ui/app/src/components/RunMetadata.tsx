import { formatDuration, formatRelativeTime, formatUtc } from '../utils/time';
import type { RunSummary } from '../types/runs';
import RunStatusBadge from './RunStatusBadge';
import './RunMetadata.css';

interface RunMetadataProps {
  run: RunSummary;
  onRerun?: () => void;
  onDownloadLog?: () => void;
  rerunDisabled?: boolean;
}

const RunMetadata = ({ run, onRerun, onDownloadLog, onDelete, rerunDisabled, deleteDisabled }: RunMetadataProps) => {
  return (
    <header className="run-metadata">
      <div>
        <p className="breadcrumb">Runs / {run.runId}</p>
        <div className="metadata-title">
          <h1>{run.query || run.runId}</h1>
          <RunStatusBadge status={run.status} />
        </div>
        <p className="meta-line">
          Started {formatRelativeTime(run.startedAt)} ¡P Duration{' '}
          {formatDuration(run.durationSeconds)}
        </p>
        {run.finishedAt && (
          <p className="meta-line">Completed at {formatUtc(run.finishedAt)} (UTC)</p>
        )}
      </div>
      <div className="metadata-actions">
        <button type="button" className="ghost" onClick={onDownloadLog}>
          Download log
        </button>
        <button type="button" className="primary" onClick={onRerun} disabled={rerunDisabled}>
          Rerun
        </button>
        {onDelete && (
          <button type="button" className="danger" onClick={onDelete} disabled={deleteDisabled}>
            Delete run
          </button>
        )}
      </div>
    </header>
  );
};

export default RunMetadata;



