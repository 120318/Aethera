import { t } from '@/i18n'

export const QUALITY_RESOLUTION_VALUES = ['2160p', '1440p', '1080p', '720p', '576p', '480p']
export const QUALITY_SOURCE_VALUES = ['REMUX', 'UHD BluRay', 'BluRay', 'HDTV', 'WEB-DL', 'WEBRip', 'DVD', 'DVDRip', 'HDCAM', 'R5', 'TC', 'TS', 'CAM']
export const QUALITY_RESOURCE_KIND_VALUES = ['video_file', 'original_disc']
export const buildQualityResourceKindOptions = () => [
  { label: t('quality.resourceKind.videoFile'), value: 'video_file' },
  { label: t('quality.resourceKind.originalDisc'), value: 'original_disc' },
]
export const qualityResourceKindOptions = buildQualityResourceKindOptions()
export const QUALITY_RESOURCE_FORM_VALUES = ['BluRay Disc', 'Video File', 'DVD Disc']
export const RESOURCE_FORMS_BY_KIND = {
  video_file: ['Video File'],
  original_disc: ['BluRay Disc', 'DVD Disc'],
}
export const QUALITY_VIDEO_CODEC_VALUES = ['AV1', 'HEVC', 'AVC']
export const QUALITY_HDR_TYPE_VALUES = ['Dolby Vision', 'HDR10+', 'HDR10']
export const QUALITY_AUDIO_CODEC_VALUES = ['FLAC', 'Dolby Atmos', 'DTS-X', 'TrueHD', 'DTS-HD MA', 'DTS-HD', 'DTS', 'DDP', 'AC3', 'AAC']
export const QUALITY_AUDIO_CHANNEL_VALUES = ['7.1', '5.1', '2.0', '1.0']
export const QUALITY_COLOR_DEPTH_VALUES = ['12bit', '10bit', '8bit']

export function asSelectOptions(values) {
  return values.map((value) => ({ label: value, value }))
}

export const qualityResolutionOptions = asSelectOptions(QUALITY_RESOLUTION_VALUES)
export const qualitySourceOptions = asSelectOptions(QUALITY_SOURCE_VALUES)
export const qualityResourceFormOptions = asSelectOptions(QUALITY_RESOURCE_FORM_VALUES)
export const qualityVideoCodecOptions = asSelectOptions(QUALITY_VIDEO_CODEC_VALUES)
export const qualityHdrTypeOptions = asSelectOptions(QUALITY_HDR_TYPE_VALUES)
export const qualityAudioCodecOptions = asSelectOptions(QUALITY_AUDIO_CODEC_VALUES)
export const qualityAudioChannelOptions = asSelectOptions(QUALITY_AUDIO_CHANNEL_VALUES)
export const qualityColorDepthOptions = asSelectOptions(QUALITY_COLOR_DEPTH_VALUES)

export function resourceFormValuesForKinds(kinds) {
  const selectedKinds = Array.isArray(kinds) && kinds.length > 0 ? kinds : ['video_file']
  return [...new Set(selectedKinds.flatMap((kind) => RESOURCE_FORMS_BY_KIND[kind] || []))]
}

export function resourceFormOptionsForKinds(kinds) {
  return asSelectOptions(resourceFormValuesForKinds(kinds))
}

export function normalizeResourceFormsForKinds(forms, kinds) {
  const allowed = new Set(resourceFormValuesForKinds(kinds))
  return (forms || []).filter((form) => allowed.has(form))
}
