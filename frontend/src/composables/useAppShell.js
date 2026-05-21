import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useAlertCenterStore } from '@/stores/alert-center'
import { useI18n } from 'vue-i18n'

const ACTIVE_OPERATIONS_POLL_MS = 5000
const IDLE_OPERATIONS_POLL_MS = 30000

export function useAppShell() {
  const router = useRouter()
  const route = useRoute()
  const authStore = useAuthStore()
  const themeStore = useThemeStore()
  const alertCenterStore = useAlertCenterStore()
  const { t } = useI18n()
  const { activityTick, badgeCount, bellState, pollFast, summary } = storeToRefs(alertCenterStore)

  const headerSearchQuery = ref('')
  const displayAlertCount = computed(() => badgeCount.value)
  const alertCountButtonClass = computed(() => {
    const label = displayAlertCount.value > 99 ? '99+' : String(displayAlertCount.value)
    return label.length === 1 ? 'ui-task-count-button-single' : 'ui-task-count-button-multi'
  })
  const alertButtonPt = computed(() => ({
    root: {
      class: [
        'ui-alert-button shrink-0',
        alertCountButtonClass.value,
        bellState.value === 'error' ? 'ui-alert-button-error' : '',
        bellState.value === 'running' ? 'ui-alert-button-running' : '',
      ],
    },
    icon: {
      class: 'text-title',
    },
    label: {
      class: 'leading-none',
    },
  }))
  const alertCenterTooltip = computed(() => {
    if (bellState.value === 'error') {
      return t('alertCenter.tooltipError', { count: summary.value.unacknowledged_error_count || 0 })
    }
    if (bellState.value === 'running') {
      return t('alertCenter.tooltipRunning', { count: summary.value.active_action_count || 0 })
    }
    return t('alertCenter.tooltipIdle')
  })

  const isAuthPage = computed(() => route.path === '/login' || route.path === '/setup')
  const isHomePage = computed(() => route.path === '/discover')
  const shouldPollAlertCenter = computed(() => authStore.isAuthenticated && !isAuthPage.value)
  const mainClass = computed(() => {
    if (isAuthPage.value) return 'flex-1 w-full flex justify-center'
    return 'flex-1 w-full max-w-layout mx-auto px-container py-page'
  })
  const mainStyle = computed(() => {
    if (isAuthPage.value) {
      return {
        paddingTop: 'calc(var(--size-header-height) + var(--spacing-page))',
        paddingBottom: 'var(--spacing-page)',
        minHeight: 'calc(100dvh - var(--size-header-height) - var(--size-footer-height))',
      }
    }
    return {
      paddingTop: 'calc(var(--size-header-height) + var(--spacing-page))',
    }
  })

  let alertPollTimer = null
  let alertPollInFlight = false

  function handleHeaderSearch(value) {
    const query = String(value || '').trim()
    if (!query) return

    headerSearchQuery.value = ''
    router.push({
      name: 'DiscoverPage',
      query: { query },
    })
  }

  function stopAlertPolling() {
    if (!alertPollTimer) return
    window.clearTimeout(alertPollTimer)
    alertPollTimer = null
  }

  function nextAlertPollDelay() {
    return pollFast.value ? ACTIVE_OPERATIONS_POLL_MS : IDLE_OPERATIONS_POLL_MS
  }

  function scheduleAlertPolling() {
    stopAlertPolling()
    if (!shouldPollAlertCenter.value || document.hidden) return
    alertPollTimer = window.setTimeout(() => {
      void refreshAlertCenterPoll()
    }, nextAlertPollDelay())
  }

  async function refreshAlertCenterPoll() {
    if (alertPollInFlight || !shouldPollAlertCenter.value || document.hidden) return
    alertPollInFlight = true
    try {
      await alertCenterStore.refreshCenter()
    } finally {
      alertPollInFlight = false
      scheduleAlertPolling()
    }
  }

  function startAlertPolling() {
    if (alertPollTimer || alertPollInFlight || !shouldPollAlertCenter.value || document.hidden) return
    void refreshAlertCenterPoll()
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      stopAlertPolling()
      return
    }
    startAlertPolling()
  }

  onMounted(() => {
    themeStore.init()
    document.addEventListener('visibilitychange', handleVisibilityChange)
    startAlertPolling()
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    stopAlertPolling()
  })

  watch(shouldPollAlertCenter, (enabled) => {
    if (enabled) {
      startAlertPolling()
      return
    }
    stopAlertPolling()
  }, { immediate: true })

  watch(activityTick, () => {
    if (!shouldPollAlertCenter.value || document.hidden) return
    stopAlertPolling()
    void refreshAlertCenterPoll()
  })

  return {
    route,
    headerSearchQuery,
    displayAlertCount,
    alertButtonPt,
    alertCenterTooltip,
    isAuthPage,
    isHomePage,
    mainClass,
    mainStyle,
    alertCenterStore,
    handleHeaderSearch,
  }
}
