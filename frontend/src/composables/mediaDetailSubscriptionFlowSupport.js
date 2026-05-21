import { requireStrictMediaIdentity } from '@/composables/mediaIdentitySupport'
import { hasMeaningfulSubscriptionFilters, normalizeMediaType } from '@/composables/mediaDetailSubscriptionSupport'
import { t } from '@/i18n'

export function resolveRouteMediaType(mediaId) {
  const currentMediaId = String(mediaId || '')
  const [, type] = currentMediaId.split(':')
  return type === 'movie' || type === 'tv' ? type : null
}

export function resolveEffectiveFilters(downloadConfig, defaultFilterPreset) {
  if (hasMeaningfulSubscriptionFilters(downloadConfig?.filters)) {
    return downloadConfig?.filters || null
  }
  if (!downloadConfig?.filter_config_id && defaultFilterPreset?.filters) {
    return defaultFilterPreset.filters
  }
  return null
}

export function resolveFilterPresetName(downloadConfig, defaultFilterPreset) {
  if (downloadConfig?.filter_config_name) {
    return downloadConfig.filter_config_name
  }
  if (!downloadConfig?.filter_config_id && defaultFilterPreset?.name) {
    return defaultFilterPreset.name
  }
  return t('mediaDetail.emptyValue')
}

export function resolveDefaultDirectoryId({ detail, objectConfig, routeMediaType }) {
  const mediaType = routeMediaType || normalizeMediaType(detail?.media_type || detail?.type)
  const directories = (objectConfig?.directories || []).filter((item) => (
    item?.enabled && normalizeMediaType(item?.media_type) === mediaType
  ))
  return directories.find((item) => item?.is_default)?.id || null
}

export function buildDetailMediaIdentity({ mediaId, detail, errorMessage }) {
  return requireStrictMediaIdentity(
    {
      media_id: mediaId,
      title: detail?.title,
      year: detail?.year,
    },
    errorMessage,
  )
}
