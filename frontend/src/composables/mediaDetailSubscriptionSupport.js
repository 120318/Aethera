export function normalizeMediaType(value) {
  if (value === 'movie' || value === 'tv') return value
  if (typeof value === 'string' && value.includes('tv')) return 'tv'
  return 'movie'
}

export function hasMeaningfulSubscriptionFilters(filters) {
  if (!filters) return false
  const listFields = [
    filters.resolution,
    filters.source,
    filters.resource_form,
    filters.codec,
    filters.hdr_type,
    filters.audio_codec,
    filters.audio_channels,
    filters.color_depth,
    filters.include_keywords,
    filters.exclude_keywords,
    filters.tags,
  ]
  if (listFields.some((items) => Array.isArray(items) && items.length > 0)) return true
  return !!filters.upgrade_policy?.enabled
}
