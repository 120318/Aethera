export function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

export function addDays(date, days) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days)
}

export function toLocalDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

export function startOfWeek(date) {
  const value = startOfDay(date)
  return addDays(value, -value.getDay())
}

function airingDateMatches(airing, dayDate) {
  if (!airing?.date) return false
  const airDate = new Date(`${airing.date}T00:00:00`)
  return airDate.toDateString() === dayDate.toDateString()
}

export function groupCalendarAiringsForDate(airings, dayDate, t) {
  const rawAirings = (Array.isArray(airings) ? airings : []).filter((airing) => airingDateMatches(airing, dayDate))
  const groups = {}

  rawAirings.forEach((airing) => {
    const groupKey = airing.media_type === 'tv'
      ? `tv:${airing.media_id}:${airing.season_number || ''}`
      : `movie:${airing.media_id}:${airing.kind}`

    if (!groups[groupKey]) {
      groups[groupKey] = {
        ...airing,
        episodes: airing.media_type === 'tv' && airing.episode_number ? [airing.episode_number] : []
      }
      return
    }

    if (airing.media_type === 'tv' && airing.episode_number) {
      groups[groupKey].episodes.push(airing.episode_number)
    }
  })

  return Object.values(groups).map((group) => {
    if (group.media_type !== 'tv') return group

    const sortedEpisodes = [...new Set(group.episodes)].sort((a, b) => a - b)
    const start = sortedEpisodes[0]
    const end = sortedEpisodes[sortedEpisodes.length - 1]
    const seasonPrefix = group.season_number ? t('calendar.seasonLabel', { number: group.season_number }) : ''
    return {
      ...group,
      episode_display: start === end
        ? `${seasonPrefix}${t('calendar.episodeLabel', { number: start })}`
        : `${seasonPrefix}${t('calendar.episodeRangeLabel', { start, end })}`
    }
  })
}

export function buildCalendarAiringKey(airing) {
  return [
    airing.kind,
    airing.media_id,
    airing.date,
    airing.season_number,
    airing.episode_number,
  ].filter(Boolean).join(':')
}

export function buildCalendarAiringRoute(airing) {
  return {
    name: 'MediaDetail',
    params: { mediaId: airing.media_id },
    query: airing.media_type === 'tv' && airing.season_number ? { season: airing.season_number } : {}
  }
}

export function buildCalendarAiringMetaText(airing, t) {
  if (airing.media_type === 'tv') {
    return airing.episode_display
  }
  if (airing.kind === 'movie_digital_release') {
    return t('calendar.digitalRelease')
  }
  if (airing.kind === 'movie_physical_release') {
    return t('calendar.physicalRelease')
  }
  return t('calendar.theatricalRelease')
}

export function buildTodayUpdateLabel(airing, t) {
  if (airing.media_type === 'tv') return t('discover.todayUpdates.updateLabel')
  if (airing.kind === 'movie_digital_release') return t('discover.todayUpdates.onlineLabel')
  return t('discover.todayUpdates.releaseLabel')
}

export function buildTodayUpdateMedia(airing, t) {
  return {
    ...airing,
    media_id: airing.media_id,
    media_type: airing.media_type,
    poster_path: airing.poster,
    title: airing.title,
    year: airing.year,
    vote_average: airing.vote_average,
    vote_count: airing.vote_count,
    rating_count: airing.rating_count,
    rating_source: airing.rating_source,
    subtitle_line1: buildTodayUpdateLabel(airing, t),
    subtitle_line2: buildCalendarAiringMetaText(airing, t),
    overview: '',
  }
}
