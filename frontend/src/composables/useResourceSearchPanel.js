import { computed, unref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export function useResourceSearchPanel({
  props,
  emit,
  searchState,
  searchResults,
  localSearchState,
  localFilters,
  siteOptions,
  sizeOptions,
  seederOptions,
  promotionOptions,
  filtersLoaded,
  fetchFilterPresets,
  performSearch,
}) {
  const { t } = useI18n()
  watch(searchResults, (newValue) => {
    if (newValue && newValue.length > 0 && !filtersLoaded.value) {
      fetchFilterPresets()
      filtersLoaded.value = true
    }
  })

  const dataViewPt = {
    header: { class: 'p-none' },
  }

  const activeTags = computed(() => {
    const tags = []

    if (props.showMediaIdInput && localSearchState.value.media_id) {
      tags.push({ label: t('resourceSearch.mediaId'), value: localSearchState.value.media_id })
    }

    if (searchState.keyword) {
      tags.push({ label: t('resourceSearch.searchTerm'), value: searchState.keyword })
    }

    if (props.showSiteInput && searchState.site && searchState.site.length > 0) {
      const siteLabels = searchState.site.map((site) => {
        const option = siteOptions.value.find((item) => item.value === site)
        return option ? option.label : site
      })
      tags.push({ label: t('resourceSearch.site'), value: siteLabels.join(', ') })
    }

    if (localFilters.value.resolutions?.length) {
      tags.push({ label: t('resourceSearch.resolution'), value: localFilters.value.resolutions.join(', ') })
    }
    if (localFilters.value.seasons?.length) {
      tags.push({ label: t('resourceSearch.seasons'), value: localFilters.value.seasons.join(', ') })
    }
    if (localFilters.value.episodes?.length) {
      tags.push({ label: t('resourceSearch.episodes'), value: localFilters.value.episodes.join(', ') })
    }
    if (localFilters.value.groups?.length) {
      tags.push({ label: t('resourceSearch.groups'), value: localFilters.value.groups.join(', ') })
    }
    if (localFilters.value.sources?.length) {
      tags.push({ label: t('resourceSearch.source'), value: localFilters.value.sources.join(', ') })
    }
    if (localFilters.value.resourceForms?.length) {
      tags.push({ label: t('resourceSearch.resourceForm'), value: localFilters.value.resourceForms.join(', ') })
    }
    if (localFilters.value.hdrTypes?.length) {
      tags.push({ label: t('subscription.hdrType'), value: localFilters.value.hdrTypes.join(', ') })
    }
    if (localFilters.value.tags?.length) {
      tags.push({ label: t('resourceSearch.tags'), value: localFilters.value.tags.join(', ') })
    }
    if (localFilters.value.audioCodecs?.length) {
      tags.push({ label: t('resourceSearch.audioCodec'), value: localFilters.value.audioCodecs.join(', ') })
    }
    if (localFilters.value.audioChannels?.length) {
      tags.push({ label: t('resourceSearch.audioChannels'), value: localFilters.value.audioChannels.join(', ') })
    }
    if (localFilters.value.colorDepths?.length) {
      tags.push({ label: t('resourceSearch.colorDepth'), value: localFilters.value.colorDepths.join(', ') })
    }
    if (localFilters.value.sizeRange) {
      const option = unref(sizeOptions).find((item) => item.value === localFilters.value.sizeRange)
      tags.push({ label: t('resourceSearch.size'), value: option ? option.label : localFilters.value.sizeRange })
    }
    if (localFilters.value.seeders) {
      const option = unref(seederOptions).find((item) => item.value === localFilters.value.seeders)
      tags.push({ label: t('resourceSearch.seeders'), value: option ? option.label : localFilters.value.seeders })
    }
    if (localFilters.value.promotions?.length) {
      const labels = localFilters.value.promotions.map((promotion) => {
        const option = unref(promotionOptions).find((item) => item.value === promotion)
        return option ? option.label : promotion
      })
      tags.push({ label: t('resourceSearch.promotion'), value: labels.join(', ') })
    }
    if (localFilters.value.matchState) {
      const matchStateLabelMap = {
        matched_id: t('resourceSearch.matchedId'),
        unmatched_id: t('resourceSearch.unmatchedId'),
        matched_rule: t('resourceSearch.matchedRule'),
      }
      tags.push({
        label: t('resourceSearch.matchState'),
        value: matchStateLabelMap[localFilters.value.matchState] || localFilters.value.matchState,
      })
    }

    return tags
  })

  async function handleSearch() {
    const mediaIdToUse = props.mediaId || localSearchState.value.media_id
    if (mediaIdToUse) {
      searchState.media_id = mediaIdToUse
      localSearchState.value.media_id = mediaIdToUse
    }

    const command = await performSearch()
    if (command) emit('command-submitted', command)
  }

  return {
    dataViewPt,
    activeTags,
    handleSearch,
  }
}
