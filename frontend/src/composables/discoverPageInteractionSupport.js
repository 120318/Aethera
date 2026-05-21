export function setDiscoverListGridRef(listGridRefs, key, el) {
  if (!key) return
  if (!el) {
    delete listGridRefs.value[key]
    return
  }
  listGridRefs.value[key] = el
}

export function updateDiscoverViewportWidth(viewportWidth) {
  viewportWidth.value = window.innerWidth
}

export async function scrollToDiscoverSection(nextTick, discoverSectionRef) {
  await nextTick()
  discoverSectionRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

export function replaceDiscoverRoute(router, route, query) {
  router.replace({ path: route.path, query, hash: '' })
}

export async function handleDiscoverSearch({
  searchQuery,
  discoverPanelVisible,
  replaceSearchUrl,
  search,
  clearResults,
  clearSearchState,
}) {
  const query = searchQuery.value.trim()
  if (!query) {
    discoverPanelVisible.value = false
    clearResults()
    clearSearchState()
    return
  }
  discoverPanelVisible.value = false
  replaceSearchUrl()
  await search(query)
}

export async function toggleDiscoverPanelState({
  key,
  discoverPanelVisible,
  activeListKey,
  activeListPage,
  searchQuery,
  clearResults,
  replaceDiscoverRoute,
  scrollToDiscoverSection,
}) {
  if (!key) return
  if (discoverPanelVisible.value && activeListKey.value === key) {
    discoverPanelVisible.value = false
    replaceDiscoverRoute({})
    return
  }
  searchQuery.value = ''
  clearResults()
  activeListKey.value = key
  activeListPage.value = 1
  discoverPanelVisible.value = true
  replaceDiscoverRoute({ rank: key, page: 1 })
  await scrollToDiscoverSection()
}

export function buildMediaDetailRoute(media) {
  const mediaId = typeof media === 'string' ? media : media?.media_id
  if (media?.source && media?.source_id && media?.media_type) {
    return {
      name: 'MediaSourceDetail',
      query: {
        source: media.source,
        source_id: media.source_id,
        media_type: media.media_type,
        title: media.title,
        year: media.year,
      },
    }
  }
  if (mediaId) {
    const seasonNumber = Number(media?.season_number)
    if (String(mediaId).includes(':tv:') && (!Number.isInteger(seasonNumber) || seasonNumber <= 0)) {
      return { name: 'DiscoverPage' }
    }
    const query = Number.isInteger(seasonNumber) && seasonNumber > 0 ? { season: seasonNumber } : {}
    return { name: 'MediaDetail', params: { mediaId }, query }
  }
  return { name: 'DiscoverPage' }
}

export async function syncDiscoverRouteQuery({
  route,
  searchQuery,
  filters,
  clearResults,
  discoverPanelVisible,
  search,
}) {
  const nextQuery = typeof route.query.query === 'string' ? route.query.query : ''
  const nextMediaType = typeof route.query.media_type === 'string' ? route.query.media_type : 'all'

  if (!nextQuery) {
    if (searchQuery.value) {
      searchQuery.value = ''
      clearResults()
    }
    return
  }

  searchQuery.value = nextQuery
  if (['all', 'movie', 'tv'].includes(nextMediaType)) {
    filters.media_type = nextMediaType
  }
  discoverPanelVisible.value = false
  await search(nextQuery)
}

export async function syncDiscoverRouteRank({
  rank,
  page,
  listMetas,
  isValidDiscoverRank,
  searchQuery,
  clearResults,
  activeListKey,
  discoverPanelVisible,
  normalizeDiscoverRank,
  scrollToDiscoverSection,
  activeListPage,
}) {
  const { key, page: fallbackPage } = normalizeDiscoverRank(rank)
  if (!key) {
    discoverPanelVisible.value = false
    activeListPage.value = 1
    return
  }
  const isValid = typeof isValidDiscoverRank === 'function'
    ? isValidDiscoverRank(key)
    : listMetas.value.some((item) => item.key === key)
  if (!isValid) return
  searchQuery.value = ''
  clearResults()
  activeListKey.value = key
  activeListPage.value = Math.max(1, Number(page) || fallbackPage)
  discoverPanelVisible.value = true
  await scrollToDiscoverSection()
}

export async function initializeDiscoverPage({
  nextTick,
  updateViewportWidth,
  layoutReady,
  restoreFromUrl,
  loadListMetas,
  route,
  normalizeDiscoverRank,
  listMetas,
  activeListKey,
  activeListPage,
  discoverPanelVisible,
  isValidDiscoverRank,
  scrollToDiscoverSection,
  params,
  updateUrlParams,
  search,
  recalcSkeletonMeasure,
}) {
  updateViewportWidth()
  await nextTick()
  layoutReady.value = true

  restoreFromUrl()
  await loadListMetas()

  const initialRank = normalizeDiscoverRank(route.query.rank)
  const isValidInitialRank = typeof isValidDiscoverRank === 'function'
    ? isValidDiscoverRank(initialRank.key)
    : listMetas.value.some((item) => item.key === initialRank.key)
  if (initialRank.key && isValidInitialRank) {
    activeListKey.value = initialRank.key
    activeListPage.value = Math.max(1, Number(route.query.page) || initialRank.page)
    discoverPanelVisible.value = true
    await scrollToDiscoverSection()
  }

  if (params.value.query?.trim()) {
    updateUrlParams()
    await search(params.value.query)
  }

  recalcSkeletonMeasure()
}
