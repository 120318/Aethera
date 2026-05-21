import {
  QUALITY_AUDIO_CODEC_VALUES,
  QUALITY_AUDIO_CHANNEL_VALUES,
  QUALITY_HDR_TYPE_VALUES,
  QUALITY_RESOURCE_FORM_VALUES,
  QUALITY_RESOLUTION_VALUES,
  QUALITY_SOURCE_VALUES,
  QUALITY_VIDEO_CODEC_VALUES,
} from '@/constants/qualityOptions'

export const qualityRankingDimensionOptions = [
  { key: 'resolution', labelKey: 'settings.quality.dimensions.resolution' },
  { key: 'source', labelKey: 'settings.quality.dimensions.source' },
  { key: 'resource_form', labelKey: 'settings.quality.dimensions.resourceForm' },
  { key: 'hdr_type', labelKey: 'settings.quality.dimensions.hdrType' },
  { key: 'video_codec', labelKey: 'settings.quality.dimensions.videoCodec' },
  { key: 'audio_codec', labelKey: 'settings.quality.dimensions.audioCodec' },
  { key: 'audio_channels', labelKey: 'settings.quality.dimensions.audioChannels' },
]

export function buildQualityRankingDimensionOptions(t) {
  return qualityRankingDimensionOptions.map((item) => ({
    ...item,
    label: item.labelKey ? t(item.labelKey) : item.key,
  }))
}

export const qualityRankingDefaultState = {
  dimension_order: qualityRankingDimensionOptions.map((item) => item.key),
  resolution: [...QUALITY_RESOLUTION_VALUES],
  source: [...QUALITY_SOURCE_VALUES],
  resource_form: [...QUALITY_RESOURCE_FORM_VALUES],
  hdr_type: [...QUALITY_HDR_TYPE_VALUES],
  video_codec: [...QUALITY_VIDEO_CODEC_VALUES],
  audio_codec: [...QUALITY_AUDIO_CODEC_VALUES],
  audio_channels: [...QUALITY_AUDIO_CHANNEL_VALUES.filter((value) => value !== '1.0')],
}

export function cloneQualityRanking(value) {
  const source = JSON.parse(JSON.stringify(value || {}))
  const next = {}
  Object.keys(qualityRankingDefaultState).forEach((key) => {
    next[key] = Array.isArray(source[key]) ? [...source[key]] : [...qualityRankingDefaultState[key]]
  })
  const knownDimensions = new Set(qualityRankingDimensionOptions.map((item) => item.key))
  const ordered = Array.isArray(source.dimension_order)
    ? source.dimension_order.filter((key) => knownDimensions.has(key))
    : []
  for (const key of qualityRankingDefaultState.dimension_order) {
    if (!ordered.includes(key)) ordered.push(key)
  }
  next.dimension_order = ordered
  return next
}

export function syncQualityRankingState(target, value) {
  const next = cloneQualityRanking(value)
  Object.keys(qualityRankingDefaultState).forEach((key) => {
    target[key] = Array.isArray(next[key]) ? [...next[key]] : [...qualityRankingDefaultState[key]]
  })
}

export function moveArrayItem(items, index, direction) {
  const target = direction === 'up' ? index - 1 : index + 1
  if (target < 0 || target >= items.length) return
  const next = [...items]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  return next
}
