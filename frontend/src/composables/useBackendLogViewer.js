import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { getBackendLogs } from '@/api/logs'
import { t } from '@/i18n'

const INITIAL_LIMIT = 200
const INCREMENTAL_LIMIT = 200
const MAX_LINES = 1000
const POLL_INTERVAL_MS = 3000
const LOG_LEVEL_PATTERN = /\s\|\s(TRACE|DEBUG|INFO|WARNING|ERROR|CRITICAL)\s\|/
const LOG_LEVEL_RANK = {
  trace: 5,
  debug: 10,
  info: 20,
  warning: 30,
  error: 40,
  critical: 50,
}

function extractLogLevel(line) {
  const match = line.match(LOG_LEVEL_PATTERN)
  return match ? match[1].toLowerCase() : ''
}

export function useBackendLogViewer(isActive) {
  const lines = ref([])
  const keyword = ref('')
  const selectedLevel = ref('warning')
  const initialLoading = ref(false)
  const manualRefreshing = ref(false)
  const initialized = ref(false)
  const autoRefreshEnabled = ref(true)
  const lastRefreshedAt = ref(null)
  const sourceFile = ref('')
  const loadError = ref('')

  const cursor = ref(null)

  let pollTimer = null
  let pollInFlight = false

  const filteredLines = computed(() => {
    const needle = keyword.value.trim().toLowerCase()
    const level = selectedLevel.value
    const minRank = level ? (LOG_LEVEL_RANK[level] || 0) : 0

    return lines.value.filter((line) => {
      if (minRank > 0) {
        const lineLevel = extractLogLevel(line)
        const lineRank = LOG_LEVEL_RANK[lineLevel] || 0
        if (lineRank < minRank) {
          return false
        }
      }
      if (!needle) {
        return true
      }
      return line.toLowerCase().includes(needle)
    })
  })

  const lineCount = computed(() => lines.value.length)
  const filteredLineCount = computed(() => filteredLines.value.length)

  function trimLines(nextLines) {
    if (nextLines.length <= MAX_LINES) return nextLines
    return nextLines.slice(nextLines.length - MAX_LINES)
  }

  async function loadLogs({ manual = false } = {}) {
    if (pollInFlight) return

    pollInFlight = true
    if (!initialized.value) {
      initialLoading.value = true
    }
    if (manual) {
      manualRefreshing.value = true
    }

    try {
      const payload = await getBackendLogs({
        limit: initialized.value ? INCREMENTAL_LIMIT : INITIAL_LIMIT,
        cursor: initialized.value ? cursor.value : null,
      })

      const nextLines = Array.isArray(payload?.lines) ? payload.lines : []
      lines.value = payload?.reset || !initialized.value
        ? trimLines(nextLines)
        : trimLines([...lines.value, ...nextLines])
      cursor.value = payload?.cursor || null
      sourceFile.value = payload?.source_file || ''
      lastRefreshedAt.value = new Date().toISOString()
      loadError.value = ''
      initialized.value = true
    } catch (error) {
      loadError.value = error?.message || t('backendLogs.loadFailed')
      if (autoRefreshEnabled.value) {
        autoRefreshEnabled.value = false
      }
    } finally {
      initialLoading.value = false
      manualRefreshing.value = false
      pollInFlight = false
    }
  }

  function stopPolling() {
    if (!pollTimer) return
    window.clearInterval(pollTimer)
    pollTimer = null
  }

  function startPolling() {
    if (pollTimer || !isActive.value || !autoRefreshEnabled.value || document.hidden) return
    pollTimer = window.setInterval(() => {
      loadLogs()
    }, POLL_INTERVAL_MS)
  }

  async function handleVisibilityChange() {
    if (document.hidden) {
      stopPolling()
      return
    }
    if (isActive.value && autoRefreshEnabled.value && !initialized.value) {
      await loadLogs()
    }
    startPolling()
  }

  function pauseAutoRefresh() {
    autoRefreshEnabled.value = false
  }

  function resumeAutoRefresh() {
    autoRefreshEnabled.value = true
  }

  async function refreshNow() {
    await loadLogs({ manual: true })
  }

  watch(
    [() => isActive.value, autoRefreshEnabled],
    async ([active, autoRefresh]) => {
      if (!active || document.hidden) {
        stopPolling()
        return
      }

      if (!initialized.value) {
        await loadLogs()
      }

      if (autoRefresh) {
        startPolling()
      } else {
        stopPolling()
      }
    },
    { immediate: true }
  )

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    stopPolling()
  })

  return {
    autoRefreshEnabled,
    filteredLineCount,
    filteredLines,
    initialized,
    initialLoading,
    keyword,
    lastRefreshedAt,
    lineCount,
    loadError,
    manualRefreshing,
    pauseAutoRefresh,
    refreshNow,
    resumeAutoRefresh,
    selectedLevel,
    sourceFile,
  }
}
