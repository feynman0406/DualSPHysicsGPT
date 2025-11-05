import { useEffect, useMemo } from 'react';
import clsx from 'clsx';
import type { DependencyManifest, DependencyFile } from '../types/runs';
import './DependencyList.css';

interface DependencyListProps {
  runId: string;
  manifest?: DependencyManifest;
  summaryCount?: number;
  summaryWarnings?: number;
  buildDownloadUrl: (runId: string, relativePath: string) => string;
}

const normalizeNotes = (value: DependencyFile['notes']): string[] | undefined => {
  if (!value) {
    return undefined;
  }
  return value.map(entry => String(entry));
};

const DependencyList = ({
  runId,
  manifest,
  summaryCount,
  summaryWarnings,
  buildDownloadUrl,
}: DependencyListProps) => {
  const files = manifest?.files ?? [];
  const warnings = manifest?.warnings ?? [];

  const { validFiles, invalidEntries } = useMemo(() => {
    const collected: DependencyFile[] = [];
    let invalid = 0;
    for (const file of files) {
      if (!file || typeof file.path !== 'string') {
        invalid += 1;
        continue;
      }
      const normalizedNotes = normalizeNotes(file.notes);
      collected.push({ ...file, notes: normalizedNotes } as DependencyFile);
    }
    return { validFiles: collected, invalidEntries: invalid };
  }, [files]);

  useEffect(() => {
    if (summaryCount !== undefined && summaryCount !== validFiles.length) {
      console.warn('[deps] Dependency count mismatch', {
        runId,
        summaryCount,
        manifestCount: validFiles.length,
      });
    }
  }, [summaryCount, validFiles.length, runId]);

  useEffect(() => {
    if (summaryWarnings !== undefined && summaryWarnings !== warnings.length) {
      console.warn('[deps] Dependency warning mismatch', {
        runId,
        summaryWarnings,
        manifestWarnings: warnings.length,
      });
    }
  }, [summaryWarnings, warnings.length, runId]);

  useEffect(() => {
    if (invalidEntries > 0) {
      console.warn('[deps] Skipped malformed dependency entries', { runId, invalidEntries });
    }
  }, [invalidEntries, runId]);

  if (validFiles.length === 0 && warnings.length === 0) {
    return (
      <section className="dependency-panel">
        <h3>Dependencies</h3>
        <p className="placeholder">No dependency manifest available for this run.</p>
      </section>
    );
  }

  return (
    <section className="dependency-panel">
      <header className="dependency-header">
        <h3>Dependency Manifest</h3>
        <span className="dependency-count">
          {validFiles.length} file{validFiles.length === 1 ? '' : 's'}
        </span>
      </header>

      {warnings.length > 0 && (
        <div className="dependency-warnings">
          <h4>Warnings ({warnings.length})</h4>
          <ul>
            {warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {validFiles.length > 0 && (
        <div className="dependency-table-wrapper">
          <table className="dependency-table">
            <thead>
              <tr>
                <th scope="col">Path</th>
                <th scope="col">Purpose</th>
                <th scope="col">Source</th>
                <th scope="col">Status</th>
                <th scope="col">Notes</th>
                <th scope="col" aria-label="Download" />
              </tr>
            </thead>
            <tbody>
              {validFiles.map(file => {
                const downloadUrl = file.copiedPath ? buildDownloadUrl(runId, file.copiedPath) : undefined;
                const downloadName = file.path ? file.path.split(/[\/]/).pop() : undefined;
                const notes = file.notes;
                return (
                  <tr key={file.path}>
                    <td data-label="Path">
                      <code>{file.path}</code>
                    </td>
                    <td data-label="Purpose">{file.purpose ?? '—'}</td>
                    <td data-label="Source">{file.source ?? '—'}</td>
                    <td data-label="Status">
                      {file.status ? (
                        <span className={clsx('status-chip', `status-${file.status}`)}>{file.status}</span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td data-label="Notes">
                      {notes && notes.length > 0 ? (
                        <ul>
                          {notes.map((note, index) => (
                            <li key={`${file.path}-note-${index}`}>{note}</li>
                          ))}
                        </ul>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td data-label="Download" className="download-cell">
                      {downloadUrl ? (
                        <a href={downloadUrl} className="ghost compact" download={downloadName || undefined}>
                          Download
                        </a>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

export default DependencyList;


