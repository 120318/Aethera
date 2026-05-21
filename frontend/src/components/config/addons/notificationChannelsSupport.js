export function createNotificationChannelId() {
  return globalThis.crypto?.randomUUID?.() || `notification-channel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function createEmptyNotificationChannel() {
  return {
    id: createNotificationChannelId(),
    type: 'telegram',
    name: '',
    enabled: true,
    event_patterns: ['subscription.*', 'follow.*', 'media.*', 'download.*'],
    levels: [],
    bot_token: '',
    chat_id: '',
  }
}

export function assignNotificationChannelForm(form, channel, eventPatternsInput) {
  form.id = channel.id
  form.type = channel.type || 'telegram'
  form.name = channel.name || ''
  form.enabled = channel.enabled !== false
  form.event_patterns = Array.isArray(channel.event_patterns) ? [...channel.event_patterns] : ['subscription.*', 'follow.*', 'media.*', 'download.*']
  form.levels = Array.isArray(channel.levels) ? [...channel.levels] : []
  form.bot_token = channel.bot_token || ''
  form.chat_id = channel.chat_id || ''
  eventPatternsInput.value = form.event_patterns.join(', ')
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

export function normalizeCommaSeparatedItems(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function formatNotificationItems(value, fallback = '') {
  return (value || []).join(', ') || fallback
}
