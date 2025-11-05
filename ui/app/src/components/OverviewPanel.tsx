import type { RunSummary, StepDetailPayload } from '../types/runs';
import './OverviewPanel.css';

interface OverviewPanelProps {
  run: RunSummary;
  stepDetail?: StepDetailPayload;
}

const OverviewPanel = ({ run, stepDetail }: OverviewPanelProps) => {
  const manifest = run.dependencyManifest;
  const manifestFiles = Array.isArray(manifest?.files) ? manifest?.files : [];
  const dependencyCount =
    run.summary?.dependencyCount ?? (manifestFiles.length > 0 ? manifestFiles.length : undefined);
  const dependencyWarnings =
    run.summary?.dependencyWarnings ?? (Array.isArray(manifest?.warnings) ? manifest.warnings.length : 0);
  const manifestWarnings = Array.isArray(manifest?.warnings) ? manifest.warnings : [];
  const displayDependencies = manifestFiles.slice(0, 4);
  const remainingDependencies = Math.max(manifestFiles.length - displayDependencies.length, 0);

  return (
    <div className="overview-panel">
      <section className="overview-cards">
        <div>
          <h3>Primary Output</h3>
          <p>{run.summary?.primaryOutput ?? 'Pending'}</p>
        </div>
        <div>
          <h3>Artifacts</h3>
          <p>{run.summary?.artifactCount ?? '—'}</p>
        </div>
        <div>
          <h3>Exit Code</h3>
          <p>{run.exitCode ?? '—'}</p>
        </div>
        <div>
          <h3>Dependencies</h3>
          <p>
            {dependencyCount ?? '—'}
            {dependencyWarnings > 0 ? ` (${dependencyWarnings} warning${dependencyWarnings > 1 ? 's' : ''})` : ''}
          </p>
        </div>
      </section>
      <section className="overview-detail">
        <div>
          <h3>Prompt</h3>
          <p>{stepDetail?.overview?.inputPrompt ?? 'Prompt details will appear once available.'}</p>
        </div>
        <div>
          <h3>Retrieved references</h3>
          {stepDetail?.overview?.retrievedReferences ? (
            <ul>
              {stepDetail.overview.retrievedReferences.map(reference => (
                <li key={reference.filename}>
                  <strong>{reference.filename}</strong>
                  {reference.score !== undefined ? (
                    <span> | Score {(reference.score * 100).toFixed(1)}%</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p>Reference summary pending backend instrumentation.</p>
          )}
        </div>
        <div>
          <h3>Dependency warnings</h3>
          {manifestWarnings.length > 0 ? (
            <ul className="dependency-warnings">
              {manifestWarnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p>No dependency warnings recorded.</p>
          )}
        </div>
        <div>
          <h3>Tracked dependencies</h3>
          {displayDependencies.length > 0 ? (
            <ul className="dependency-summary">
              {displayDependencies.map(file => (
                <li key={file.path}>
                  <strong>{file.path}</strong>
                  {file.status ? <span className={`status status-${file.status}`}>{file.status}</span> : null}
                  {file.purpose ? <span className="purpose"> — {file.purpose}</span> : null}
                </li>
              ))}
              {remainingDependencies > 0 ? (
                <li className="muted">+ {remainingDependencies} more in manifest</li>
              ) : null}
            </ul>
          ) : (
            <p>No dependency files reported yet.</p>
          )}
        </div>
        <div>
          <h3>Parameter changes</h3>
          {stepDetail?.overview?.parameterChanges ? (
            <ul>
              {stepDetail.overview.parameterChanges.map(change => (
                <li key={change.path}>
                  <strong>{change.path}</strong>
                  <span> {String(change.from ?? '—')} → {String(change.to ?? '—')}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>Parameter diffing will appear once comparator service lands.</p>
          )}
        </div>
      </section>
    </div>
  );
};

export default OverviewPanel;
