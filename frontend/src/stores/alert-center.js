import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { acknowledgeAlert as acknowledgeAlertApi, getAlertCenter } from '@/api/alerts'
import { t } from '@/i18n'

const EMPTY_SUMMARY = {
  active_count: 0,
  active_action_count: 0,
  unacknowledged_error_count: 0,
  unacknowledged_warning_count: 0,
  bell_state: 'idle',
}
const ACTIVITY_BOOST_MS = 15000

export const useAlertCenterStore = defineStore('alert-center', () => {
  const visible = ref(false)
  const summary = ref({ ...EMPTY_SUMMARY })
  const activeActions = ref([])
  const alerts = ref([])
  const loading = ref(false)
  const lastError = ref('')
  const activityTick = ref(0)
  const activityBoostUntil = ref(0)

  const bellState = computed(() => summary.value?.bell_state || 'idle')
  const centerItems = computed(() => {
    const items = [
      ...alerts.value.map(alert => ({
        id: `alert:${alert.id}`,
        kind: 'alert',
        priority: 0,
        timestamp: alert.last_seen_at || alert.updated_at || alert.created_at,
        record: alert,
      })),
      ...activeActions.value.map(action => ({
        id: `action:${action.id}`,
        kind: 'action',
        priority: 1,
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
    if (bellState.value === 'error') return summary.value.unacknowledged_error_count || 0
    if (bellState.value === 'running') return summary.value.active_action_count || 0
    return 0
  })
  const hasActiveSignal = computed(() => bellState.value === 'error' || bellState.value === 'running')
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
      const data = await getAlertCenter()
      summary.value = data?.summary || { ...EMPTY_SUMMARY }
      activeActions.value = data?.active_actions || []
      alerts.value = data?.alerts || []
      if (summary.value.bell_state === 'idle') {
        activityBoostUntil.value = 0
      }
      lastError.value = ''
    } catch (error) {
      lastError.value = error?.message || t('alertCenter.loadFailed')
    } finally {
      loading.value = false
    }
  }

  function notifyActivity() {
    activityTick.value += 1
    activityBoostUntil.value = Date.now() + ACTIVITY_BOOST_MS
    void refreshCenter()
  }

  async function acknowledge(alertId) {
    if (!alertId) return null
    const alert = await acknowledgeAlertApi(alertId)
    alerts.value = alerts.value.filter(item => item.id !== alertId)
    await refreshCenter()
    return alert
  }

  return {
    visible,
    summary,
    activeActions,
    alerts,
    centerItems,
    loading,
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
    notifyActivity,
    acknowledge,
  }
})
