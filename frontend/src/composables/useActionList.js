import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { getActionFilterOptions, listActions } from '@/api/actions'

export function useActionList({ mediaId, showFilters, targetId, targetType }) {
  const initialLoading = ref(true)
  const listLoading = ref(false)
  const items = ref([])
  const keyword = ref('')
  const selectedKinds = ref([])
  const selectedStatuses = ref([])
  const selectedTriggers = ref([])
  const first = ref(0)
  const rows = ref(10)
  const totalRecords = ref(0)
  const kindOptions = ref([])
  const statusOptions = ref([])
  const triggerOptions = ref([])
  const keywordPending = ref(false)

  let keywordTimer = null
  let loadRequestId = 0
  let filterOptionsRequestId = 0

  const showPaginator = computed(() => totalRecords.value > rows.value)
  const hasActiveFilters = computed(() => (
    !!keyword.value
    || selectedKinds.value.length > 0
    || selectedStatuses.value.length > 0
    || selectedTriggers.value.length > 0
  ))
  const shouldShowFilters = computed(() => (
    showFilters.value && (
      hasActiveFilters.value
      || totalRecords.value > 0
      || listLoading.value
      || initialLoading.value
      || keywordPending.value
    )
  ))

  async function load() {
    const requestId = ++loadRequestId
    listLoading.value = true
    try {
      const params = {
        limit: rows.value,
        offset: first.value,
      }
      if (mediaId.value) params.media_id = mediaId.value
      if (targetType.value) params.target_type = targetType.value
      if (targetId.value) params.target_id = targetId.value
      if (keyword.value) params.keyword = keyword.value
      if (selectedKinds.value.length > 0) params.kind = [...selectedKinds.value]
      if (selectedStatuses.value.length > 0) params.status = [...selectedStatuses.value]
      if (selectedTriggers.value.length > 0) params.trigger = [...selectedTriggers.value]
      const data = await listActions(params)
      if (requestId !== loadRequestId) return
      items.value = data?.items || []
      totalRecords.value = data?.total || 0
    } finally {
      if (requestId === loadRequestId) {
        listLoading.value = false
        initialLoading.value = false
      }
    }
  }

  async function loadFilterOptions(mapKindLabel, mapStatusLabel, mapTriggerLabel) {
    const requestId = ++filterOptionsRequestId
    const params = {}
    if (mediaId.value) params.media_id = mediaId.value
    if (targetType.value) params.target_type = targetType.value
    if (targetId.value) params.target_id = targetId.value
    if (keyword.value) params.keyword = keyword.value
    const data = await getActionFilterOptions(params)
    if (requestId !== filterOptionsRequestId) return
    kindOptions.value = (data?.kinds || []).map(value => ({ label: mapKindLabel(value), value }))
    statusOptions.value = (data?.statuses || []).map(value => ({ label: mapStatusLabel(value), value }))
    triggerOptions.value = (data?.triggers || []).map(value => ({ label: mapTriggerLabel(value), value }))
  }

  function clearKeywordTimer() {
    if (!keywordTimer) return
    window.clearTimeout(keywordTimer)
    keywordTimer = null
  }

  function onPage(event) {
    first.value = event.first
    rows.value = event.rows
  }

  function resetFilters() {
    keyword.value = ''
    selectedKinds.value = []
    selectedStatuses.value = []
    selectedTriggers.value = []
  }

  function initialize(labelResolvers) {
    const { mapKindLabel, mapStatusLabel, mapTriggerLabel } = labelResolvers

    onMounted(async () => {
      await load()
      await loadFilterOptions(mapKindLabel, mapStatusLabel, mapTriggerLabel)
    })

    watch([mediaId, targetType, targetId], async () => {
      first.value = 0
      await load()
      await loadFilterOptions(mapKindLabel, mapStatusLabel, mapTriggerLabel)
    })

    watch([first, rows], () => {
      load()
    })

    watch(keyword, () => {
      first.value = 0
      clearKeywordTimer()
      keywordPending.value = true
      keywordTimer = window.setTimeout(() => {
        Promise.all([
          load(),
          loadFilterOptions(mapKindLabel, mapStatusLabel, mapTriggerLabel),
        ]).finally(() => {
          keywordPending.value = false
        })
      }, 250)
    })

    watch([selectedKinds, selectedStatuses, selectedTriggers], () => {
      first.value = 0
      load()
    })

    onBeforeUnmount(() => {
      clearKeywordTimer()
    })
  }

  return {
    first,
    hasActiveFilters,
    initialLoading,
    initialize,
    items,
    keyword,
    keywordPending,
    kindOptions,
    listLoading,
    onPage,
    resetFilters,
    rows,
    selectedKinds,
    selectedStatuses,
    selectedTriggers,
    shouldShowFilters,
    showPaginator,
    statusOptions,
    totalRecords,
    triggerOptions,
  }
}
