import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const ROWS_PER_PAGE = 10
const STATUS_SORT_PRIORITY = {
  failed: 0,
  attention: 1,
  importing: 2,
  migrating: 3,
  ready_to_import: 4,
  downloading: 5,
  queued: 6,
  completed: 7,
}

export function useTaskLiveFilters(tasks) {
  const { t } = useI18n()
  const currentFirst = ref(0)
  const localFilters = reactive({ keyword: '', statuses: [], episodes: [] })
  const sortModel = ref({ prop: 'added_on', order: 'descending' })

  const statusOptions = computed(() => [
    { label: t('taskLive.status.queued'), value: 'queued' },
    { label: t('taskLive.status.downloading'), value: 'downloading' },
    { label: t('taskLive.status.readyToImport'), value: 'ready_to_import' },
    { label: t('taskLive.status.importing'), value: 'importing' },
    { label: t('taskLive.status.migrating'), value: 'migrating' },
    { label: t('taskLive.status.completed'), value: 'completed' },
    { label: t('taskLive.status.attention'), value: 'attention' },
    { label: t('taskLive.status.failed'), value: 'failed' },
  ])

  const sortOptions = computed(() => [
    { label: t('taskLive.addedAt'), value: 'added_on' },
    { label: t('taskLive.progress'), value: 'progress' },
    { label: t('resourceSearch.size'), value: 'size' },
    { label: t('taskLive.state'), value: 'status' },
  ])

  const episodeOptions = computed(() => {
    const episodes = new Set()
    for (const task of tasks.value) {
      for (const episode of resolveTaskEpisodes(task)) {
        episodes.add(episode)
      }
    }
    return [...episodes]
      .sort((left, right) => left - right)
      .map(episode => ({
        label: t('taskLive.episodeLabel', { number: episode }),
        value: episode,
      }))
  })

  const hasActiveFilters = computed(() => (
    localFilters.keyword
    || localFilters.statuses.length > 0
    || localFilters.episodes.length > 0
  ))
  const paginatorPosition = computed(() => 'both')

  const filteredAndSortedTasks = computed(() => {
    let result = [...tasks.value]

    if (localFilters.keyword) {
      const keyword = localFilters.keyword.toLowerCase()
      result = result.filter((task) => (
        (task.title && task.title.toLowerCase().includes(keyword))
        || (task.description && task.description.toLowerCase().includes(keyword))
      ))
    }

    if (localFilters.statuses.length > 0) {
      result = result.filter((task) => {
        const phaseGroup = task.phase_group || task.phase || ''
        return localFilters.statuses.includes(phaseGroup)
      })
    }

    if (localFilters.episodes.length > 0) {
      const selectedEpisodes = new Set(localFilters.episodes.map(Number))
      result = result.filter((task) => resolveTaskEpisodes(task).some(episode => selectedEpisodes.has(episode)))
    }

    const { prop, order } = sortModel.value
    const multiplier = order === 'descending' ? -1 : 1
    result.sort((taskA, taskB) => {
      let valueA = prop === 'status'
        ? STATUS_SORT_PRIORITY[taskA.phase_group || taskA.phase] ?? Number.MAX_SAFE_INTEGER
        : taskA[prop]
      let valueB = prop === 'status'
        ? STATUS_SORT_PRIORITY[taskB.phase_group || taskB.phase] ?? Number.MAX_SAFE_INTEGER
        : taskB[prop]

      if (prop === 'added_on') {
        valueA = typeof valueA === 'number' ? valueA : (valueA ? Date.parse(valueA) || 0 : 0)
        valueB = typeof valueB === 'number' ? valueB : (valueB ? Date.parse(valueB) || 0 : 0)
      }

      if (valueA === valueB) return 0
      if (valueA === null || valueA === undefined) return 1
      if (valueB === null || valueB === undefined) return -1
      if (typeof valueA === 'string') return valueA.localeCompare(valueB) * multiplier
      return (valueA - valueB) * multiplier
    })

    return result
  })

  const maxPaginatorFirst = computed(() => {
    const total = filteredAndSortedTasks.value.length
    if (total <= ROWS_PER_PAGE) return 0
    return Math.floor((total - 1) / ROWS_PER_PAGE) * ROWS_PER_PAGE
  })

  function clearFilters() {
    localFilters.keyword = ''
    localFilters.statuses = []
    localFilters.episodes = []
  }

  watch(maxPaginatorFirst, (maxFirst) => {
    if (currentFirst.value <= maxFirst) return
    currentFirst.value = maxFirst
  })

  return {
    currentFirst,
    localFilters,
    sortModel,
    statusOptions,
    sortOptions,
    episodeOptions,
    hasActiveFilters,
    paginatorPosition,
    filteredAndSortedTasks,
    maxPaginatorFirst,
    clearFilters,
    rowsPerPage: ROWS_PER_PAGE,
  }
}

function resolveTaskEpisodes(task) {
  const candidates = [
    task?.selected_episodes,
    task?.attributes?.episodes,
    task?.display_attributes?.episodes,
    task?.task_data?.context?.parsed_attributes?.episodes,
    task?.task_data?.context?.search_result?.attributes?.episodes,
  ]
  const episodes = []
  for (const candidate of candidates) {
    if (!Array.isArray(candidate)) continue
    for (const value of candidate) {
      const episode = Number(value)
      if (Number.isFinite(episode) && episode > 0) episodes.push(episode)
    }
  }
  return [...new Set(episodes)]
}
