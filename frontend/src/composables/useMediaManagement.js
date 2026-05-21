import { onUnmounted, ref, watch } from 'vue'

import { getMediaManagementSummary, listMediaManagementItems } from '@/api/mediaManagement'
import { upsertManagedItem } from '@/composables/mediaManagementPageSupport'

export function useMediaManagement() {
  const summary = ref({
    total: 0,
    subscribed: 0,
    followed: 0,
    downloading: 0,
    in_library: 0,
    issues: 0,
  })
  const items = ref([])
  const summaryLoading = ref(false)
  const loading = ref(false)
  const total = ref(0)
  const first = ref(0)
  const rows = ref(10)

  const filters = ref({
    statuses: [],
    query: '',
    mediaType: '',
    sort: 'activity',
  })

  let loadRequestId = 0
  let summaryRequestId = 0
  let queryTimer = null

  async function loadSummary() {
    const requestId = ++summaryRequestId
    summaryLoading.value = true
    try {
      const response = await getMediaManagementSummary()
      const data = response?.data || response || {}
      if (requestId !== summaryRequestId) return
      summary.value = {
        total: data?.total || 0,
        subscribed: data?.subscribed || 0,
        followed: data?.followed || 0,
        downloading: data?.downloading || 0,
        in_library: data?.in_library || 0,
        issues: data?.issues || 0,
      }
    } finally {
      if (requestId === summaryRequestId) {
        summaryLoading.value = false
      }
    }
  }

  async function loadItems() {
    const requestId = ++loadRequestId
    loading.value = true
    try {
      const params = {
        limit: rows.value,
        offset: first.value,
        sort: filters.value.sort,
      }
      if (filters.value.query) params.query = filters.value.query
      if (filters.value.mediaType) params.media_type = filters.value.mediaType
      if (Array.isArray(filters.value.statuses) && filters.value.statuses.length > 0) {
        params.statuses = filters.value.statuses.join(',')
      }
      const data = await listMediaManagementItems(params)
      if (requestId !== loadRequestId) return
      items.value = data?.items || []
      total.value = data?.total || 0
    } finally {
      if (requestId === loadRequestId) {
        loading.value = false
      }
    }
  }

  function patchItem(mediaId, updater, seasonNumber = null) {
    const index = items.value.findIndex((entry) => (
      entry.media_id === mediaId && (entry.season_number || null) === (seasonNumber || null)
    ))
    if (index === -1) return null

    const current = items.value[index]
    const next = updater(current)
    if (!next) {
      items.value.splice(index, 1)
      total.value = Math.max(0, total.value - 1)
      return null
    }

    items.value.splice(index, 1, next)
    return next
  }

  function restoreItem(item) {
    if (!item) return null
    const restored = upsertManagedItem(items.value, item)
    if (restored) {
      total.value = Math.max(total.value, items.value.length)
    }
    return restored
  }

  async function refreshSummary() {
    await loadSummary()
  }

  function refreshAll() {
    return Promise.all([loadSummary(), loadItems()])
  }

  function onPage(event) {
    first.value = event.first
    rows.value = event.rows
  }

  watch([first, rows], () => {
    loadItems()
  })

  watch(
    () => [filters.value.mediaType, filters.value.sort, ...(filters.value.statuses || [])],
    () => {
      first.value = 0
      loadItems()
    }
  )

  watch(
    () => filters.value.query,
    () => {
      first.value = 0
      if (queryTimer) {
        window.clearTimeout(queryTimer)
      }
      queryTimer = window.setTimeout(() => {
        loadItems()
      }, 250)
    }
  )

  onUnmounted(() => {
    if (queryTimer) {
      window.clearTimeout(queryTimer)
    }
  })

  return {
    summary,
    items,
    total,
    summaryLoading,
    loading,
    filters,
    first,
    rows,
    onPage,
    patchItem,
    restoreItem,
    refreshSummary,
    loadItems,
    refreshAll,
  }
}
