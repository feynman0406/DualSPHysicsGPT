import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ArtifactMetadata } from '../types/runs';
import './ArtifactViewer.css';

interface ArtifactViewerProps {
  artifacts: ArtifactMetadata[];
  isLoading: boolean;
  error?: unknown;
  onRefresh?: () => void;
  loadContent: (artifact: ArtifactMetadata) => Promise<string>;
}

type CopyState = 'idle' | 'success' | 'error';

const COPY_RESET_DELAY_MS = 2000;

const humanFileSize = (size?: number) => {
  if (!size || size <= 0) {
    return 'unknown';
  }
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
  const value = size / Math.pow(1024, index);
  return `${value.toFixed(1)} ${units[index]}`;
};

const fallbackCopyText = (value: string) => {
  if (typeof document === 'undefined') {
    throw new Error('Clipboard API unavailable in this environment.');
  }
  const body = document.body;
  if (!body) {
    throw new Error('Document body unavailable for clipboard copy.');
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.top = '-1000px';
  textarea.style.left = '-1000px';
  textarea.style.opacity = '0';
  textarea.style.pointerEvents = 'none';
  body.appendChild(textarea);

  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  let succeeded = false;
  try {
    succeeded = typeof document.execCommand === 'function' && document.execCommand('copy');
  } finally {
    body.removeChild(textarea);
  }

  if (!succeeded) {
    throw new Error('Copy command was rejected.');
  }
};

const ArtifactViewer = ({
  artifacts,
  isLoading,
  error,
  onRefresh,
  loadContent,
}: ArtifactViewerProps) => {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>('');
  const [isPreviewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<CopyState>('idle');

  const sortedArtifacts = useMemo(() => {
    return [...artifacts].sort((a, b) => a.path.localeCompare(b.path));
  }, [artifacts]);

  useEffect(() => {
    if (!selectedPath && sortedArtifacts.length > 0) {
      setSelectedPath(sortedArtifacts[0].path);
    }
  }, [sortedArtifacts, selectedPath]);

  useEffect(() => {
    const artifact = sortedArtifacts.find(item => item.path === selectedPath);
    if (!artifact) {
      setPreview('');
      return;
    }

    let cancelled = false;
    const load = async () => {
      try {
        setPreviewLoading(true);
        setPreviewError(null);
        const content = await loadContent(artifact);
        if (!cancelled) {
          setPreview(content);
        }
      } catch (err) {
        if (!cancelled) {
          setPreviewError(String((err as Error).message ?? 'Unable to preview artifact'));
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      }
    };

    if (artifact.previewAvailable !== false) {
      void load();
    } else {
      setPreview('Preview not available for this artifact type.');
    }

    return () => {
      cancelled = true;
    };
  }, [selectedPath, sortedArtifacts, loadContent]);

  useEffect(() => {
    setCopyStatus('idle');
  }, [selectedPath]);

  useEffect(() => {
    if (isPreviewLoading) {
      setCopyStatus('idle');
    }
  }, [isPreviewLoading]);

  useEffect(() => {
    setCopyStatus('idle');
  }, [preview]);

  useEffect(() => {
    if (copyStatus === 'idle') {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setCopyStatus('idle');
    }, COPY_RESET_DELAY_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [copyStatus]);

  const handleCopy = useCallback(async () => {
    if (!preview) {
      return;
    }

    const textToCopy = preview;
    const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;

    if (clipboard?.writeText) {
      try {
        await clipboard.writeText(textToCopy);
        setCopyStatus('success');
        return;
      } catch {
        // Fall through to the execCommand fallback.
      }
    }

    try {
      fallbackCopyText(textToCopy);
      setCopyStatus('success');
    } catch {
      setCopyStatus('error');
    }
  }, [preview]);

  const selectedArtifact = sortedArtifacts.find(item => item.path === selectedPath) ?? null;
  const canCopyPreview = Boolean(
    selectedArtifact &&
      !isPreviewLoading &&
      !previewError &&
      preview &&
      selectedArtifact.previewAvailable !== false,
  );
  const hasPreviewActions = canCopyPreview || Boolean(selectedArtifact?.downloadUrl);
  const copyButtonLabel =
    copyStatus === 'success' ? 'Copied!' : copyStatus === 'error' ? 'Copy failed' : 'Copy preview';

  return (
    <div className="artifact-viewer">
      <aside className="artifact-list" aria-label="Artifact list">
        <header className="artifact-toolbar">
          <h3>Artifacts ({sortedArtifacts.length})</h3>
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Refresh
          </button>
        </header>
        {isLoading && sortedArtifacts.length === 0 ? (
          <p className="placeholder">Loading artifacts�K</p>
        ) : error ? (
          <div className="error" role="alert">
            <strong>Unable to load artifacts.</strong>
            <div>{String((error as Error).message ?? 'Unknown error')}</div>
          </div>
        ) : sortedArtifacts.length === 0 ? (
          <p className="placeholder">No artifacts found for this run.</p>
        ) : (
          <ul>
            {sortedArtifacts.map(artifact => (
              <li key={artifact.path}>
                <button
                  type="button"
                  className={artifact.path === selectedPath ? 'selected' : undefined}
                  onClick={() => setSelectedPath(artifact.path)}
                >
                  <span className="artifact-name">{artifact.label ?? artifact.path}</span>
                  <span className="artifact-meta">{humanFileSize(artifact.sizeBytes)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <section className="artifact-preview" aria-live="polite">
        {selectedArtifact ? (
          <header className="preview-header">
            <div>
              <h3>{selectedArtifact.label ?? selectedArtifact.path}</h3>
              <p>
                {selectedArtifact.path} �P {humanFileSize(selectedArtifact.sizeBytes)}
              </p>
            </div>
            {hasPreviewActions ? (
              <div className="preview-actions">
                {canCopyPreview ? (
                  <button
                    type="button"
                    className="ghost compact"
                    onClick={handleCopy}
                    aria-label="Copy artifact preview"
                  >
                    <span aria-live="polite" aria-atomic="true">
                      {copyButtonLabel}
                    </span>
                  </button>
                ) : null}
                {selectedArtifact.downloadUrl ? (
                  <a
                    className="ghost compact"
                    href={selectedArtifact.downloadUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download
                  </a>
                ) : null}
              </div>
            ) : null}
          </header>
        ) : null}
        <div className="preview-body">
          {isPreviewLoading ? (
            <p className="placeholder">Loading preview�K</p>
          ) : previewError ? (
            <div className="error" role="alert">
              {previewError}
            </div>
          ) : preview ? (
            <pre>{preview}</pre>
          ) : (
            <p className="placeholder">Select an artifact to preview its contents.</p>
          )}
        </div>
      </section>
    </div>
  );
};

export default ArtifactViewer;


