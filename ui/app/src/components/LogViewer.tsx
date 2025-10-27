import { useEffect, useMemo, useRef, useState } from 'react';
import type { LogEntry } from '../types/runs';
import './LogViewer.css';

interface LogViewerProps {
  entries: LogEntry[];
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
  availableStreams?: string[];
}

const formatRelative = (seconds?: number) => {
  if (seconds === undefined) {
    return '--';
  }
  return seconds.toFixed(1).padStart(6, ' ');
};

const LogViewer = ({
  entries,
  isLoading,
  error,
  onRetry,
  availableStreams = [],
}: LogViewerProps) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const [search, setSearch] = useState('');
  const [stream, setStream] = useState<string>('all');
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const filteredEntries = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return entries.filter(entry => {
      if (stream !== 'all' && entry.stream !== stream) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      return entry.message.toLowerCase().includes(normalizedSearch);
    });
  }, [entries, stream, search]);

  useEffect(() => {
    if (!autoScroll) {
      return;
    }
    const viewport = viewportRef.current;
    if (viewport) {
      viewport.scrollTop = viewport.scrollHeight;
    }
  }, [filteredEntries, autoScroll]);

  return (
    <div className="log-viewer">
      <div className="log-toolbar">
        <label>
          <span className="visually-hidden">Search logs</span>
          <input
            type="search"
            placeholder="Search logs"
            value={search}
            onChange={event => setSearch(event.target.value)}
            disabled={isLoading}
          />
        </label>
        <label>
          <span className="visually-hidden">Filter stream</span>
          <select value={stream} onChange={event => setStream(event.target.value)}>
            <option value="all">All streams</option>
            {availableStreams.map(name => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={event => setAutoScroll(event.target.checked)}
          />
          <span>Autoscroll</span>
        </label>
        <button type="button" className="ghost" onClick={onRetry} disabled={isLoading}>
          Refresh
        </button>
      </div>

      {error ? (
        <div className="log-error" role="alert">
          <strong>Unable to stream logs.</strong>
          <span> {String((error as Error).message ?? 'Unknown error')}</span>
        </div>
      ) : null}

      <div className="log-viewport" ref={viewportRef} aria-live="polite">
        {isLoading && entries.length === 0 ? (
          <div className="placeholder">Connecting to log stream...</div>
        ) : filteredEntries.length === 0 ? (
          <div className="placeholder">No log entries yet.</div>
        ) : (
          <pre className="log-entries">
            {filteredEntries.map(entry => (
              <div key={entry.sequence} className={`log-entry log-${entry.stream ?? 'stdout'}`}>
                <span className="timestamp">{formatRelative(entry.timestampRelative)}</span>
                <span className="stream">{entry.stream ?? 'stdout'}</span>
                <span className="message">{entry.message}</span>
              </div>
            ))}
          </pre>
        )}
      </div>
    </div>
  );
};

export default LogViewer;
