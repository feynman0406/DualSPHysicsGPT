import type { RunSummary, StepDetailPayload } from '../types/runs';
import './OverviewPanel.css';

interface OverviewPanelProps {
  run: RunSummary;
  stepDetail?: StepDetailPayload;
}

const OverviewPanel = ({ run, stepDetail }: OverviewPanelProps) => {
  return (
    <div className="overview-panel">
      <section className="overview-cards">
        <div>
          <h3>Primary Output</h3>
          <p>{run.summary?.primaryOutput ?? 'Pending'}</p>
        </div>
        <div>
          <h3>Artifacts</h3>
          <p>{run.summary?.artifactCount ?? '"'}</p>
        </div>
        <div>
          <h3>Exit Code</h3>
          <p>{run.exitCode ?? '"'}</p>
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
                    <span>  |  Score {(reference.score * 100).toFixed(1)}%</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p>Reference summary pending backend instrumentation.</p>
          )}
        </div>
        <div>
          <h3>Parameter changes</h3>
          {stepDetail?.overview?.parameterChanges ? (
            <ul>
              {stepDetail.overview.parameterChanges.map(change => (
                <li key={change.path}>
                  <strong>{change.path}</strong>
                  <span>
                    {' '}
                    {String(change.from ?? '"')} -' {String(change.to ?? '"')}
                  </span>
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
