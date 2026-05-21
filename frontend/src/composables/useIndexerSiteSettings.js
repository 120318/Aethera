export function isSearchToggleDisabled(site, mode, isBaseDisabled = false) {
  if (isBaseDisabled) return true
  if (!site.settings.enabled) return true
  if (mode === 'title') return !site.capabilities.supports_title
  if (mode === 'imdb') return !site.capabilities.supports_imdb
  if (mode === 'douban') return !site.capabilities.supports_douban
  return true
}

export function isMediaTypeToggleDisabled(site, mediaType, isBaseDisabled = false) {
  if (isBaseDisabled) return true
  if (!site.settings.enabled) return true
  if (mediaType === 'movie' && !site.capabilities.supports_movie) return true
  if (mediaType === 'tv' && !site.capabilities.supports_tv) return true
  return false
}

function getSupportedMediaTypes(capabilities) {
  return [
    ...(capabilities.supports_movie ? ['movie'] : []),
    ...(capabilities.supports_tv ? ['tv'] : []),
  ]
}

function getEffectiveMediaTypes(capabilities, mediaTypes) {
  const supportedMediaTypes = getSupportedMediaTypes(capabilities)
  if (!Array.isArray(mediaTypes)) return supportedMediaTypes
  return mediaTypes.filter((mediaType) => supportedMediaTypes.includes(mediaType))
}

export function computeSiteEffective(site, settings) {
  const enabled = settings.enabled && site.is_live
  const manualMediaTypes = Array.isArray(settings.media_types)
  const mediaTypes = getEffectiveMediaTypes(site.capabilities, settings.media_types)
  return {
    enabled,
    use_title: enabled && site.capabilities.supports_title && !settings.disable_title,
    use_imdb: enabled && site.capabilities.supports_imdb && !settings.disable_imdb,
    use_douban: enabled && site.capabilities.supports_douban && !settings.disable_douban,
    supports_movie: manualMediaTypes ? mediaTypes.includes('movie') : !!site.capabilities.supports_movie,
    supports_tv: manualMediaTypes ? mediaTypes.includes('tv') : !!site.capabilities.supports_tv,
    media_types_source: manualMediaTypes ? 'manual' : 'auto',
  }
}

export function buildNextSiteSettings(indexer, siteId, updater, cloneValue) {
  const nextIndexer = cloneValue(indexer)
  const settings = Array.isArray(nextIndexer.site_settings) ? [...nextIndexer.site_settings] : []
  const targetIndex = settings.findIndex((item) => item.site_id === siteId)
  const current = targetIndex === -1
    ? {
        site_id: siteId,
        enabled: true,
        disable_title: false,
        disable_imdb: false,
        disable_douban: false,
        media_types: null,
      }
    : { ...settings[targetIndex] }
  const nextSetting = updater(current)
  if (targetIndex === -1) {
    settings.push(nextSetting)
  } else {
    settings[targetIndex] = nextSetting
  }
  nextIndexer.site_settings = settings
  return nextIndexer
}
