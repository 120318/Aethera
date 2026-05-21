import { i18n, t } from '@/i18n'

function toDate(value) {
  if (value === null || value === undefined || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;

  if (typeof value === 'number') {
    const timestamp = value < 1e12 ? value * 1000 : value;
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatAbsoluteDateTime(value) {
  const date = toDate(value);
  if (!date) return '-';

  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

export function formatRelativeTime(value) {
  const date = toDate(value);
  if (!date) return '-';

  const diffSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSeconds < 60) return t('formatters.relative.justNow');

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return t('formatters.relative.minutesAgo', { count: diffMinutes });

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return t('formatters.relative.hoursAgo', { count: diffHours });

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return t('formatters.relative.daysAgo', { count: diffDays });

  return formatAbsoluteDateTime(date);
}

export function formatTimestamp(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate()
  ).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

export function formatSizeBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

export function formatSpeed(bytes) {
  if (!bytes || bytes === 0) return '0 B/s';
  const k = 1024;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

export function formatSize(bytes) {
  if (!bytes) return '-';
  const k = 1024;
  if (bytes < k) return `${bytes} B`;
  if (bytes < k * k) return `${(bytes / k).toFixed(2)} KB`;
  if (bytes < k * k * k) return `${(bytes / (k * k)).toFixed(2)} MB`;
  return `${(bytes / (k * k * k)).toFixed(2)} GB`;
}

export function formatETA(seconds) {
  if (!seconds || seconds < 0 || seconds === 8640000) return '-';
  if (seconds < 60) return t('formatters.duration.seconds', { count: seconds });
  if (seconds < 3600) return t('formatters.duration.minutes', { count: Math.floor(seconds / 60) });
  if (seconds < 86400) return t('formatters.duration.hours', { count: Math.floor(seconds / 3600) });
  if (seconds < 2592000) return t('formatters.duration.days', { count: Math.floor(seconds / 86400) });
  return t('formatters.duration.months', { count: Math.floor(seconds / 2592000) });
}

function formatDurationUnitValue(value) {
  if (!Number.isFinite(value)) return 0;
  if (value >= 10) return Math.round(value);
  return Number(value.toFixed(1)).toString();
}

export function formatDurationMs(durationMs, fallback = '') {
  if (durationMs == null) return fallback;
  const milliseconds = Math.max(0, Number(durationMs));
  if (!Number.isFinite(milliseconds)) return fallback;
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;

  const seconds = milliseconds / 1000;
  if (seconds < 60) return t('formatters.duration.seconds', { count: formatDurationUnitValue(seconds) });
  if (seconds < 3600) return t('formatters.duration.minutes', { count: formatDurationUnitValue(seconds / 60) });
  if (seconds < 86400) return t('formatters.duration.hours', { count: formatDurationUnitValue(seconds / 3600) });
  if (seconds < 2592000) return t('formatters.duration.days', { count: formatDurationUnitValue(seconds / 86400) });
  return t('formatters.duration.months', { count: formatDurationUnitValue(seconds / 2592000) });
}

export function formatCount(n) {
  if (!n) return '';
  if (n >= 10000) {
    return new Intl.NumberFormat(i18n.global.locale.value, {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(n);
  }
  return String(n);
}

export function formatEpisodeRange(episodes) {
  if (!episodes || !episodes.length) return '';
  const sorted = [...episodes].sort((a, b) => a - b);
  const ranges = [];
  let start = sorted[0];
  let end = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === end + 1) {
      end = sorted[i];
    } else {
      ranges.push(start === end ? `${start}` : `${start}-${end}`);
      start = end = sorted[i];
    }
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`);
  return ranges.join(',');
}

export function formatState(state) {
  const stateMap = {
    downloading: 'formatters.state.downloading',
    seeding: 'formatters.state.seeding',
    paused: 'formatters.state.paused',
    queued: 'formatters.state.queued',
    checking: 'formatters.state.checking',
    missing: 'formatters.state.missing',
    error: 'formatters.state.error',
    active: 'formatters.state.seeding',
    downloaded: 'formatters.state.downloaded',
    transferred: 'formatters.state.transferred',
    torrent_removed: 'formatters.state.torrentRemoved',
    available: 'formatters.state.available',
    failed: 'formatters.state.failed',
    unknown: 'common.unknown'
  };
  const labelKey = stateMap[state];
  return labelKey ? t(labelKey) : state || t('common.unknown');
}
