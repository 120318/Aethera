import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'
import { DEFAULT_RESOURCE_TAGS, ResourceTagType } from '@/constants/resourceTagTypes'
import { useI18n } from 'vue-i18n'

export const useResourceTags = () => {
  const { t } = useI18n()
  const getSortedTags = (resource, options = {}) => {
    if (!resource) return []

    const visibleTagSet = new Set(options.visibleTags || DEFAULT_RESOURCE_TAGS)
    const tags = []
    const pushTag = (type, tag) => {
      if (!visibleTagSet.has(type)) return
      tags.push({ ...tag, type })
    }

    if (resource.resource?.matched_by_id === false) {
      const matchedUnmatchedRule = resource.resource?.matched_unmatched_rule === true
      pushTag(ResourceTagType.UNMATCHED, {
        value: '!',
        tone: matchedUnmatchedRule ? 'success' : 'warn',
        icon: null,
        priority: 0,
        tooltip: matchedUnmatchedRule
          ? t('resourceTags.unmatchedRuleTooltip')
          : t('resourceTags.unmatchedTitleTooltip'),
      })
    }

    if (resource.resource?.directory) {
      pushTag(ResourceTagType.DIRECTORY, {
        value: resource.resource.directory,
        tone: 'neutral',
        icon: 'pi pi-folder',
        priority: 0
      })
    }

    if (resource.resource?.seeders !== undefined) {
      pushTag(ResourceTagType.SEEDERS, {
        value: resource.resource.seeders || '0',
        tone: getSeederTone(resource.resource.seeders),
        icon: 'pi pi-users',
        priority: 1
      })
    }

    if (resource.resource?.publish_date) {
      pushTag(ResourceTagType.PUBLISH_DATE, {
        value: formatRelativeDateLabel(resource.resource.publish_date),
        tone: 'neutral',
        icon: 'pi pi-clock',
        priority: 1,
        tooltip: formatAbsoluteDateLabel(resource.resource.publish_date),
      })
    }

    if (resource.resource?.created_at) {
      pushTag(ResourceTagType.CREATED_AT, {
        value: formatRelativeDateLabel(resource.resource.created_at),
        tone: 'neutral',
        icon: 'pi pi-clock',
        priority: 1,
        tooltip: formatAbsoluteDateLabel(resource.resource.created_at),
      })
    }

    const freeTag = formatFreeTag(resource.resource)
    if (freeTag) {
      pushTag(ResourceTagType.FREE, {
        value: freeTag.value,
        tone: freeTag.tone,
        icon: 'pi pi-gift',
        priority: 1
      })
    }

    if (resource.attributes) {
      const displayAttributes = resource.displayAttributes || resource.attributes
      const baseAttributes = resource.attributes
      const seasonTooltip = buildCoverageTooltip('season', baseAttributes?.seasons, displayAttributes?.seasons)
      const episodeTooltip = buildCoverageTooltip('episode', baseAttributes?.episodes, displayAttributes?.episodes)

      const seasons = displayAttributes.seasons || (displayAttributes.season ? [displayAttributes.season] : [])
      if (seasons && seasons.length > 0) {
        const seasonLabels = formatSeasonLabels(seasons)
        seasonLabels.forEach(label => {
          pushTag(ResourceTagType.SEASON, {
            value: label,
            tone: 'accent',
            icon: null,
            priority: 2,
            tooltip: seasonTooltip,
          })
        })
      }

      if (displayAttributes.episodes && displayAttributes.episodes.length > 0) {
        const episodeLabels = formatEpisodeLabels(displayAttributes.episodes)
        episodeLabels.forEach(label => {
          pushTag(ResourceTagType.EPISODE, {
            value: label,
            tone: 'accent',
            icon: null,
            priority: 2,
            tooltip: episodeTooltip,
          })
        })
      }

      const discLabel = formatDiscLabel(displayAttributes.disc_number, displayAttributes.disc_total)
      if (discLabel) {
        pushTag(ResourceTagType.DISC, {
          value: discLabel,
          tone: 'accent',
          icon: null,
          priority: 2,
        })
      }
    }

    if (resource.attributes) {
      if (resource.attributes.resolution) {
        pushTag(ResourceTagType.RESOLUTION, {
          value: resource.attributes.resolution,
          tone: getResolutionTone(resource.attributes.resolution),
          icon: null,
          priority: 3
        })
      }

      if (resource.attributes.video_codec) {
        pushTag(ResourceTagType.VIDEO_CODEC, {
          value: resource.attributes.video_codec,
          tone: 'neutral',
          icon: null,
          priority: 3
        })
      }

      if (resource.attributes.audio_codec) {
        pushTag(ResourceTagType.AUDIO_CODEC, {
          value: resource.attributes.audio_codec,
          tone: 'neutral',
          icon: null,
          priority: 3
        })
      }
      if (resource.attributes.hdr_type) {
        pushTag(ResourceTagType.HDR_TYPE, {
          value: resource.attributes.hdr_type,
          tone: getHdrTypeTone(resource.attributes.hdr_type),
          icon: null,
          priority: 3
        })
      }

      if (resource.attributes.audio_channels) {
        pushTag(ResourceTagType.AUDIO_CHANNELS, {
          value: resource.attributes.audio_channels,
          tone: 'neutral',
          icon: null,
          priority: 3
        })
      }

      if (resource.attributes.color_depth) {
        pushTag(ResourceTagType.COLOR_DEPTH, {
          value: resource.attributes.color_depth,
          tone: 'neutral',
          icon: null,
          priority: 3
        })
      }
    }

    if (resource.attributes) {
      if (resource.attributes.groups && resource.attributes.groups.length > 0) {
        resource.attributes.groups.forEach(group => {
          pushTag(ResourceTagType.GROUP, {
            value: group,
            tone: 'neutral',
            icon: null,
            priority: 4
          })
        })
      }

      const displaySources = filterRedundantSources(resource.attributes.sources, resource.attributes.resource_form)
      if (displaySources.length > 0) {
        displaySources.forEach(source => {
          pushTag(ResourceTagType.SOURCE, {
            value: source,
            tone: 'neutral',
            icon: null,
            priority: 4
          })
        })
      }

      const resourceFormLabel = formatResourceFormLabel(resource.attributes.resource_form, t)
      if (resourceFormLabel) {
        pushTag(ResourceTagType.RESOURCE_FORM, {
          value: resourceFormLabel,
          tone: 'accent',
          icon: null,
          priority: 4,
        })
      }

      if (resource.attributes.package_layout) {
        pushTag(ResourceTagType.PACKAGE_LAYOUT, {
          value: resource.attributes.package_layout,
          tone: 'neutral',
          icon: null,
          priority: 4,
        })
      }

      if (resource.attributes.versions && resource.attributes.versions.length > 0) {
        resource.attributes.versions.forEach(version => {
          pushTag(ResourceTagType.VERSION, {
            value: version,
            tone: 'neutral',
            icon: null,
            priority: 4
          })
        })
      }

      if (resource.attributes.language) {
        pushTag(ResourceTagType.LANGUAGE, {
          value: resource.attributes.language,
          tone: 'neutral',
          icon: null,
          priority: 4
        })
      }

      if (resource.attributes.subtitle) {
        pushTag(ResourceTagType.SUBTITLE, {
          value: resource.attributes.subtitle,
          tone: 'warn',
          icon: null,
          priority: 4
        })
      }

      if (Array.isArray(resource.attributes.tags) && resource.attributes.tags.length > 0) {
        resource.attributes.tags.forEach(tag => {
          pushTag(ResourceTagType.TAG, {
            value: tag,
            tone: 'accent',
            icon: null,
            priority: 4
          })
        })
      }
    }

    if (resource.resource?.size) {
      pushTag(ResourceTagType.SIZE, {
        value: resource.resource.size,
        tone: getSizeTone(resource.resource.size),
        icon: null,
        priority: 4
      })
    }

    if (resource.resource?.site) {
      const siteLabel = resource.resource.site_name || resource.resource.site
      const indexerLabel = resource.resource.indexer_name || resource.resource.indexer_id || ''
      pushTag(ResourceTagType.SITE, {
        value: indexerLabel ? `${indexerLabel} / ${siteLabel}` : siteLabel,
        tone: 'neutral',
        icon: null,
        priority: 4,
        tooltip: indexerLabel ? t('resourceTags.indexerSiteTooltip', { indexer: indexerLabel, site: siteLabel }) : null,
      })
    }

    // Case-insensitive deduplication.
    const uniqueTags = []
    const seenValues = new Set()

    tags.forEach(tag => {
      if (!tag.value) return
      const key = String(tag.value).toLowerCase().trim()
      if (!seenValues.has(key)) {
        seenValues.add(key)
        uniqueTags.push(tag)
      }
    })

    // Lower priority numbers are shown first.
    return uniqueTags.sort((a, b) => a.priority - b.priority)
  }

  const getSeederTone = (seeders) => {
    const count = parseInt(seeders) || 0
    if (count <= 5) return 'danger'
    if (count <= 20) return 'warn'
    return 'success'
  }

  const getResolutionTone = (resolution) => {
    if (!resolution) return 'neutral'
    return 'accent'
  }

  const getSizeTone = (size) => {
    if (!size) return 'neutral'
    const str = String(size).toUpperCase()
    const num = parseFloat(str)
    if (isNaN(num)) return 'neutral'
    if (str.includes('TB') || str.includes('TIB')) return 'danger'
    if (str.includes('GB') || str.includes('GIB')) return num >= 20 ? 'warn' : 'neutral'
    return 'neutral'
  }

  const getHdrTypeTone = (hdrType) => {
    if (!hdrType) return 'neutral'
    const up = hdrType.toUpperCase()
    if (up.includes('DV') || up.includes('DOLBY')) return 'warn'
    if (up.includes('HDR')) return 'warn'
    return 'neutral'
  }

  const formatFreeTag = (resourceInfo) => {
    const downloadFactor = toNumber(resourceInfo?.download_volume_factor)
    const uploadFactor = toNumber(resourceInfo?.upload_volume_factor)
    if (downloadFactor === null) return null
    if (downloadFactor === 0) {
      if (uploadFactor !== null && uploadFactor >= 2) {
        return { value: t('resourceTags.doubleFree'), tone: 'success' }
      }
      return { value: t('resourceTags.free'), tone: 'success' }
    }
    if (downloadFactor > 0 && downloadFactor < 1) {
      const percent = Math.round(downloadFactor * 100)
      return { value: `${percent}%`, tone: 'accent' }
    }
    return null
  }

  const toNumber = (value) => {
    if (value === undefined || value === null || value === '') return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  const formatSeasonLabels = (seasons) => {
    if (!seasons || !seasons.length) return []

    const seasonNumbers = seasons.map(s => parseInt(s)).filter(n => !isNaN(n)).sort((a, b) => a - b)

    if (seasonNumbers.length === 0) return []

    const min = Math.min(...seasonNumbers)
    const max = Math.max(...seasonNumbers)
    const isConsecutive = seasonNumbers.length === (max - min + 1) &&
      seasonNumbers.every((num, index) => num === min + index)

    if (isConsecutive && seasonNumbers.length > 1) {
      return [`S${min}-S${max}`]
    }

    return seasons.slice(0, 3).map(s => `S${s}`)
  }

  const formatAbsoluteDateLabel = (value) => {
    if (!value) return ''
    const formatted = formatAbsoluteDateTime(value)
    if (formatted === '-') return String(value)
    return formatted
  }

  const formatRelativeDateLabel = (value) => {
    if (!value) return ''
    const formatted = formatRelativeTime(value)
    if (formatted === '-') return formatAbsoluteDateLabel(value)
    return formatted
  }

  const formatEpisodeLabels = (episodes) => {
    if (!episodes || !episodes.length) return []

    const episodeNumbers = episodes.map(e => parseInt(e)).filter(n => !isNaN(n)).sort((a, b) => a - b)

    if (episodeNumbers.length === 0) return []

    const min = Math.min(...episodeNumbers)
    const max = Math.max(...episodeNumbers)
    const isConsecutive = episodeNumbers.length === (max - min + 1) &&
      episodeNumbers.every((num, index) => num === min + index)

    if (isConsecutive && episodeNumbers.length > 1) {
      return [`E${min}-E${max}`]
    }

    return episodes.slice(0, 3).map(e => `E${e}`)
  }

  const formatDiscLabel = (discNumber, discTotal) => {
    const normalizedDiscNumber = Number(discNumber)
    const normalizedDiscTotal = Number(discTotal)
    if (!Number.isInteger(normalizedDiscNumber) || normalizedDiscNumber <= 0) {
      return Number.isInteger(normalizedDiscTotal) && normalizedDiscTotal > 0 ? t('resourceTags.discCount', { count: normalizedDiscTotal }) : ''
    }

    if (Number.isInteger(normalizedDiscTotal) && normalizedDiscTotal >= normalizedDiscNumber) {
      return t('resourceTags.discProgress', { number: normalizedDiscNumber, total: normalizedDiscTotal })
    }
    return t('resourceTags.discNumber', { number: normalizedDiscNumber })
  }

  const buildCoverageTooltip = (label, fullValues, selectedValues) => {
    if (!Array.isArray(fullValues) || !fullValues.length || !Array.isArray(selectedValues) || !selectedValues.length) {
      return ''
    }
    const fullNumbers = fullValues.map(value => parseInt(value)).filter(value => !isNaN(value)).sort((a, b) => a - b)
    const selectedNumbers = selectedValues.map(value => parseInt(value)).filter(value => !isNaN(value)).sort((a, b) => a - b)
    if (!fullNumbers.length || !selectedNumbers.length) return ''
    if (fullNumbers.length === selectedNumbers.length && fullNumbers.every((value, index) => value === selectedNumbers[index])) {
      return ''
    }
    const formatter = label === 'season' ? formatSeasonLabels : formatEpisodeLabels
    const labelText = label === 'season' ? t('resourceTags.season') : t('resourceTags.episode')
    return t('resourceTags.coverageTooltip', { label: labelText, values: formatter(fullNumbers).join(', ') })
  }

  return {
    getSortedTags,
  }
}

function formatResourceFormLabel(value, t) {
  const labels = {
    'BluRay Disc': t('resourceKind.blurayDisc'),
    'DVD Disc': t('resourceKind.dvdDisc'),
  }
  return labels[value] || ''
}

function filterRedundantSources(sources, resourceForm) {
  if (!Array.isArray(sources) || !sources.length) return []
  if (resourceForm === 'BluRay Disc') {
    return sources.filter(source => source !== 'BluRay' && source !== 'UHD BluRay')
  }
  if (resourceForm === 'DVD Disc') {
    return sources.filter(source => source !== 'DVD')
  }
  return sources
}
