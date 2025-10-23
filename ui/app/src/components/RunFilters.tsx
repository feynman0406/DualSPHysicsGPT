import { ChangeEvent } from 'react';
import type { RunStatus } from '../types/runs';
import './RunFilters.css';

interface RunFiltersProps {
  status: RunStatus | 'all';
  onStatusChange: (status: RunStatus | 'all') => void;
  search: string;
  onSearchChange: (value: string) => void;
}

const STATUS_OPTIONS: Array<{ label: string; value: RunStatus | 'all' }> = [
  { label: 'All statuses', value: 'all' },
  { label: 'Queued', value: 'queued' },
  { label: 'Running', value: 'running' },
  { label: 'Success', value: 'success' },
  { label: 'Failed', value: 'failed' },
  { label: 'Interrupted', value: 'interrupted' },
];

const RunFilters = ({ status, onStatusChange, search, onSearchChange }: RunFiltersProps) => {
  const handleStatusChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onStatusChange(event.target.value as RunStatus | 'all');
  };

  return (
    <div className="run-filters">
      <label className="search-field">
        <span className="visually-hidden">Search runs</span>
        <input
          type="search"
          placeholder="Search by run ID or query"
          value={search}
          onChange={event => onSearchChange(event.target.value)}
        />
      </label>
      <label className="status-select">
        <span className="visually-hidden">Filter by status</span>
        <select value={status} onChange={handleStatusChange}>
          {STATUS_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
};

export default RunFilters;
