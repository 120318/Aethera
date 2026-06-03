export const DEFAULT_NOTIFICATION_EVENT_PATTERNS = [
  'download.completed',
  'download.failed',
  'download.task.downloader_change_failed',
  'download.task.storage_change_failed',
  'media.import.completed',
  'media.import.failed',
  'library.file.missing',
  'follow.*',
  'subscription.ended.*',
  'media_server_sync.failed',
  'danmu.generate.failed',
]

export function createNotificationChannelId() {
  return globalThis.crypto?.randomUUID?.() || `notification-channel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function createEmptyNotificationChannel() {
  return {
    id: createNotificationChannelId(),
    type: 'telegram',
    name: '',
    enabled: true,
    event_patterns: [...DEFAULT_NOTIFICATION_EVENT_PATTERNS],
    levels: [],
    bot_token: '',
    chat_id: '',
  }
}

export function assignNotificationChannelForm(form, channel) {
  form.id = channel.id
  form.type = channel.type || 'telegram'
  form.name = channel.name || ''
  form.enabled = channel.enabled !== false
  form.event_patterns = Array.isArray(channel.event_patterns) && channel.event_patterns.length
    ? [...channel.event_patterns]
    : [...DEFAULT_NOTIFICATION_EVENT_PATTERNS]
  form.levels = Array.isArray(channel.levels) ? [...channel.levels] : []
  form.bot_token = channel.bot_token || ''
  form.chat_id = channel.chat_id || ''
}

export function cloneNotificationChannel(channel) {
  return {
    ...channel,
    event_patterns: [...(channel.event_patterns || [])],
    levels: [...(channel.levels || [])],
  }
}

export function cloneNotificationChannels(channels) {
  return channels.map((channel) => cloneNotificationChannel(channel))
}

export function formatNotificationItems(value, fallback = '') {
  return (value || []).join(', ') || fallback
}
