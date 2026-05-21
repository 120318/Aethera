import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDiscoverListMetas, getDiscoverLists } from '@/api/discover'
import {
  buildDiscoverPagedItems,
  buildDiscoverMeasureCardWrapperStyle,
  buildDiscoverSearchHeroStyle,
  buildDiscoverStackStyle,
  buildOrderedDiscoverLists,
  buildDiscoverSkeletonMeasureMedia,
  getDiscoverSkeletonColumns,
  normalizeDiscoverRank,
  resolveActiveDiscoverList,
} from '@/composables/discoverPageSupport'
import {
  initializeDiscoverPage,
  syncDiscoverRouteRank,
  syncDiscoverRouteQuery,
} from '@/composables/discoverPageInteractionSupport'
import { createDiscoverPageActions } from '@/composables/discoverPageActionFactory'
import { useSearch } from '@/composables/useSearch'
import { useUrlParams } from '@/composables/useUrlParams'
import { useI18n } from 'vue-i18n'

const TODAY_UPDATES_KEY = 'today_updates'

export function useDiscoverPage() {
  const DISCOVER_PAGE_SIZE = 15
  const { t } = useI18n()
  const router = useRouter()
  const route = useRoute()
  const stackRef = ref(null)
  const searchBlockRef = ref(null)
  const measureCardWrapperRef = ref(null)
  const measureCardRef = ref(null)
  const searchLoadingGridRef = ref(null)
  const searchResultsGridRef = ref(null)
  const discoverSectionRef = ref(null)
  const listGridRefs = ref({})
  const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1280)
  const measureCardWidth = ref(0)
  const measuredMediaCardHeight = ref(0)
  const layoutReady = ref(false)

  const { params, setParams, clearParams } = useUrlParams()
  const {
    query: searchQuery,
    loading,
    results,
    hasSearched,
    filters,
    search,
    clearResults,
  } = useSearch({
    apiEndpoint: '/api/v1/media/search',
    defaultFilters: { media_type: 'all' },
  })

  const listsLoading = ref(false)
  const listMetas = ref([])
  const listStates = ref({})
  const activeListKey = ref('')
  const activeListPage = ref(1)
  const discoverPanelVisible = ref(false)
  const skeletonColumns = computed(() => getDiscoverSkeletonColumns(viewportWidth.value))
  const skeletonCount = computed(() => skeletonColumns.value * 4)
  const listSkeletonCount = computed(() => 6)
  const measureCardWrapperStyle = computed(() => buildDiscoverMeasureCardWrapperStyle(measureCardWidth.value))
  const stackStyle = computed(() => buildDiscoverStackStyle())
  const orderedLists = computed(() => buildOrderedDiscoverLists(listMetas.value, listStates.value))
  const discoverButtons = computed(() => orderedLists.value)
  const activeList = computed(() => resolveActiveDiscoverList(activeListKey.value, orderedLists.value))
  const activeListPaged = computed(() => buildDiscoverPagedItems(activeList.value?.items || [], activeListPage.value, DISCOVER_PAGE_SIZE))
  const showSearchResults = computed(() => hasSearched.value && !discoverPanelVisible.value)
  const hasRouteQuery = computed(() => Boolean(String(params.value.query || '').trim()))
  const showDiscoverButtons = computed(() => (
    !listsLoading.value
    && !showSearchResults.value
    && !hasRouteQuery.value
  ))
  const showTodayUpdatesPanel = computed(() => discoverPanelVisible.value && activeListKey.value === TODAY_UPDATES_KEY)
  const isSearchHeroCentered = computed(() => !hasSearched.value && !discoverPanelVisible.value)
  const searchHeroBodyClass = computed(() => (isSearchHeroCentered.value ? '-translate-y-section -mt-block' : ''))
  const searchHeroStyle = computed(() => buildDiscoverSearchHeroStyle(isSearchHeroCentered.value))
  const actions = createDiscoverPageActions({
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
    activeListPage,
    getDiscoverLists,
    listStates,
    router,
    route,
    discoverPanelVisible,
    clearResults,
    search,
    discoverSectionRef,
    viewportWidth,
  })

  watch(() => filters.media_type, () => {
    if (hasSearched.value && searchQuery.value.trim()) {
      actions.updateUrlParams()
    }
  })

  watch(() => route.fullPath, async () => syncDiscoverRouteQuery({ route, searchQuery, filters, clearResults, discoverPanelVisible, search }))
  watch(() => [route.query.rank, route.query.page], async ([rank, page]) => syncDiscoverRouteRank({
    rank,
    page,
    listMetas,
    isValidDiscoverRank: (key) => key === TODAY_UPDATES_KEY || listMetas.value.some((item) => item.key === key),
    searchQuery,
    clearResults,
    activeListKey,
    discoverPanelVisible,
    normalizeDiscoverRank,
    scrollToDiscoverSection: actions.scrollToDiscoverSection,
    activeListPage,
  }))

  watch(() => activeListKey.value, (key) => {
    if (!key) return
    if (key === TODAY_UPDATES_KEY) return
    actions.loadList(key)
  })

  watch(() => [discoverPanelVisible.value, activeListKey.value, activeListPage.value], ([visible, key, page]) => {
    if (!visible || !key) return
    actions.replaceDiscoverRank(key, page)
  })

  watch(() => activeList.value?.items?.length || 0, () => {
    activeListPage.value = activeListPaged.value.currentPage
  })

  watch(() => [
    loading.value,
    results.value.length,
    activeListKey.value,
    orderedLists.value.map((list) => `${list.key}:${list.loading}:${list.items.length}`).join('|'),
    skeletonCount.value,
  ], () => actions.recalcSkeletonMeasure())

  onMounted(async () => {
    await initializeDiscoverPage({
      nextTick,
      updateViewportWidth: actions.updateViewportWidth,
      layoutReady,
      restoreFromUrl: actions.restoreFromUrl,
      loadListMetas: actions.loadListMetas,
      route,
      normalizeDiscoverRank,
      listMetas,
      activeListKey,
      activeListPage,
      discoverPanelVisible,
      isValidDiscoverRank: (key) => key === TODAY_UPDATES_KEY || listMetas.value.some((item) => item.key === key),
      scrollToDiscoverSection: actions.scrollToDiscoverSection,
      params,
      updateUrlParams: actions.updateUrlParams,
      search,
      recalcSkeletonMeasure: actions.recalcSkeletonMeasure,
    })
    window.addEventListener('resize', actions.recalcSkeletonMeasure)
    window.addEventListener('resize', actions.updateViewportWidth)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', actions.recalcSkeletonMeasure)
    window.removeEventListener('resize', actions.updateViewportWidth)
  })

  return {
    stackRef,
    searchBlockRef,
    measureCardWrapperRef,
    measureCardRef,
    searchLoadingGridRef,
    searchResultsGridRef,
    discoverSectionRef,
    skeletonMeasureMedia: computed(() => buildDiscoverSkeletonMeasureMedia(t)),
    setListGridRef: actions.setListGridRef,
    layoutReady,
    measureCardWrapperStyle,
    stackStyle,
    searchQuery,
    loading,
    results,
    hasSearched,
    listsLoading,
    listMetas,
    discoverButtons,
    activeList,
    activeListItems: computed(() => activeListPaged.value.items),
    activeListCurrentPage: computed(() => activeListPaged.value.currentPage),
    activeListTotalPages: computed(() => activeListPaged.value.totalPages),
    activeListHasPrevPage: computed(() => activeListPaged.value.hasPrevPage),
    activeListHasNextPage: computed(() => activeListPaged.value.hasNextPage),
    discoverPanelVisible,
    activeListKey,
    todayUpdatesKey: TODAY_UPDATES_KEY,
    showSearchResults,
    showDiscoverButtons,
    showTodayUpdatesPanel,
    isSearchHeroCentered,
    searchHeroBodyClass,
    searchHeroStyle,
    skeletonCount,
    listSkeletonCount,
    measuredMediaCardHeight,
    handleSearch: actions.handleSearch,
    clearSearch: () => {
      searchQuery.value = ''
      clearResults()
      discoverPanelVisible.value = false
      clearParams()
    },
    toggleDiscoverPanel: actions.toggleDiscoverPanel,
    prevDiscoverPage: () => {
      if (!activeListPaged.value.hasPrevPage) return
      activeListPage.value = activeListPaged.value.currentPage - 1
    },
    nextDiscoverPage: () => {
      if (!activeListPaged.value.hasNextPage) return
      activeListPage.value = activeListPaged.value.currentPage + 1
    },
    getMediaDetailRoute: actions.getMediaDetailRoute,
    getMediaCardKey: (item) => item?.media_id || `${item?.source || 'source'}:${item?.media_type || 'media'}:${item?.source_id || item?.douban_id || item?.title}`,
  }
}
