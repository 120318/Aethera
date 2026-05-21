function normalizeTitle(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeYear(value) {
  const numeric = Number(value)
  return Number.isInteger(numeric) && numeric > 0 ? numeric : null
}

export function parseMediaId(value) {
  const mediaId = String(value || '').trim()
  if (!mediaId) return null

  const parts = mediaId.split(':')
  if (parts.length < 3) return null

  const [provider, mediaType, rawId] = parts
  if (!provider || !rawId || (mediaType !== 'movie' && mediaType !== 'tv')) {
    return null
  }

  if (parts.length !== 3) return null

  return {
    provider,
    media_type: mediaType,
    id: rawId,
    media_id: mediaId,
  }
}

export function buildStrictMediaIdentity(input) {
  const mediaId = String(input?.media_id || input?.id || '').trim()
  const title = normalizeTitle(input?.title)
  const year = normalizeYear(input?.year)
  const seasonNumber = normalizeYear(input?.season_number ?? input?.seasonNumber)
  const mediaType = input?.media_type || input?.mediaType || parseMediaId(mediaId)?.media_type

  if (!mediaId || !title || year === null) {
    return null
  }

  const identity = {
    media_id: mediaId,
    title,
    year,
  }
  if (mediaType === 'tv' && seasonNumber !== null) {
    identity.season_number = seasonNumber
  }
  return identity
}

export function buildMediaExecutionSnapshot(input) {
  const media = buildStrictMediaIdentity(input)
  if (!media) return null

  const imdbId = typeof input?.imdb_id === 'string' ? input.imdb_id.trim() : (typeof input?.imdbId === 'string' ? input.imdbId.trim() : '')
  const doubanId = typeof input?.douban_id === 'string' ? input.douban_id.trim() : (typeof input?.doubanId === 'string' ? input.doubanId.trim() : '')
  const tmdbId = normalizeYear(input?.tmdb_id ?? input?.tmdbId)
  const seasonsCount = normalizeYear(input?.seasons_count ?? input?.seasonsCount)
  const episodesCount = normalizeYear(input?.episodes_count ?? input?.episodesCount)
  const airedEpisodeCount = normalizeYear(input?.aired_episode_count ?? input?.airedEpisodeCount)

  if (imdbId) media.imdb_id = imdbId
  if (doubanId) media.douban_id = doubanId
  if (tmdbId !== null) media.tmdb_id = tmdbId
  if (seasonsCount !== null) media.seasons_count = seasonsCount
  if (episodesCount !== null) media.episodes_count = episodesCount
  media.aired_episode_count = airedEpisodeCount !== null ? airedEpisodeCount : 0
  return media
}

export function mediaTargetKey(input) {
  const target = buildMediaTarget(input)
  if (!target) return ''
  return `${target.media_id}:${target.season_number || ''}`
}

export function buildMediaTarget(input) {
  const mediaId = String(input?.media_id || input?.mediaId || input?.id || '').trim()
  if (!mediaId) return null

  const seasonNumber = normalizeYear(input?.season_number ?? input?.seasonNumber)
  const mediaType = input?.media_type || input?.mediaType || parseMediaId(mediaId)?.media_type
  if (mediaType === 'tv' && seasonNumber === null) return null
  const target = { media_id: mediaId }
  if (mediaType === 'tv' && seasonNumber !== null) {
    target.season_number = seasonNumber
  }
  return target
}

export function requireMediaTarget(input, message = t('mediaIdentity.targetIncomplete')) {
  const target = buildMediaTarget(input)
  if (!target) {
    throw new Error(message)
  }
  return target
}

export function requireStrictMediaIdentity(input, message = t('mediaIdentity.infoIncomplete')) {
  const media = buildStrictMediaIdentity(input)
  if (!media) {
    throw new Error(message)
  }
  return media
}

export function requireMediaExecutionSnapshot(input, message = t('mediaIdentity.executionIncomplete')) {
  const media = buildMediaExecutionSnapshot(input)
  if (!media) {
    throw new Error(message)
  }
  return media
}
import { t } from '@/i18n'
