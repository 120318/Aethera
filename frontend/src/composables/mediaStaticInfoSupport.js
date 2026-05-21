import { resolveMediaImageUrl } from '@/utils/mediaImage'

function formatDate(value) {
  return String(value || '').slice(0, 10)
}

function formatDurationLabel(value, mediaType, t) {
  if (!value) return ''
  const digits = String(value).match(/\d+/)?.[0]
  if (!digits) return String(value)
  if (mediaType === 'tv') return t('mediaStaticInfo.episodeDuration', { minutes: digits })
  return t('mediaStaticInfo.duration', { minutes: digits })
}

export function resolveMediaTypeInfo(type, t) {
  if (type === 'movie') return { label: t('mediaManagement.mediaType.movie'), icon: 'pi pi-video' }
  if (type === 'tv') return { label: t('mediaManagement.mediaType.tv'), icon: 'pi pi-desktop' }
  return null
}

export function resolveMediaTypeCardClass(type) {
  if (type === 'tv') return 'ui-panel-media-tv'
  if (type === 'movie') return 'ui-panel-media-movie'
  return ''
}

export function buildVendorLinks(detail) {
  const links = []
  const seen = new Set()

  const pushLink = (name, url, logo) => {
    const normalizedName = (name || '').trim().toLowerCase()
    const normalizedUrl = (url || '').trim()
    const key = normalizedUrl || normalizedName
    if (!normalizedName || !normalizedUrl || seen.has(key)) return
    seen.add(key)
    links.push({ key, name, url: normalizedUrl, logo })
  }

  if (detail?.douban_id) {
    pushLink('Douban', `https://movie.douban.com/subject/${detail.douban_id}/`, '/icons/douban.svg')
  }
  if (detail?.imdb_id) {
    pushLink('IMDb', `https://www.imdb.com/title/${detail.imdb_id}/`, '/icons/imdb.svg')
  }
  if (detail?.tmdb_id) {
    const mediaType = detail?.media_type || detail?.type || 'movie'
    pushLink('TMDB', `https://www.themoviedb.org/${mediaType}/${detail.tmdb_id}`, '/icons/tmdb.svg')
  }

  return links
}

export function buildDetailTags(detail, mediaTypeInfo, t) {
  const tags = []
  if (mediaTypeInfo) {
    tags.push({
      key: 'media-type',
      label: mediaTypeInfo.label,
      icon: mediaTypeInfo.icon,
      tone: 'accent',
    })
  }

  const mediaType = detail?.media_type || detail?.type

  const directorNames = Array.isArray(detail?.directors)
    ? detail.directors.map((person) => person?.name).filter(Boolean)
    : []
  if (directorNames.length > 0) {
    tags.push({
      key: 'directors',
      label: t('mediaStaticInfo.directors', { names: directorNames.slice(0, 2).join(' / ') }),
    })
  }

  const genres = Array.isArray(detail?.genres) ? detail.genres.filter(Boolean) : []
  if (genres.length > 0) {
    tags.push({
      key: 'genres',
      label: genres.slice(0, 3).join(' / '),
    })
  }

  const primaryDate = mediaType === 'tv'
    ? detail?.first_air_date
    : detail?.release_date
  if (primaryDate) {
    tags.push({
      key: 'date',
      label: t(mediaType === 'tv' ? 'mediaStaticInfo.firstAirDate' : 'mediaStaticInfo.releaseDate', {
        date: formatDate(primaryDate),
      }),
    })
  }

  const durationLabel = formatDurationLabel(detail?.duration, mediaType, t)
  if (durationLabel) {
    tags.push({
      key: 'duration',
      label: durationLabel,
    })
  }

  return tags
}

export function proxyMediaImage(url) {
  return resolveMediaImageUrl(url)
}

export function getRateColorClass(rate) {
  if (!rate) return 'bg-rate-none'
  if (rate >= 7.5) return 'bg-rate-high'
  if (rate >= 6.0) return 'bg-rate-medium'
  return 'bg-rate-low'
}

export function getRateTextClass(rate) {
  if (!rate || rate < 6.0) return 'text-white'
  return 'text-black'
}

export function formatCharacter(character) {
  if (!character) return ''
  return character.replace(/^text\s*/, '').replace(/^as\s+/i, '')
}
