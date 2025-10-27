export const formatFileSize = (bytes: number, precision = 1): string => {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '--';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ['KB', 'MB', 'GB'];
  let size = bytes / 1024;
  for (const unit of units) {
    if (size < 1024 || unit === units[units.length - 1]) {
      return `${size.toFixed(precision)} ${unit}`;
    }
    size /= 1024;
  }
  return `${size.toFixed(precision)} GB`;
};
