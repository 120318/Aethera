import { useRouter } from 'vue-router'

import { getObjectConfig } from '@/api/config'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/i18n'

const SETTINGS_HASH = {
  tmdb: '#metadata',
  downloader: '#downloader',
  indexer: '#indexer',
  naming: '#naming',
  directory: '#directory',
}

function normalizeMediaType(value) {
  if (!value) return 'movie'
  if (value === 'movie' || value === 'tv') return value
  if (typeof value === 'string') {
    if (value.includes('movie')) return 'movie'
    if (value.includes('tv')) return 'tv'
  }
  return 'movie'
}

function getPayload(data) {
  return data?.config || data || {}
}

function getEnabledDownloaders(config) {
  return (config.downloaders || []).filter((item) => item?.enabled)
}

function getEnabledIndexers(config) {
  return (config.indexers || []).filter((item) => item?.enabled)
}

function getEnabledTemplates(config, mediaType) {
  return (config.naming_templates || []).filter((item) => item?.enabled && item?.type === mediaType)
}

function getEnabledDirectories(config, mediaType) {
  return (config.directories || []).filter((item) => item?.enabled && normalizeMediaType(item?.media_type) === mediaType)
}

function hasValidDefaultDownloader(config) {
  const enabledDownloaders = getEnabledDownloaders(config)
  if (!enabledDownloaders.length) return false
  const defaultDownloaderId = config.download?.default_downloader_id
  return !!defaultDownloaderId && enabledDownloaders.some((item) => item.id === defaultDownloaderId)
}

function hasValidDefaultTemplate(config, mediaType) {
  return getEnabledTemplates(config, mediaType).some((item) => item?.is_default)
}

function hasValidDefaultDirectory(config, mediaType) {
  return getEnabledDirectories(config, mediaType).some((item) => item?.is_default)
}

function hasUsableDirectoryBindings(config, mediaType) {
  return getEnabledDirectories(config, mediaType).some((directory) => {
    if (!directory?.is_default) return false
    if (!directory?.downloader_id) return false
    if (mediaType === 'movie') return !!directory.movie_template_id
    return !!directory.tv_template_id
  })
}

function createReadyState() {
  return {
    available: true,
    reason: t('actionPrerequisites.ready'),
    target: null,
  }
}

function createBlockedState(reason, target) {
  return {
    available: false,
    reason,
    target,
  }
}

function evaluateSearchReadiness(config) {
  if (!getEnabledIndexers(config).length) {
    return createBlockedState(t('actionPrerequisites.indexerRequired'), 'indexer')
  }
  return createReadyState()
}

function evaluateAcquireReadiness(config, mediaTypeInput) {
  const mediaType = normalizeMediaType(mediaTypeInput)

  if (!getEnabledIndexers(config).length) {
    return createBlockedState(t('actionPrerequisites.indexerRequired'), 'indexer')
  }

  if (!hasValidDefaultDownloader(config)) {
    return createBlockedState(t('actionPrerequisites.defaultDownloaderRequired'), 'downloader')
  }

  const templates = getEnabledTemplates(config, mediaType)
  if (!templates.length || !hasValidDefaultTemplate(config, mediaType)) {
    return createBlockedState(
      t(mediaType === 'movie' ? 'actionPrerequisites.defaultMovieTemplateRequired' : 'actionPrerequisites.defaultTvTemplateRequired'),
      'naming',
    )
  }

  const directories = getEnabledDirectories(config, mediaType)
  if (!directories.length) {
    return createBlockedState(
      t(mediaType === 'movie' ? 'actionPrerequisites.defaultMovieDirectoryRequired' : 'actionPrerequisites.defaultTvDirectoryRequired'),
      'directory',
    )
  }

  if (!hasValidDefaultDirectory(config, mediaType)) {
    return createBlockedState(
      t(mediaType === 'movie' ? 'actionPrerequisites.defaultMovieDirectoryRequired' : 'actionPrerequisites.defaultTvDirectoryRequired'),
      'directory',
    )
  }

  if (!hasUsableDirectoryBindings(config, mediaType)) {
    return createBlockedState(t('actionPrerequisites.directoryBindingRequired'), 'directory')
  }

  return createReadyState()
}

export function analyzeActionPrerequisites(configInput, mediaTypeInput) {
  const config = getPayload(configInput)
  return {
    search: evaluateSearchReadiness(config),
    download: evaluateAcquireReadiness(config, mediaTypeInput),
    subscription: evaluateAcquireReadiness(config, mediaTypeInput),
    follow: createReadyState(),
  }
}

export function useActionPrerequisites(options = {}) {
  const router = useRouter()
  const notification = useNotificationStore()
  const readinessSource = options.readinessSource || null

  async function fetchConfig() {
    const data = await getObjectConfig()
    return getPayload(data)
  }

  function goToSettings(target) {
    const hash = SETTINGS_HASH[target]
    if (!hash) return
    router.push({ path: '/settings', hash })
  }

  function resolveReadinessReason(item) {
    if (item?.reason_key) return t(item.reason_key, item.reason_params || {})
    return item?.reason || t('actionPrerequisites.configMissing')
  }

  function warnAndGo(detail, target) {
    notification.warn(detail, t('actionPrerequisites.configMissing'))
    goToSettings(target)
    return false
  }

  async function fetchGuidanceState() {
    const config = await fetchConfig()
    return {
      tmdbConfigured: !!String(config.themoviedb?.api_key || '').trim(),
    }
  }

  async function ensureSearchReady() {
    const injected = readinessSource?.value?.search
    if (injected) {
      if (!injected.available) {
        return warnAndGo(resolveReadinessReason(injected), injected.target)
      }
      return true
    }
    const config = await fetchConfig()
    const readiness = analyzeActionPrerequisites(config)
    if (!readiness.search.available) {
      return warnAndGo(readiness.search.reason, readiness.search.target)
    }
    return true
  }

  async function ensureDownloadReady(mediaTypeInput) {
    const injected = readinessSource?.value?.download
    if (injected) {
      if (!injected.available) {
        return warnAndGo(resolveReadinessReason(injected), injected.target)
      }
      return true
    }
    const config = await fetchConfig()
    const readiness = analyzeActionPrerequisites(config, mediaTypeInput)
    if (!readiness.download.available) {
      return warnAndGo(readiness.download.reason, readiness.download.target)
    }
    return true
  }

  async function ensureSubscriptionReady(mediaTypeInput) {
    const injected = readinessSource?.value?.subscription
    if (injected) {
      if (!injected.available) {
        return warnAndGo(resolveReadinessReason(injected), injected.target)
      }
      return true
    }
    const config = await fetchConfig()
    const readiness = analyzeActionPrerequisites(config, mediaTypeInput)
    if (!readiness.subscription.available) {
      return warnAndGo(readiness.subscription.reason, readiness.subscription.target)
    }
    return true
  }

  async function ensureFollowReady() {
    return true
  }

  return {
    fetchGuidanceState,
    goToSettings,
    ensureSearchReady,
    ensureDownloadReady,
    ensureFollowReady,
    ensureSubscriptionReady,
  }
}
