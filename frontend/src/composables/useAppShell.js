import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useNotificationCenterStore } from '@/stores/notification-center'
import { useI18n } from 'vue-i18n'

const ACTIVE_OPERATIONS_POLL_MS = 5000
const IDLE_OPERATIONS_POLL_MS = 30000

export function useAppShell() {
  const router = useRouter()
  const route = useRoute()
  const authStore = useAuthStore()
  const themeStore = useThemeStore()
  const notificationCenterStore = useNotificationCenterStore()
  const { t } = useI18n()
  const { activityTick, badgeCount, bellState, pollFast, summary } = storeToRefs(notificationCenterStore)

  const headerSearchQuery = ref('')
  const displayNotificationCount = computed(() => badgeCount.value)
  const notificationCountButtonClass = computed(() => {
    const label = displayNotificationCount.value > 99 ? '99+' : String(displayNotificationCount.value)
    return label.length === 1 ? 'ui-task-count-button-single' : 'ui-task-count-button-multi'
  })
  const notificationButtonPt = computed(() => ({
    root: {
      class: [
        'ui-notification-button shrink-0',
        notificationCountButtonClass.value,
        bellState.value === 'error' ? 'ui-notification-button-error' : '',
        bellState.value === 'warning' ? 'ui-notification-button-error' : '',
        bellState.value === 'running' ? 'ui-notification-button-running' : '',
      ],
    },
    icon: {
      class: 'text-title',
    },
    label: {
      class: 'leading-none',
    },
  }))
  const notificationCenterTooltip = computed(() => {
    if (bellState.value === 'error') {
      return t('notificationCenter.tooltipError', { count: summary.value.error_event_count || 0 })
    }
    if (bellState.value === 'warning') {
      return t('notificationCenter.tooltipWarning', { count: summary.value.warning_event_count || 0 })
    }
    if (bellState.value === 'running') {
      const count = (summary.value.active_action_count || 0) + (summary.value.active_download_count || 0)
      return t('notificationCenter.tooltipRunning', { count })
    }
    return t('notificationCenter.tooltipIdle')
  })

  const isAuthPage = computed(() => route.path === '/login' || route.path === '/setup')
  const isHomePage = computed(() => route.path === '/discover')
  const shouldPollNotificationCenter = computed(() => authStore.isAuthenticated && !isAuthPage.value)
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

  let notificationPollTimer = null
  let notificationPollInFlight = false

  function handleHeaderSearch(value) {
    const query = String(value || '').trim()
    if (!query) return

    headerSearchQuery.value = ''
    router.push({
      name: 'DiscoverPage',
      query: { query },
    })
  }

  function stopNotificationPolling() {
    if (!notificationPollTimer) return
    window.clearTimeout(notificationPollTimer)
    notificationPollTimer = null
  }

  function nextNotificationPollDelay() {
    return pollFast.value ? ACTIVE_OPERATIONS_POLL_MS : IDLE_OPERATIONS_POLL_MS
  }

  function scheduleNotificationPolling() {
    stopNotificationPolling()
    if (!shouldPollNotificationCenter.value || document.hidden) return
    notificationPollTimer = window.setTimeout(() => {
      void refreshNotificationCenterPoll()
    }, nextNotificationPollDelay())
  }

  async function refreshNotificationCenterPoll() {
    if (notificationPollInFlight || !shouldPollNotificationCenter.value || document.hidden) return
    notificationPollInFlight = true
    try {
      await notificationCenterStore.refreshCenter()
    } finally {
      notificationPollInFlight = false
      scheduleNotificationPolling()
    }
  }

  function startNotificationPolling() {
    if (notificationPollTimer || notificationPollInFlight || !shouldPollNotificationCenter.value || document.hidden) return
    void refreshNotificationCenterPoll()
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      stopNotificationPolling()
      return
    }
    startNotificationPolling()
  }

  onMounted(() => {
    themeStore.init()
    document.addEventListener('visibilitychange', handleVisibilityChange)
    startNotificationPolling()
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    stopNotificationPolling()
  })

  watch(shouldPollNotificationCenter, (enabled) => {
    if (enabled) {
      startNotificationPolling()
      return
    }
    stopNotificationPolling()
  }, { immediate: true })

  watch(activityTick, () => {
    if (!shouldPollNotificationCenter.value || document.hidden) return
    stopNotificationPolling()
    void refreshNotificationCenterPoll()
  })

  return {
    route,
    headerSearchQuery,
    displayNotificationCount,
    notificationButtonPt,
    notificationCenterTooltip,
    isAuthPage,
    isHomePage,
    mainClass,
    mainStyle,
    notificationCenterStore,
    handleHeaderSearch,
  }
}
