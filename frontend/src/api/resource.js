import http from '@/utils/http'

export const getLibraryList = (mediaId, seasonNumber = null) =>
  http.get('/api/v1/library/list', {
    params: {
      media_id: mediaId,
      ...(seasonNumber ? { season_number: seasonNumber } : {}),
    }
  })

export const getLibraryOverview = (mediaId) =>
  http.get('/api/v1/library/overview', {
    params: {
      media_id: mediaId,
    }
  })

export const getTaskList = (mediaId, seasonNumber = null) =>
  http.get('/api/v1/task/list', {
    params: {
      media_id: mediaId,
      ...(seasonNumber ? { season_number: seasonNumber } : {}),
    }
  })

export const getTaskDetail = (taskId) =>
  http.get('/api/v1/task/detail', { params: { task_id: taskId } })

export const getTorrentProgress = (taskIds) =>
  http.post('/api/v1/task/torrent_progress', { task_ids: taskIds })

export const syncFinishedTask = (taskId) =>
  http.post('/api/v1/task/sync_finished', { task_id: taskId })

export const pauseTasks = (taskIds) =>
  http.post('/api/v1/task/pause', { task_ids: taskIds })

export const resumeTasks = (taskIds) =>
  http.post('/api/v1/task/resume', { task_ids: taskIds })

export const checkTaskDelete = (taskId) =>
  http.post('/api/v1/task/delete/check', { task_id: taskId })

export const deleteTask = (payload) =>
  http.post('/api/v1/task/delete', payload)

export const previewTaskDownloaderChange = (taskId, payload) =>
  http.post(`/api/v1/task/${taskId}/downloader-change/preview`, payload)

export const changeTaskDownloader = (taskId, payload) =>
  http.post(`/api/v1/task/${taskId}/downloader-change`, payload)

export const downloadResource = (payload) =>
  http.post('/api/v1/resource/download', payload)

export const downloadPilotEpisode = (payload) =>
  http.post('/api/v1/resource/pilot_episode', payload)

export const deleteResource = (payload) =>
  http.post('/api/v1/resource/delete', payload)

export const deleteResourceByHash = (hash, data) =>
  http.delete(`/api/v1/resource/${hash}`, { data })

export const transferResource = (taskId) =>
  http.post('/api/v1/resource/transfer', { task_id: taskId })

export const deleteLibraryFile = (fileId, target, force = false) =>
  http.post('/api/v1/library/file/delete', { file_id: fileId, target, force })

export const getLibraryFileDetail = (fileId) =>
  http.get('/api/v1/library/file/detail', { params: { file_id: fileId } })

export const previewLibraryFileDirectoryChange = (payload) =>
  http.post('/api/v1/library/file/directory-change/preview', payload)

export const submitLibraryFileDirectoryChange = (payload) =>
  http.post('/api/v1/library/file/directory-change', payload)

export const resolveLibraryMediaServerLink = (payload) =>
  http.post('/api/v1/library/media-server/link/resolve', payload)

let resourceSitesCache = null
let resourceSitesPromise = null

export const getResourceSites = async ({ force = false } = {}) => {
  if (!force && resourceSitesCache) return resourceSitesCache
  if (!force && resourceSitesPromise) return resourceSitesPromise
  resourceSitesPromise = http.get('/api/v1/resource/sites')
    .then((payload) => {
      const result = Array.isArray(payload?.sites)
        ? { sites: payload.sites }
        : { sites: Array.isArray(payload?.data?.sites) ? payload.data.sites : [] }
      resourceSitesCache = result
      return result
    })
    .finally(() => {
      resourceSitesPromise = null
    })
  return resourceSitesPromise
}

export const clearResourceSitesCache = () => {
  resourceSitesCache = null
  resourceSitesPromise = null
}

export const searchResources = (params) =>
  http.get('/api/v1/resource/search', { params })
