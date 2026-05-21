import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { getEventFilterOptions, listEvents } from '@/api/events'

export function useEventList(mediaId, showFilters, refreshKey = null, seasonNumber = null) {
  const initialLoading = ref(true)
  const listLoading = ref(false)
  const items = ref([])
  const keyword = ref('')
  const selectedLevels = ref([])
  const selectedTypes = ref([])
  const selectedSources = ref([])
  const first = ref(0)
  const rows = ref(10)
  const totalRecords = ref(0)
  const typeOptions = ref([])
  const sourceOptions = ref([])
  const levelOptions = ref([])
  const keywordPending = ref(false)

  let keywordTimer = null
  let loadRequestId = 0
  let filterOptionsRequestId = 0

  const showPaginator = computed(() => totalRecords.value > rows.value)
  const hasActiveFilters = computed(() => (
    !!keyword.value
    || selectedLevels.value.length > 0
    || selectedTypes.value.length > 0
    || selectedSources.value.length > 0
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
      if (seasonNumber?.value) params.season_number = seasonNumber.value
      if (keyword.value) params.keyword = keyword.value
      if (selectedLevels.value.length > 0) params.level = [...selectedLevels.value]
      if (selectedTypes.value.length > 0) params.type = [...selectedTypes.value]
      if (selectedSources.value.length > 0) params.source = [...selectedSources.value]
      const data = await listEvents(params)
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

  async function loadFilterOptions(mapLevelLabel, mapTypeLabel, mapSourceLabel) {
    const requestId = ++filterOptionsRequestId
    const params = {}
    if (mediaId.value) params.media_id = mediaId.value
    if (seasonNumber?.value) params.season_number = seasonNumber.value
    if (keyword.value) params.keyword = keyword.value
    const data = await getEventFilterOptions(params)
    if (requestId !== filterOptionsRequestId) return
    levelOptions.value = (data?.levels || []).map(value => ({ label: mapLevelLabel(value), value }))
    typeOptions.value = (data?.types || []).map(value => ({ label: mapTypeLabel(value), value }))
    sourceOptions.value = (data?.sources || []).map(value => ({ label: mapSourceLabel(value), value }))
  }

  function clearKeywordTimer() {
    if (!keywordTimer) return
    window.clearTimeout(keywordTimer)
    keywordTimer = null
  }

  function resetEventViewState() {
    items.value = []
    totalRecords.value = 0
    typeOptions.value = []
    sourceOptions.value = []
    levelOptions.value = []
    keyword.value = ''
    selectedLevels.value = []
    selectedTypes.value = []
    selectedSources.value = []
    first.value = 0
    initialLoading.value = true
    listLoading.value = false
    keywordPending.value = false
    loadRequestId += 1
    filterOptionsRequestId += 1
    clearKeywordTimer()
  }

  function onPage(event) {
    first.value = event.first
    rows.value = event.rows
  }

  function resetFilters() {
    keyword.value = ''
    selectedLevels.value = []
    selectedTypes.value = []
    selectedSources.value = []
    first.value = 0
  }

  function initialize(labelResolvers) {
    const { mapLevelLabel, mapTypeLabel, mapSourceLabel } = labelResolvers

    onMounted(async () => {
      await load()
      await loadFilterOptions(mapLevelLabel, mapTypeLabel, mapSourceLabel)
    })

    watch([mediaId, seasonNumber].filter(Boolean), async () => {
      resetEventViewState()
      await load()
      await loadFilterOptions(mapLevelLabel, mapTypeLabel, mapSourceLabel)
    })

    if (refreshKey) {
      watch(refreshKey, async (value) => {
        if (!value) return
        await load()
        await loadFilterOptions(mapLevelLabel, mapTypeLabel, mapSourceLabel)
      })
    }

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
          loadFilterOptions(mapLevelLabel, mapTypeLabel, mapSourceLabel),
        ]).finally(() => {
          keywordPending.value = false
        })
      }, 250)
    })

    watch([selectedLevels, selectedTypes, selectedSources], () => {
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
    levelOptions,
    listLoading,
    onPage,
    resetFilters,
    rows,
    selectedLevels,
    selectedSources,
    selectedTypes,
    shouldShowFilters,
    showPaginator,
    sourceOptions,
    totalRecords,
    typeOptions,
  }
}
