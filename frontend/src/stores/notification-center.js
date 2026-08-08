import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { acknowledgeEvent, acknowledgeEventCenter, getEventCenter } from '@/api/events'
import { t } from '@/i18n'

const EMPTY_SUMMARY = {
  active_action_count: 0,
  active_download_count: 0,
  warning_event_count: 0,
  error_event_count: 0,
  bell_state: 'idle',
}
const ACTIVITY_BOOST_MS = 15000

export const useNotificationCenterStore = defineStore('notification-center', () => {
  const visible = ref(false)
  const summary = ref({ ...EMPTY_SUMMARY })
  const activeActions = ref([])
  const activeDownloads = ref([])
  const events = ref([])
  const loading = ref(false)
  const markingAllRead = ref(false)
  const lastError = ref('')
  const activityTick = ref(0)
  const activityBoostUntil = ref(0)

  const bellState = computed(() => summary.value?.bell_state || 'idle')
  const centerItems = computed(() => {
    const items = [
      ...events.value.map(event => ({
        id: `event:${event.id}`,
        kind: 'event',
        priority: 0,
        timestamp: event.ts,
        record: event,
      })),
      ...activeDownloads.value.map(download => ({
        id: `download:${download.id}`,
        kind: 'download',
        priority: 1,
        timestamp: download.updated_at || download.created_at,
        record: download,
      })),
      ...activeActions.value.map(action => ({
        id: `action:${action.id}`,
        kind: 'action',
        priority: 2,
        timestamp: action.started_at || action.ts,
        record: action,
      })),
    ]
    return items.sort((left, right) => {
      if (left.priority !== right.priority) return left.priority - right.priority
      return new Date(right.timestamp || 0).getTime() - new Date(left.timestamp || 0).getTime()
    })
  })
  const badgeCount = computed(() => {
    if (bellState.value === 'error') return summary.value.error_event_count || 0
    if (bellState.value === 'warning') return summary.value.warning_event_count || 0
    if (bellState.value === 'running') {
      return (summary.value.active_action_count || 0) + (summary.value.active_download_count || 0)
    }
    return 0
  })
  const hasActiveSignal = computed(() => bellState.value === 'error' || bellState.value === 'warning' || bellState.value === 'running')
  const pollFast = computed(() => hasActiveSignal.value || Date.now() < activityBoostUntil.value)

  function open() {
    visible.value = true
  }

  function close() {
    visible.value = false
  }

  function setVisible(value) {
    visible.value = !!value
  }

  async function refreshCenter() {
    loading.value = true
    try {
      const data = await getEventCenter()
      summary.value = data?.summary || { ...EMPTY_SUMMARY }
      activeActions.value = data?.active_actions || []
      activeDownloads.value = data?.active_downloads || []
      events.value = data?.events || []
      if (summary.value.bell_state === 'idle') {
        activityBoostUntil.value = 0
      }
      lastError.value = ''
    } catch (error) {
      lastError.value = error?.message || t('notificationCenter.loadFailed')
    } finally {
      loading.value = false
    }
  }

  async function markEventRead(eventId) {
    if (!eventId) return
    await acknowledgeEvent(eventId)
    await refreshCenter()
  }

  async function markAllRead() {
    markingAllRead.value = true
    try {
      await acknowledgeEventCenter()
      await refreshCenter()
    } finally {
      markingAllRead.value = false
    }
  }

  function notifyActivity() {
    activityTick.value += 1
    activityBoostUntil.value = Date.now() + ACTIVITY_BOOST_MS
    void refreshCenter()
  }

  return {
    visible,
    summary,
    activeActions,
    activeDownloads,
    events,
    centerItems,
    loading,
    markingAllRead,
    lastError,
    bellState,
    badgeCount,
    hasActiveSignal,
    activityTick,
    activityBoostUntil,
    pollFast,
    open,
    close,
    setVisible,
    refreshCenter,
    markEventRead,
    markAllRead,
    notifyActivity,
  }
})
