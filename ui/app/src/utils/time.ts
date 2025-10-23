import { format, formatDistanceToNow } from 'date-fns';

export const formatUtc = (iso: string | undefined) => {
  if (!iso) {
    return '—';
  }
  try {
    return format(new Date(iso), 'yyyy-MM-dd HH:mm:ss');
  } catch (error) {
    return iso;
  }
};

export const formatRelativeTime = (iso: string | undefined) => {
  if (!iso) {
    return 'unknown';
  }
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch (error) {
    return iso;
  }
};

export const formatDuration = (seconds: number | undefined | null) => {
  if (seconds === undefined || seconds === null) {
    return '—';
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const segments = [
    hours > 0 ? String(hours).padStart(2, '0') : null,
    String(minutes).padStart(2, '0'),
    String(secs).padStart(2, '0'),
  ].filter(Boolean);
  return segments.join(':');
};
