import { computed, ref, reactive } from 'vue'
import { getMediaDetail, getMediaDetailOverview, getMediaSourceDetail } from '@/api/media'
import { getLibraryList, getTaskList } from '@/api/resource'
import { useI18n } from 'vue-i18n'

export function useMediaDetailData() {
  const { t } = useI18n()
  const loading = ref(true)
  const detail = ref(null)
  const error = ref("")
  
  const tabData = reactive({
    resources: [],
    resourcesTotalEpisodes: 0,
    tasks: [],
    search: []
  })
  const deletedTaskIds = ref(new Set())

  const detailOverview = ref(null)
  const overview = computed(() => detailOverview.value?.summary?.local_resources || null)

  const dataLoaded = reactive({
    resources: false,
    overview: false,
    tasks: false,
    search: false
  })

  function resetSeasonScopedData() {
    detailOverview.value = null
    tabData.resources = []
    tabData.resourcesTotalEpisodes = 0
    tabData.tasks = []
    tabData.search = []
    deletedTaskIds.value = new Set()
    dataLoaded.resources = false
    dataLoaded.overview = false
    dataLoaded.tasks = false
    dataLoaded.search = false
  }

  function applyLibraryData(libraryData = null) {
    tabData.resourcesTotalEpisodes = Number(libraryData?.total_episodes || 0)
    tabData.resources = (libraryData?.resources || []).map(item => ({
      id: item.id,
      file_name: item.file_name || '',
      resource_title: item.resource_title || item.file_name || t('downloadDialog.unknownResource'),
      name: item.resource_title || item.file_name || t('downloadDialog.unknownResource'),
      directory: item.directory || '',
      directory_id: item.directory_id || '',
      directory_name: item.directory_name || '',
      size: Number(item.size || 0),
      created_at: item.created_at || 0,
      attributes: item.attributes || {},
      is_package: !!item.is_package,
      file_count: Number(item.file_count || 1),
      package_root: item.package_root || '',
      actions: Array.isArray(item.actions) ? item.actions : [],
      action_states: Array.isArray(item.action_states) ? item.action_states : [],
      progress: 1,
      state: 'completed',
      is_library_resource: true
    }))
    dataLoaded.resources = true
  }

  function applyTaskData(tasks = []) {
    tabData.tasks = mapTaskData(tasks || [])
      .filter(task => !deletedTaskIds.value.has(task.id))
    dataLoaded.tasks = true
  }

  function applyDetailPageData(payload, activeTab = 'resources') {
    if (!payload) return null
    detail.value = payload.media || null
    detailOverview.value = payload.overview || null
    dataLoaded.overview = true
    if (activeTab === 'tasks' && Array.isArray(payload.tab_data?.tasks)) {
      applyTaskData(payload.tab_data.tasks)
    }
    loading.value = false
    error.value = ''
    return detail.value
  }

  async function fetchDetail(mediaId, seasonNumber = null) {
    if (!mediaId) return
    loading.value = true
    try {
      error.value = ""
      detail.value = await getMediaDetail(mediaId, seasonNumber)
      return detail.value
    } catch (e) {
      error.value = t('mediaDetail.loadDetailFailed')
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchSourceDetail(sourceContext) {
    if (!sourceContext?.source || !sourceContext?.sourceId || !sourceContext?.mediaType) return null
    loading.value = true
    try {
      error.value = ""
      detail.value = await getMediaSourceDetail(sourceContext)
      return detail.value
    } catch (e) {
      error.value = e?.code === 10024 ? t('mediaDetail.tmdbMappingRequired') : t('mediaDetail.loadDetailFailed')
      throw e
    } finally {
      loading.value = false
    }
  }

  async function loadResourceInfo(mediaId, seasonNumber = null) {
    try {
      const libraryData = await getLibraryList(mediaId, seasonNumber)
      applyLibraryData(libraryData)
    } catch (e) {
      console.warn(t('mediaDetail.loadResourcesFailed'), e)
      tabData.resourcesTotalEpisodes = 0
      dataLoaded.resources = true
    }
  }

  async function loadDetailOverview(mediaId, seasonNumber = null) {
    try {
      detailOverview.value = await getMediaDetailOverview(mediaId, seasonNumber)
      dataLoaded.overview = true
    } catch (e) {
      console.warn(t('mediaDetail.loadOverviewFailed'), e)
      detailOverview.value = null
      dataLoaded.overview = true
    }
  }

  async function loadTaskInfo(mediaId, seasonNumber = null) {
    try {
      const data = await getTaskList(mediaId, seasonNumber)
      applyTaskData(data.tasks || [])
    } catch (e) {
      console.warn(t('mediaDetail.loadTasksFailed'), e)
      dataLoaded.tasks = true
    }
  }

  function mapTaskItem(task) {
    const attributes = task.attributes || {}
    const size = Number(task.size || 0)
    const hash = task.torrent_hash || ''
    return {
      id: task.id,
      title: task.title || t('downloadDialog.unknownResource'),
      description: task.description || '',
      attributes,
      selected_season: task.selected_season ?? null,
      selected_episodes: Array.isArray(task.selected_episodes) ? task.selected_episodes : [],
      directory_id: task.directory_id || task.context?.directory_id || '',
      directory_name: task.directory_name || '',
      partial_selection: !!task.partial_selection,
      phase: task.phase || '',
      phase_group: task.phase_group || '',
      phase_label: task.phase_label || '',
      phase_label_key: task.phase_label_key || '',
      attention_reason_key: task.attention_reason_key || '',
      attention_reason_params: task.attention_reason_params || {},
      actions: Array.isArray(task.actions) ? task.actions : [],
      realtime: task.realtime || {},
      active_command_type: task.active_command_type || '',
      active_command_id: task.active_command_id || '',
      task_data: {
        id: task.id,
        status: task.status || '',
        error_stage: task.error_stage || '',
        download_client: task.download_client || '',
        download_client_url: task.download_client_url || '',
        info_hash: hash,
        hash: hash,
        torrent_hash: hash
      },
      progress: task.progress || 0,
      status: task.status || '',
      state: task.realtime?.torrent_state || '',
      added_on: task.created_at || 0,
      size,
      dlspeed: Number(task.realtime?.download_speed || 0),
      upspeed: Number(task.realtime?.upload_speed || 0),
      eta: Number(task.realtime?.eta || 0),
      num_seeds: Number(task.realtime?.num_seeds || 0),
      num_leechs: Number(task.realtime?.num_leechs || 0),
      realtime_unavailable: task.realtime?.available === false,
      info_hash: hash,
      hash: hash,
      torrent_hash: hash,
      download_client: task.download_client || '',
      download_client_url: task.download_client_url || '',
      downloader_id: '',
      save_path: task.save_path || '',
      category: '',
      tracker: task.site || task.indexer || '',
      indexer: task.indexer || '',
      site: task.site || task.indexer || '',
      page_url: task.page_url || '',
      detail_url: task.detail_url || '',
      torrent_url: task.torrent_url || '',
      error_stage: task.error_stage || '',
      error_key: task.error_key || '',
      error_params: task.error_params || {},
      is_library_resource: false
    }
  }

  function replaceTaskItem(task) {
    if (!task?.id) return
    if (deletedTaskIds.value.has(task.id)) return
    const nextTask = mapTaskItem(task)
    const index = tabData.tasks.findIndex((item) => item?.id === task.id)
    if (index === -1) return
    const nextTasks = [...tabData.tasks]
    nextTasks[index] = nextTask
    tabData.tasks = nextTasks
  }

  function markTaskDeleted(taskId) {
    if (!taskId) return
    deletedTaskIds.value = new Set([...deletedTaskIds.value, taskId])
    tabData.tasks = tabData.tasks.filter(task => task?.id !== taskId)
  }

  function setDetailSeasonContext(seasonNumber) {
    const normalized = Number(seasonNumber)
    if (!detail.value || !Number.isInteger(normalized) || normalized <= 0) return
    const selectedSeason = Array.isArray(detail.value.seasons)
      ? detail.value.seasons.find((season) => Number(season?.season_number) === normalized)
      : null
    const selectedDoubanId = selectedSeason?.douban_id || null
    const doubanVoteAverage = selectedSeason?.douban_vote_average ?? null
    const doubanRatingCount = selectedSeason?.douban_rating_count ?? null
    const tmdbVoteAverage = detail.value.tmdb_vote_average ?? (detail.value.rating_source === 'tmdb' ? detail.value.vote_average : null)
    const tmdbRatingCount = detail.value.tmdb_rating_count ?? (detail.value.rating_source === 'tmdb' ? detail.value.rating_count : null)
    const ratingUpdates = selectedDoubanId
      ? {
          vote_average: doubanVoteAverage,
          rating_count: doubanRatingCount,
          vote_count: doubanRatingCount,
          rating_source: 'douban',
        }
      : {
          vote_average: tmdbVoteAverage,
          rating_count: tmdbRatingCount,
          vote_count: tmdbRatingCount,
          rating_source: tmdbVoteAverage != null ? 'tmdb' : null,
        }
    detail.value = {
      ...detail.value,
      season_number: normalized,
      episodes_count: selectedSeason?.episode_count_override ?? selectedSeason?.episode_count ?? detail.value.episodes_count,
      episode_count_override: selectedSeason?.episode_count_override ?? null,
      douban_id: selectedDoubanId,
      ...ratingUpdates,
    }
  }

  function mapTaskData(tasks) {
    return tasks.map((task) => mapTaskItem(task))
  }

  return {
    loading,
    detail,
    error,
    tabData,
    detailOverview,
    overview,
    dataLoaded,
    resetSeasonScopedData,
    applyDetailPageData,
    fetchDetail,
    fetchSourceDetail,
    loadResourceInfo,
    loadDetailOverview,
    loadTaskInfo,
    replaceTaskItem,
    markTaskDeleted,
    setDetailSeasonContext,
  }
}
