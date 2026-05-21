import { computed, ref } from 'vue'

export function useLocalResourcesOverview(props) {
  const selectedEpisodes = ref([])

  const episodesCount = computed(() => {
    return Number(props.totalEpisodes || 0)
  })

  const episodes = computed(() => {
    if (!episodesCount.value) return []
    return Array.from({ length: episodesCount.value }, (_, i) => i + 1)
  })

  const mediaTypeFromId = computed(() => {
    const parts = String(props.mediaId || '').split(':')
    return parts.length >= 3 ? parts[1] : ''
  })
  const mediaType = computed(() => (
    props.detail?.media_type || props.detail?.type || mediaTypeFromId.value || ''
  ))
  const isTv = computed(() => mediaType.value === 'tv')

  const seasonFilteredResources = computed(() => props.resources || [])

  const collectedEpisodeSet = computed(() => {
    const episodesSet = new Set()
    const collectedEpisodes = Array.isArray(props.overview?.collected_episodes)
      ? props.overview.collected_episodes
      : []
    if (collectedEpisodes.length > 0) {
      collectedEpisodes.forEach((ep) => episodesSet.add(ep))
      return episodesSet
    }
    seasonFilteredResources.value.forEach((resource) => {
      const resourceEpisodes = resource.attributes?.episodes || []
      resourceEpisodes.forEach((ep) => episodesSet.add(ep))
    })
    return episodesSet
  })

  const showEpisodeFilter = computed(() => (
    !props.overviewLoading
    && isTv.value
    && episodesCount.value > 0
    && collectedEpisodeSet.value.size > 0
  ))

  const showEpisodeFilterSkeleton = computed(() => props.overviewLoading && isTv.value && episodesCount.value > 0)

  const episodeSkeletonItems = computed(() => (
    episodesCount.value > 0 ? Math.min(episodesCount.value, 28) : 14
  ))

  function isEpisodeExisting(episode) {
    if (!episode) return false
    if (collectedEpisodeSet.value.has(episode)) return true

    const stringEpisode = String(episode)
    return collectedEpisodeSet.value.has(stringEpisode)
  }

  function toggleEpisode(episode) {
    if (selectedEpisodes.value.includes(episode)) {
      selectedEpisodes.value = selectedEpisodes.value.filter((item) => item !== episode)
      return
    }
    selectedEpisodes.value.push(episode)
  }

  function getEpisodeButtonClass(episode) {
    const classes = [
      'inline-flex',
      'items-center',
      'justify-center',
      'select-none',
      'border',
      'transition-colors',
      'duration-200',
      'text-center',
      'w-control-badge-sm',
      'h-control-badge-sm',
    ]

    if (!isEpisodeExisting(episode)) {
      classes.push('cursor-default', 'ui-episode-state-idle')
      return classes
    }

    const isSelected = selectedEpisodes.value.includes(episode)
    classes.push('cursor-pointer', 'border-separator')
    classes.push(isSelected ? 'ui-episode-state-selected' : 'ui-episode-state-collected')
    return classes
  }

  return {
    selectedEpisodes,
    seasonFilteredResources,
    showEpisodeFilter,
    showEpisodeFilterSkeleton,
    episodeSkeletonItems,
    episodes,
    isEpisodeExisting,
    toggleEpisode,
    getEpisodeButtonClass,
  }
}
