import { computed, reactive, ref } from 'vue'

import { isTorrentRemoved as utilIsTorrentRemoved } from '@/utils/resourceStatus'
import { useI18n } from 'vue-i18n'

export function useLocalResourcesList(resources, selectedEpisodes) {
  const { t } = useI18n()
  const resourceSortModel = ref({
    prop: 'created_at',
    order: 'descending',
  })

  const localFilters = reactive({
    keyword: '',
  })

  const hasActiveFilters = computed(() => !!localFilters.keyword)
  const resourceSortOptions = computed(() => [
    { label: t('localResources.importTime'), value: 'created_at' },
    { label: t('localResources.fileSize'), value: 'size' },
    { label: t('localResources.fileName'), value: 'file_name' },
  ])

  const filteredResources = computed(() => {
    if (!resources.value.length) return []

    let result = resources.value.filter((resource) => !utilIsTorrentRemoved(resource))

    if (selectedEpisodes.value.length > 0) {
      result = result.filter((resource) => {
        const resourceEpisodes = resource.attributes?.episodes || []
        return selectedEpisodes.value.some((selectedEpisode) => (
          resourceEpisodes.includes(selectedEpisode) || resourceEpisodes.includes(String(selectedEpisode))
        ))
      })
    }

    if (localFilters.keyword) {
      const keyword = localFilters.keyword.toLowerCase()
      result = result.filter((resource) => (
        (resource.file_name && resource.file_name.toLowerCase().includes(keyword))
        || (resource.name && resource.name.toLowerCase().includes(keyword))
        || (resource.resource_title && resource.resource_title.toLowerCase().includes(keyword))
      ))
    }

    return result
  })

  const sortedResources = computed(() => {
    const list = filteredResources.value.slice()
    const { prop, order } = resourceSortModel.value
    if (!prop) return list

    const multiplier = order === 'descending' ? -1 : 1
    list.sort((resourceA, resourceB) => compareResources(resourceA, resourceB, prop, multiplier))
    return list
  })

  const totalVisibleResources = computed(() => (
    resources.value.filter((resource) => !utilIsTorrentRemoved(resource)).length
  ))

  function clearFilters() {
    localFilters.keyword = ''
  }

  return {
    localFilters,
    resourceSortModel,
    resourceSortOptions,
    hasActiveFilters,
    filteredResources,
    sortedResources,
    totalVisibleResources,
    clearFilters,
    isTorrentRemoved: utilIsTorrentRemoved,
  }
}

function compareResources(resourceA, resourceB, prop, multiplier) {
  if (prop === 'file_name') {
    const valueA = (resourceA.file_name || resourceA.resource_title || resourceA.name || '').toString().toLowerCase()
    const valueB = (resourceB.file_name || resourceB.resource_title || resourceB.name || '').toString().toLowerCase()
    if (valueA < valueB) return -1 * multiplier
    if (valueA > valueB) return 1 * multiplier
    return 0
  }

  if (prop === 'size') {
    const valueA = Number(resourceA.size || 0)
    const valueB = Number(resourceB.size || 0)
    if (valueA === valueB) return 0
    return valueA > valueB ? multiplier : -multiplier
  }

  const valueA = typeof resourceA[prop] === 'number'
    ? resourceA[prop]
    : (resourceA[prop] ? Date.parse(resourceA[prop]) || 0 : 0)
  const valueB = typeof resourceB[prop] === 'number'
    ? resourceB[prop]
    : (resourceB[prop] ? Date.parse(resourceB[prop]) || 0 : 0)

  if (valueA === valueB) return 0
  return valueA > valueB ? multiplier : -multiplier
}
