import { formatDuration, formatRelativeTime, formatUtc } from '../utils/time';
import { formatFileSize } from '../utils/files';
import type { RunSummary } from '../types/runs';
import RunStatusBadge from './RunStatusBadge';
import './RunMetadata.css';

interface RunMetadataProps {
  run: RunSummary;
  onRerun?: () => void;
  onDownloadLog?: () => void;
  onDelete?: () => void;
  rerunDisabled?: boolean;
  deleteDisabled?: boolean;
}

const RunMetadata = ({ run, onRerun, onDownloadLog, onDelete, rerunDisabled, deleteDisabled }: RunMetadataProps) => {
  const stlSummary = run.summary?.externalStl;
  const hasExternalStl =
    (stlSummary && typeof stlSummary === 'object') || run.summary?.externalStlAttached === true;
  const stlName =
    stlSummary && typeof stlSummary === 'object' ? stlSummary.filename : undefined;
  const stlSize =
    stlSummary && typeof stlSummary === 'object' && typeof stlSummary.sizeBytes === 'number'
      ? formatFileSize(stlSummary.sizeBytes)
      : undefined;
  const reasoningLabel =
    run.reasoningLevel ??
    run.reasoningConfig?.effort ??
    run.reasoningConfig?.level ??
    run.reasoningConfig?.intensity ??
    undefined;


  return (
    <header className="run-metadata">
      <div>
        <p className="breadcrumb">Runs / {run.runId}</p>
        <div className="metadata-title">
          <h1>{run.query || run.runId}</h1>
          <RunStatusBadge status={run.status} />
        </div>
        <p className="meta-line">
          Started {formatRelativeTime(run.startedAt)} | Duration{' '}
          {formatDuration(run.durationSeconds)}
        </p>
        {run.modelName && (
          <p className="meta-line">Model: {run.modelName}</p>
        )}
        {reasoningLabel && (
          <p className="meta-line">Reasoning: {reasoningLabel}</p>
        )}
        {hasExternalStl && (
          <p className="meta-line">
            External STL: {stlName ?? 'Attached'}
            {stlSize ? ` | ${stlSize}` : null}
          </p>
        )}
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


