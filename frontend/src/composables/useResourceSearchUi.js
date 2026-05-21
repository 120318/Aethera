import { computed, ref, watch } from 'vue'

import { getFilters } from '@/api/filter'
import { useActionPrerequisites } from '@/composables/useActionPrerequisites'
import { useI18n } from 'vue-i18n'

const SIZE_OPTIONS = [
  { labelKey: 'resourceSearch.sizeSmall', value: 'small' },
  { labelKey: 'resourceSearch.sizeMedium', value: 'medium' },
  { labelKey: 'resourceSearch.sizeLarge', value: 'large' },
  { labelKey: 'resourceSearch.sizeHuge', value: 'huge' },
]

const SEEDER_OPTIONS = [
  { labelKey: 'resourceSearch.seederAny', value: 'any' },
  { labelKey: 'resourceSearch.seederGood', value: 'good' },
  { labelKey: 'resourceSearch.seederExcellent', value: 'excellent' },
]

const PROMOTION_OPTIONS = [
  { labelKey: 'resourceSearch.free', value: 'free' },
  { labelKey: 'resourceSearch.doubleFree', value: 'double_free' },
  { labelKey: 'resourceSearch.discount', value: 'discount' },
]

const IMDB_MATCH_OPTIONS = [
  { labelKey: 'resourceSearch.matchedId', value: 'matched_id' },
  { labelKey: 'resourceSearch.unmatchedId', value: 'unmatched_id' },
  { labelKey: 'resourceSearch.matchedRule', value: 'matched_rule' },
]

const SORT_OPTIONS = [
  { labelKey: 'resourceSearch.seedersCount', value: 'seeders' },
  { labelKey: 'resourceSearch.publishDate', value: 'publish_date' },
  { labelKey: 'resourceSearch.size', value: 'size' },
  { labelKey: 'resourceSearch.title', value: 'title' },
]

export function useResourceSearchUi({
  props,
  emit,
  searchState,
  localFilters,
  sortState,
  hasSearched,
  searchResults,
  mediaInfo,
  clearAllFilters,
  addTorrent,
  filterCatalog,
}) {
  const { ensureDownloadReady } = useActionPrerequisites()
  const { t } = useI18n()
  const filterDialogVisible = ref(false)
  const downloadDialogVisible = ref(false)
  const selectedResourceForDownload = ref(null)
  const filterPresets = ref([])
  const selectedFilterPreset = ref(null)
  const localSearchState = ref({
    media_id: props.mediaId,
  })

  const sortModel = computed({
    get: () => ({
      prop: sortState.value.field,
      order: sortState.value.direction === 'asc' ? 'ascending' : 'descending',
    }),
    set: (value) => {
      if (!value) return
      sortState.value.field = value.prop
      sortState.value.direction = value.order === 'ascending' ? 'asc' : 'desc'
    },
  })

  const shouldShowResultsCard = computed(() => (
    hasSearched.value || searchResults.value.length > 0 || props.alwaysShowResults
  ))

  watch(
    () => props.mediaId,
    (newMediaId) => {
      localSearchState.value.media_id = newMediaId
      searchState.media_id = newMediaId
    },
    { immediate: true },
  )

  watch(
    () => props.type,
    (newType) => {
      if (newType) searchState.type = newType
    },
    { immediate: true },
  )

  watch(
    () => [searchState.loading, searchState.commandLoading],
    () => {
      emit('search-loading', !!searchState.commandLoading)
    },
  )

  watch(searchResults, () => {
    if (props.embedded) return
    emit('search-complete', {
      searchResults: searchResults.value,
      mediaInfo: mediaInfo.value,
    })
  })

  async function fetchFilterPresets() {
    if (Array.isArray(filterCatalog?.value) && filterCatalog.value.length > 0) {
      filterPresets.value = filterCatalog.value
      return
    }
    try {
      const data = await getFilters()
      filterPresets.value = data || []
    } catch (error) {
      console.error(t('resourceSearch.filterListLoadFailed'), error)
    }
  }

  function applyFilterPreset() {
    if (!selectedFilterPreset.value) return

    const preset = filterPresets.value.find((item) => item.id === selectedFilterPreset.value)
    if (!preset?.filters) return

    const filters = preset.filters
    if (filters.resolution) localFilters.value.resolutions = filters.resolution
    if (filters.source) localFilters.value.sources = filters.source
    if (filters.resource_form) localFilters.value.resourceForms = filters.resource_form
  }

  function handleDialogConfirm() {
    filterDialogVisible.value = false
  }

  function handleClearFilters() {
    clearAllFilters()
    if (props.disableKeywordInput && props.keyword) {
      localFilters.value.keyword = props.keyword
    }
  }

  async function handleDownloadClick(resource) {
    const mediaType = props.type || mediaInfo.value?.media_type || mediaInfo.value?.type
    const canContinue = await ensureDownloadReady(mediaType)
    if (!canContinue) return
    selectedResourceForDownload.value = resource
    downloadDialogVisible.value = true
  }

  async function handleDownloadConfirm(data) {
    try {
      const mediaPayload = mediaInfo.value || {
        media_id: props.mediaId || localSearchState.value.media_id,
        title: props.title || '',
        year: props.year ? Number(props.year) : undefined,
      }
      const command = await addTorrent(data.resource, mediaPayload, data.directory_id)
      if (command) {
        emit('command-submitted', command)
        emit('download', {
          resource: data.resource,
          mediaInfo: mediaPayload,
          command,
        })
      }
    } catch (error) {
      console.error(t('resourceSearch.downloadResultHandleFailed'), error)
    } finally {
      downloadDialogVisible.value = false
      selectedResourceForDownload.value = null
    }
  }

  return {
    sizeOptions: computed(() => SIZE_OPTIONS.map((option) => ({ label: t(option.labelKey), value: option.value }))),
    seederOptions: computed(() => SEEDER_OPTIONS.map((option) => ({ label: t(option.labelKey), value: option.value }))),
    promotionOptions: computed(() => PROMOTION_OPTIONS.map((option) => ({ label: t(option.labelKey), value: option.value }))),
    imdbMatchOptions: computed(() => IMDB_MATCH_OPTIONS.map((option) => ({ label: t(option.labelKey), value: option.value }))),
    sortOptions: computed(() => SORT_OPTIONS.map((option) => ({ label: t(option.labelKey), value: option.value }))),
    filterDialogVisible,
    downloadDialogVisible,
    selectedResourceForDownload,
    filterPresets,
    selectedFilterPreset,
    localSearchState,
    sortModel,
    shouldShowResultsCard,
    fetchFilterPresets,
    applyFilterPreset,
    handleDialogConfirm,
    handleClearFilters,
    handleDownloadClick,
    handleDownloadConfirm,
  }
}
