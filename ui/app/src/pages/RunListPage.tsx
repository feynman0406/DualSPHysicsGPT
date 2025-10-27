import { useMemo, useState } from 'react';
import clsx from 'clsx';
import { useCreateRun, useRuns } from '../hooks/useRuns';
import type { RunStatus } from '../types/runs';
import RunFilters from '../components/RunFilters';
import RunCard from '../components/RunCard';
import RunStatusBadge from '../components/RunStatusBadge';
import NewRunDialog, { NewRunFormValues } from '../components/NewRunDialog';
import './RunListPage.css';

const RunListPage = () => {
  const [status, setStatus] = useState<RunStatus | 'all'>('all');
  const [search, setSearch] = useState('');
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);

  const { data: runs = [], isLoading, isFetching, error, refetch } = useRuns();
  const createRun = useCreateRun();

  const filteredRuns = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return runs
      .filter(run => (status === 'all' ? true : run.status === status))
      .filter(run => {
        if (!normalizedSearch) {
          return true;
        }
        return (
          run.runId.toLowerCase().includes(normalizedSearch) ||
          run.query.toLowerCase().includes(normalizedSearch)
        );
      })
      .sort((a, b) => {
        const dateA = a.startedAt ? Date.parse(a.startedAt) : 0;
        const dateB = b.startedAt ? Date.parse(b.startedAt) : 0;
        return dateB - dateA;
      });
  }, [runs, status, search]);

  const activeRuns = useMemo(
    () => runs.filter(run => run.status === 'running' || run.status === 'queued'),
    [runs],
  );

  const handleCreateRun = async (values: NewRunFormValues) => {
    setDialogError(null);
    try {
      await createRun.mutateAsync(values);
      setDialogOpen(false);
    } catch (err) {
      setDialogError(String((err as Error).message ?? 'Unable to trigger run'));
    }
  };

  return (
    <section className="run-list-page">
      <header className="page-header">
        <div>
          <h1>Runs</h1>
          <p>Monitor DualSPHysics executions, rerun scenarios, and inspect outputs.</p>
        </div>
        <div className="page-actions">
          <button type="button" className="primary" onClick={() => setDialogOpen(true)}>
            New run
          </button>
          <button
            type="button"
            className={clsx('ghost', { spinning: isFetching })}
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </header>

      <div className="list-toolbar">
        <RunFilters
          status={status}
          onStatusChange={setStatus}
          search={search}
          onSearchChange={setSearch}
        />
        {activeRuns.length > 0 && (
          <div className="polling-indicator" role="status">
            Tracking {activeRuns.length} active run{activeRuns.length > 1 ? 's' : ''}...
          </div>
        )}
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <strong>Unable to load runs.</strong>
          <span> {String((error as Error).message ?? 'Unknown error')}.</span>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="run-grid" aria-busy="true">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="run-card skeleton" key={index} />
          ))}
        </div>
      ) : filteredRuns.length > 0 ? (
        <div className="run-grid">
          {filteredRuns.map(run => (
            <RunCard run={run} key={run.runId} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <h2>No runs match the current filters</h2>
          <p>Adjust your filters or trigger a new run to see results here.</p>
        </div>
      )}

      <section className="status-legend" aria-label="Run status legend">
        <RunStatusBadge status="queued" />
        <RunStatusBadge status="running" />
        <RunStatusBadge status="success" />
        <RunStatusBadge status="failed" />
        <RunStatusBadge status="interrupted" />
      </section>

      <NewRunDialog
        open={isDialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setDialogError(null);
        }}
        onSubmit={handleCreateRun}
        busy={createRun.isPending}
        errorMessage={dialogError}
      />
    </section>
  );
};

export default RunListPage;
