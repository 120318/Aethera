import {
  buildDiscoverQueryParams,
  loadDiscoverList,
  loadDiscoverListMetas,
  recalcDiscoverSkeletonMeasure,
  restoreDiscoverParams,
} from '@/composables/discoverPageSupport'
import {
  buildMediaDetailRoute,
  handleDiscoverSearch,
  replaceDiscoverRoute,
  scrollToDiscoverSection,
  setDiscoverListGridRef,
  toggleDiscoverPanelState,
  updateDiscoverViewportWidth,
} from '@/composables/discoverPageInteractionSupport'

export function createDiscoverPageActions(ctx) {
  const {
    params,
    searchQuery,
    filters,
    clearParams,
    setParams,
    nextTick,
    loading,
    searchLoadingGridRef,
    searchResultsGridRef,
    listGridRefs,
    skeletonColumns,
    measureCardWidth,
    measureCardRef,
    measureCardWrapperRef,
    measuredMediaCardHeight,
    getDiscoverListMetas,
    listsLoading,
    listMetas,
    activeListKey,
    getDiscoverLists,
    router,
    route,
    discoverPanelVisible,
    clearResults,
    search,
    discoverSectionRef,
    viewportWidth,
  } = ctx

  const scroll = () => scrollToDiscoverSection(nextTick, discoverSectionRef)
  const updateUrlParams = () => {
    const nextParams = buildDiscoverQueryParams(searchQuery.value, filters.media_type)
    if (!nextParams) {
      clearParams()
      return
    }
    setParams(nextParams)
  }
  const replaceSearchUrl = () => {
    const nextParams = buildDiscoverQueryParams(searchQuery.value, filters.media_type)
    router.replace({ path: route.path, query: nextParams || {}, hash: '' })
  }
  const replaceDiscoverRank = (key, page = 1) => replaceDiscoverRoute(router, route, { rank: key, page })
  const clearDiscoverRank = () => replaceDiscoverRoute(router, route, {})

  return {
    setListGridRef: (key, el) => setDiscoverListGridRef(listGridRefs, key, el),
    updateViewportWidth: () => updateDiscoverViewportWidth(viewportWidth),
    restoreFromUrl: () => {
      const restored = restoreDiscoverParams(params.value)
      searchQuery.value = restored.query
      filters.media_type = restored.mediaType
    },
    updateUrlParams,
    recalcSkeletonMeasure: async () => recalcDiscoverSkeletonMeasure({
      nextTick,
      loading: loading.value,
      searchLoadingGridRef,
      searchResultsGridRef,
      listGridRefs,
      skeletonColumns: skeletonColumns.value,
      measureCardWidth,
      measureCardRef,
      measureCardWrapperRef,
      measuredMediaCardHeight,
    }),
    loadListMetas: async () => loadDiscoverListMetas({ getDiscoverListMetas, listsLoading, listMetas, activeListKey }),
    loadList: async (key) => loadDiscoverList({ key, listStates: ctx.listStates, getDiscoverLists }),
    replaceDiscoverRank,
    clearDiscoverRank,
    handleSearch: async () => {
      await handleDiscoverSearch({
        searchQuery,
        discoverPanelVisible,
        replaceSearchUrl,
        search,
        clearResults,
        clearSearchState: () => {
          searchQuery.value = ''
          clearParams()
        },
      })
    },
    toggleDiscoverPanel: async (key) => {
      await toggleDiscoverPanelState({
        key,
        discoverPanelVisible,
        activeListKey,
        activeListPage: ctx.activeListPage,
        searchQuery,
        clearResults,
        replaceDiscoverRoute: (query) => replaceDiscoverRoute(router, route, query),
        scrollToDiscoverSection: scroll,
      })
    },
    getMediaDetailRoute: buildMediaDetailRoute,
    scrollToDiscoverSection: scroll,
  }
}
