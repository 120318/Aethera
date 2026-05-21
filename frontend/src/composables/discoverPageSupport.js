import { t } from '@/i18n'

export const discoverInitialStackMinHeight = 'var(--size-content-height)'

export function buildDiscoverSkeletonMeasureMedia(t) {
  return {
    media_id: '__skeleton__',
    title: t('discover.skeleton.title'),
    year: 2026,
    media_type: 'tv',
    vote_average: 8.6,
    vote_count: 12345,
    original_language: '',
    subtitle_line1: t('discover.skeleton.subtitleLine1'),
    subtitle_line2: t('discover.skeleton.subtitleLine2'),
    overview: '',
  }
}

export function getDiscoverSkeletonColumns(viewportWidth) {
  if (viewportWidth >= 1024) return 3
  if (viewportWidth >= 640) return 2
  return 1
}

export function buildDiscoverMeasureCardWrapperStyle(measureCardWidth) {
  if (!measureCardWidth) return { width: 'var(--size-dialog-sm)' }
  return { width: `${measureCardWidth}px` }
}

export function buildDiscoverStackStyle() {
  return { minHeight: discoverInitialStackMinHeight }
}

export function buildOrderedDiscoverLists(listMetas, listStates) {
  return listMetas.map((meta) => {
    const state = listStates[meta.key] || {}
    return {
      key: meta.key,
      title: meta.title_key ? t(meta.title_key) : meta.title,
      items: state.items || [],
      error: state.error || null,
      loading: state.loading || false,
      loaded: state.loaded || false,
    }
  })
}

export function resolveActiveDiscoverList(activeListKey, orderedLists) {
  if (!activeListKey) return orderedLists[0] || null
  return orderedLists.find((list) => list.key === activeListKey) || orderedLists[0] || null
}

export function buildDiscoverPagedItems(items, page, pageSize) {
  const normalizedItems = Array.isArray(items) ? items : []
  const normalizedPageSize = Math.max(1, Number(pageSize) || 1)
  const totalPages = Math.max(1, Math.ceil(normalizedItems.length / normalizedPageSize))
  const normalizedPage = Math.min(Math.max(1, Number(page) || 1), totalPages)
  const start = (normalizedPage - 1) * normalizedPageSize

  return {
    items: normalizedItems.slice(start, start + normalizedPageSize),
    currentPage: normalizedPage,
    totalPages,
    hasPrevPage: normalizedPage > 1,
    hasNextPage: normalizedPage < totalPages,
  }
}

export function buildSearchResultsDescription({ query, loading, resultCount, t }) {
  const trimmedQuery = query.trim()
  if (loading) {
    return trimmedQuery
      ? t('discover.searchResults.searchingQuery', { query: trimmedQuery })
      : t('discover.searchResults.searching')
  }
  if (!trimmedQuery) return t('discover.searchResults.placeholder')
  if (!resultCount) return t('discover.searchResults.noQueryResults', { query: trimmedQuery })
  return t('discover.searchResults.queryResults', { query: trimmedQuery, count: resultCount })
}

export function buildDiscoverSearchHeroStyle(isCentered) {
  if (!isCentered) {
    return {
      paddingTop: 'var(--spacing-section)',
      paddingBottom: 'var(--spacing-section)',
      minHeight: 'var(--size-placeholder-lg)',
    }
  }
  return {
    paddingTop: '0',
    paddingBottom: 'var(--spacing-section)',
    minHeight: 'calc(var(--size-content-height) - var(--spacing-section))',
    overflow: 'hidden',
  }
}

export function normalizeDiscoverRank(rank) {
  const normalized = String(rank || '').trim()
  if (!normalized) return { key: '', page: 1 }
  return { key: normalized, page: 1 }
}

export function restoreDiscoverParams(params) {
  const mediaType = ['all', 'movie', 'tv'].includes(params.media_type)
    ? params.media_type
    : ['all', 'movie', 'tv'].includes(params.type) ? params.type : 'all'

  return {
    query: params.query || '',
    mediaType,
  }
}

export function buildDiscoverQueryParams(query, mediaType) {
  const trimmedQuery = query.trim()
  if (!trimmedQuery) return null

  const nextParams = { query: trimmedQuery }
  if (mediaType && mediaType !== 'all') {
    nextParams.media_type = mediaType
    nextParams.type = mediaType
  }
  return nextParams
}

export async function recalcDiscoverSkeletonMeasure({
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
}) {
  await nextTick()

  const gridCandidates = [
    loading ? searchLoadingGridRef.value : searchResultsGridRef.value,
    ...Object.values(listGridRefs.value),
  ].filter(Boolean)

  const gridEl = gridCandidates[0]
  const firstCardEl = gridEl?.firstElementChild
  if (!firstCardEl) return

  const gridStyle = getComputedStyle(gridEl)
  const rowGap = parseFloat(gridStyle.rowGap || gridStyle.gap || '0') || 0
  const columns = Math.max(1, skeletonColumns)
  const columnWidth = Math.max(0, (gridEl.getBoundingClientRect().width - rowGap * (columns - 1)) / columns)

  if (columnWidth > 0) {
    measureCardWidth.value = columnWidth
    await nextTick()
    const measuredHeight = measureCardRef.value?.$el?.getBoundingClientRect?.().height
      || measureCardWrapperRef.value?.firstElementChild?.getBoundingClientRect?.().height
    if (measuredHeight) {
      measuredMediaCardHeight.value = measuredHeight
    }
  }
}

export async function loadDiscoverListMetas({ getDiscoverListMetas, listsLoading, listMetas, activeListKey }) {
  listsLoading.value = true
  try {
    const payload = await getDiscoverListMetas()
    const enabledLists = (Array.isArray(payload?.data) ? payload.data : []).filter((list) => list?.enabled)
    listMetas.value = enabledLists.map((list) => ({ key: list.key, title: list.title, title_key: list.title_key }))
    if (!activeListKey.value && enabledLists.length) {
      activeListKey.value = enabledLists[0].key
    }
  } catch {
    listMetas.value = []
  } finally {
    listsLoading.value = false
  }
}

export async function loadDiscoverList({ key, listStates, getDiscoverLists }) {
  if (!key) return
  const current = listStates.value[key]
  if (current?.loaded || current?.loading) return

  listStates.value = {
    ...listStates.value,
    [key]: { key, items: current?.items || [], error: null, loaded: false, loading: true },
  }

  try {
    const payload = await getDiscoverLists({ keys: key, count: 30 })
    const data = Array.isArray(payload?.data) ? payload.data : []
    const list = data.find((item) => item.key === key) || data[0]
    listStates.value = {
      ...listStates.value,
      [key]: {
        key,
        items: (list?.items || []).map((item) => ({ ...item, subscribing: false, downloading: false })),
        error: list?.error || null,
        loaded: true,
        loading: false,
      },
    }
  } catch (error) {
    listStates.value = {
      ...listStates.value,
      [key]: { key, items: [], error: String(error), loaded: true, loading: false },
    }
  }
}
