import type { RunStatus } from '../types/runs';
import './RunStatusBadge.css';

interface RunStatusBadgeProps {
  status: RunStatus;
}

const STATUS_LABEL: Record<RunStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  success: 'Success',
  failed: 'Failed',
  interrupted: 'Interrupted',
};

export const RunStatusBadge = ({ status }: RunStatusBadgeProps) => {
  return <span className={`run-status-badge status-${status}`}>{STATUS_LABEL[status]}</span>;
};

export default RunStatusBadge;
