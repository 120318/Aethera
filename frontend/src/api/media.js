import http from '@/utils/http'

export const getMediaDetail = async (mediaId, seasonNumber = null) => {
  const params = { media_id: mediaId }
  if (seasonNumber) params.season_number = seasonNumber
  const data = await http.get('/api/v1/media/detail', { params })
  return data.media
}

export const getMediaDetailPage = async ({ mediaId, seasonNumber = null, activeTab = 'resources', source = null, sourceId = null, mediaType = null, title = null, year = null } = {}) => {
  const params = { active_tab: activeTab }
  if (mediaId) params.media_id = mediaId
  if (seasonNumber) params.season_number = seasonNumber
  if (source) params.source = source
  if (sourceId) params.source_id = sourceId
  if (mediaType) params.media_type = mediaType
  if (title) params.title = title
  if (year) params.year = year
  return http.get('/api/v1/media/detail-page', { params })
}

export const getMediaSourceDetail = async ({ source, sourceId, mediaType }) => {
  const data = await http.get('/api/v1/media/detail', {
    params: {
      source,
      source_id: sourceId,
      media_type: mediaType,
    },
  })
  return data.media
}

export const getMediaDetailOverview = async (mediaId, seasonNumber = null) => {
  const params = { media_id: mediaId }
  if (seasonNumber) params.season_number = seasonNumber
  return http.get('/api/v1/media/detail-overview', { params })
}

export const attachMediaTMDBMapping = async (mediaId, tmdbId, seasonNumber = null, episodeCountOverride = null) =>
  http.post('/api/v1/media/external-mapping/tmdb', {
    tmdb_id: tmdbId,
    season_number: seasonNumber,
    episode_count_override: episodeCountOverride,
  }, { params: { media_id: mediaId } })

export const attachSourceTMDBMapping = async ({ source, sourceId, mediaType, tmdbId, seasonNumber = null, episodeCountOverride = null }) =>
  http.post('/api/v1/media/external-mapping/tmdb/source', {
    source,
    source_id: sourceId,
    media_type: mediaType,
    tmdb_id: tmdbId,
    season_number: seasonNumber,
    episode_count_override: episodeCountOverride,
  })

export const refreshMediaProfile = async (mediaId, seasonNumber = null) => {
  const params = { media_id: mediaId }
  if (seasonNumber) params.season_number = seasonNumber
  return (await http.post('/api/v1/media/profile-refresh', {}, { params })).command
}

export const getMediaOperations = (mediaId, seasonNumber = null) => {
  const params = { media_id: mediaId }
  if (seasonNumber) params.season_number = seasonNumber
  return http.get('/api/v1/media/operations', { params })
}

export const searchMedia = (params) =>
  http.get('/api/v1/media/search', { params })

export const searchMediaByEndpoint = (apiEndpoint, params) =>
  http.get(apiEndpoint, { params })
