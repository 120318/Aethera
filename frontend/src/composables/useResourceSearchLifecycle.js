import { onMounted, ref, watch } from 'vue'
import { t } from '@/i18n'

export function useResourceSearchLifecycle({
  props,
  emit,
  operations,
  searchState,
  searchResults,
  performSearch,
  loadSearchResults,
  setSearchResults,
  clearSearchResults,
}) {
  const filtersLoaded = ref(false)

  onMounted(() => {
    if (!props.embedded && props.mediaId) {
      operations.refreshActiveCommands({
        target_type: 'media',
        target_id: props.mediaId,
        season_number: props.seasonNumber || null,
      })
    }

    if (props.initialResults) {
      setSearchResults(props.initialResults)
    } else if (props.searchTrigger > 0) {
      performSearch().then((command) => {
        if (command) emit('command-submitted', command)
      })
    } else if ((props.hasSearched || props.alwaysShowResults) && !props.activeCommand && props.isActive) {
      loadSearchResults()
    } else if (props.autoSearch && props.isActive) {
      handleInitialSearch()
    }
  })

  watch(searchResults, (newValue) => {
    if (newValue && newValue.length > 0 && !filtersLoaded.value) {
      filtersLoaded.value = true
    }
  })

  watch(
    () => props.initialResults,
    (results) => {
      if (!Array.isArray(results)) return
      setSearchResults(results)
    },
  )

  watch(
    () => [props.hasSearched, props.isActive, props.mediaId, props.activeCommand?.id, props.activeCommand?.status, props.searchTrigger],
    ([hasSearchedProp, isActive, mediaId, activeCommandIdentifier, activeCommandStatus, searchTrigger]) => {
      if ((!hasSearchedProp && !props.alwaysShowResults) || !isActive || !mediaId) return
      if (searchTrigger > 0) return
      if (activeCommandIdentifier && (activeCommandStatus === 'queued' || activeCommandStatus === 'running')) return
      if (searchResults.value.length > 0 || searchState.loading) return
      loadSearchResults()
    },
  )

  watch(
    () => [props.isActive, props.mediaId, props.seasonNumber],
    async ([isActive, mediaId]) => {
      if (props.embedded) {
        if (!mediaId || !isActive) return
        await loadSearchResults()
        return
      }
      if (!mediaId) return
      operations.refreshActiveCommands({
        target_type: 'media',
        target_id: mediaId,
        season_number: props.seasonNumber || null,
      })
    },
  )

  watch(
    () => props.searchTrigger,
    async (newValue) => {
      if (newValue <= 0) return
      clearSearchResults()
      searchState.loading = true
      searchState.loadingText = t('resourceSearch.searchSubmitted')
      const command = await performSearch()
      if (command) emit('command-submitted', command)
    },
  )

  watch(
    () => props.searchResultsRefreshTrigger,
    async (newValue) => {
      if (!newValue) return
      if (!props.hasSearched && !props.alwaysShowResults) return
      await loadSearchResults()
    },
  )

  function handleInitialSearch() {
    const mediaIdToUse = props.mediaId || searchState.media_id
    if (mediaIdToUse) {
      searchState.media_id = mediaIdToUse
    }
    performSearch().then((command) => {
      if (command) emit('command-submitted', command)
    })
  }

  return {
    filtersLoaded,
  }
}
