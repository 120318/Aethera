import http from '@/utils/http'

export const getObjectConfig = () => http.get('/api/v1/config')
export const getDownloadersTabConfig = () => http.get('/api/v1/config/tab/downloaders')
export const getIndexersTabConfig = () => http.get('/api/v1/config/tab/indexers')
export const getMediaServersTabConfig = () => http.get('/api/v1/config/tab/media-servers')
export const getDirectoriesTabConfig = () => http.get('/api/v1/config/tab/directories')
export const getNamingTabConfig = () => http.get('/api/v1/config/tab/naming')
export const getMetadataTabConfig = () => http.get('/api/v1/config/tab/metadata')
export const getAddonsTabConfig = () => http.get('/api/v1/config/tab/addons')
export const getSystemTabConfig = () => http.get('/api/v1/config/tab/system')
export const getSystemConfig = () => http.get('/api/v1/config/system')
export const getLoggingConfig = () => http.get('/api/v1/config/system/logging')
export const getSchedulerConfig = () => http.get('/api/v1/config/system/scheduler')
export const getAuthConfig = () => http.get('/api/v1/config/auth')
export const getServicesConfig = () => http.get('/api/v1/config/services')
export const getDirectories = () => http.get('/api/v1/config/directories')
export const getAddonsConfig = async () => {
  const data = await http.get('/api/v1/config/addons')
  return data.addons
}

export const saveAuthConfig = (data) => http.post('/api/v1/config/auth', data)

export const testDirectoryAccess = (payload) => http.post('/api/v1/config/test-directory', payload)
export const createDirectory = (directory) => http.post('/api/v1/config/directories/add', directory)
export const updateDirectoryEntry = (directory) => http.put('/api/v1/config/directories/update', directory)
export const deleteDirectoryEntry = (id) => http.delete(`/api/v1/config/directories/delete/${id}`)
export const getDirectoryUsage = (id) => http.get(`/api/v1/config/directories/${id}/usage`)
export const setDefaultDirectoryEntry = (payload) => http.post('/api/v1/config/directories/set-default', payload)
export const previewDirectoryMigration = (id, payload) => http.post(`/api/v1/config/directories/${id}/migration/preview`, payload)
export const submitDirectoryMigration = (id, payload) => http.post(`/api/v1/config/directories/${id}/migration`, payload)
export const getDirectoryIntegrityLatest = () => http.get('/api/v1/config/directories/integrity/latest')
export const scanDirectoryIntegrity = (payload = {}) => http.post('/api/v1/config/directories/integrity/scan', payload)
export const repairDirectoryIntegrity = (payload) => http.post('/api/v1/config/directories/integrity/repair', payload)
export const getDirectoryIntegrityPolicies = () => http.get('/api/v1/config/directories/integrity/policies')
export const saveDirectoryIntegrityPolicies = (payload) => http.put('/api/v1/config/directories/integrity/policies', payload)

export const saveDownloaders = (downloaders) => http.post('/api/v1/config/downloaders', downloaders)
export const createDownloader = (payload) => http.post('/api/v1/config/downloaders', payload)
export const updateDownloader = (id, payload) => http.put(`/api/v1/config/downloaders/${id}`, payload)
export const deleteDownloader = (id) => http.delete(`/api/v1/config/downloaders/${id}`)
export const getDownloaderUsage = (id) => http.get(`/api/v1/config/downloaders/${id}/usage`)
export const setDefaultDownloaderEntry = (id) => http.post(`/api/v1/config/downloaders/set-default/${id}`)
export const clearDefaultDownloader = () => http.post('/api/v1/config/downloaders/clear-default')
export const saveMediaServers = (mediaServers) => http.post('/api/v1/config/media-servers', mediaServers)
export const createMediaServer = (payload) => http.post('/api/v1/config/media-servers', payload)
export const updateMediaServer = (id, payload) => http.put(`/api/v1/config/media-servers/${id}`, payload)
export const deleteMediaServer = (id) => http.delete(`/api/v1/config/media-servers/${id}`)
export const setDefaultMediaServerEntry = (id) => http.post(`/api/v1/config/media-servers/set-default/${id}`)
export const clearDefaultMediaServer = () => http.post('/api/v1/config/media-servers/clear-default')
export const testServiceConnection = (payload) => http.post('/api/v1/config/test-connection', payload)

export const saveAddons = async (addons) => {
  const data = await http.post('/api/v1/config/addons', addons)
  return data.addons
}

export const saveIndexers = (indexers) => http.post('/api/v1/config/indexers', indexers)
export const getIndexerHealth = (indexerId) => http.get('/api/v1/config/indexers/health', indexerId ? { params: { indexer_id: indexerId } } : undefined)
export const getIndexerSites = (indexerId) => http.get('/api/v1/config/indexers/sites', indexerId ? { params: { indexer_id: indexerId } } : undefined)
export const createIndexer = (payload) => http.post('/api/v1/config/indexers', payload)
export const updateIndexer = (id, payload) => http.put(`/api/v1/config/indexers/${id}`, payload)
export const deleteIndexer = (id) => http.delete(`/api/v1/config/indexers/${id}`)
export const reorderIndexers = (payload) => http.put('/api/v1/config/indexers/reorder', payload)

export const previewNamingTemplate = (payload) => http.post('/api/v1/config/preview', payload)
export const createNamingTemplate = (payload) => http.post('/api/v1/config/templates', payload)
export const updateNamingTemplate = (payload) => http.put('/api/v1/config/templates', payload)
export const deleteNamingTemplate = (id) => http.delete(`/api/v1/config/templates/${id}`)
export const setDefaultNamingTemplate = (payload) => http.post('/api/v1/config/templates/set-default', payload)
export const clearDefaultNamingTemplate = (payload) => http.post('/api/v1/config/templates/clear-default', payload)

export const saveSystemConfig = (data) => http.post('/api/v1/config/system', data)
export const saveDownloadConfig = (data) => http.post('/api/v1/config/system/download', data)
export const saveLoggingConfig = (data) => http.post('/api/v1/config/system/logging', data)
export const saveSchedulerConfig = (data) => http.post('/api/v1/config/system/scheduler', data)

export const saveServicesConfig = (data) => http.post('/api/v1/config/services', data)
export const saveTMDBConfig = (data) => http.post('/api/v1/config/services/tmdb', data)
export const saveDoubanConfig = (data) => http.post('/api/v1/config/services/douban', data)
export const saveBrowseSource = (source) => http.post('/api/v1/config/services/browse-source', source)
