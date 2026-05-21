import { t } from '@/i18n'

export function createBootstrapValidators({ config, notification, testServiceConnection, testDirectoryAccess }) {
  const enabled = (items) => (items || []).filter((item) => item.enabled)

  async function validateDownloaderStep() {
    const enabledDownloaders = enabled(config.downloaders)
    if (!enabledDownloaders.length) {
      notification.warn(t('bootstrap.validateDownloaderRequired'), t('bootstrap.notComplete'))
      return false
    }
    const target = enabledDownloaders.find((item) => item.id === config.download?.default_downloader_id) || enabledDownloaders[0]
    await testServiceConnection({ type: target.type, config: { url: target.url, username: target.username, password: target.password } })
    return true
  }

  async function validateIndexerStep() {
    const enabledIndexers = enabled(config.indexers)
    if (!enabledIndexers.length) {
      notification.warn(t('bootstrap.validateIndexerRequired'), t('bootstrap.notComplete'))
      return false
    }
    for (const indexer of enabledIndexers) {
      await testServiceConnection({ type: indexer.type, config: { url: indexer.url, api_key: indexer.api_key } })
    }
    return true
  }

  async function validateMediaServerStep() {
    for (const mediaServer of enabled(config.media_servers)) {
      await testServiceConnection({ type: mediaServer.type, config: { url: mediaServer.url, api_key: mediaServer.api_key } })
    }
    return true
  }

  async function validateTemplateStep() {
    if (getTemplateIncompleteReason()) {
      notification.warn(t('bootstrap.templateRequirement'), t('bootstrap.notComplete'))
      return false
    }
    return true
  }

  function getTemplateIncompleteReason() {
    const templates = enabled(config.naming_templates)
    const movies = templates.filter((item) => item.type === 'movie')
    const tv = templates.filter((item) => item.type === 'tv')
    if (!movies.length) return t('bootstrap.missingMovieTemplate')
    if (!tv.length) return t('bootstrap.missingTvTemplate')
    if (!movies.some((item) => item.is_default)) return t('bootstrap.missingDefaultMovieTemplate')
    if (!tv.some((item) => item.is_default)) return t('bootstrap.missingDefaultTvTemplate')
    return ''
  }

  async function validateDirectoryStep() {
    const directories = enabled(config.directories)
    const reason = getDirectoryIncompleteReason()
    if (reason) {
      notification.warn(reason, t('bootstrap.notComplete'))
      return false
    }
    for (const directory of directories) {
      const directoryName = directory.name || directory.path || t('settings.directory.unnamed')
      if (!directory.downloader_id) return notification.error(t('bootstrap.directoryDownloaderMissing', { name: directoryName })), false
      if (directory.media_type === 'movie' && !directory.movie_template_id) return notification.error(t('bootstrap.movieTemplateMissingForDirectory', { name: directoryName })), false
      if (directory.media_type === 'tv' && !directory.tv_template_id) return notification.error(t('bootstrap.tvTemplateMissingForDirectory', { name: directoryName })), false

      const libraryResult = await testDirectoryAccess({ path: directory.path })
      if (!isDirectoryAccessible(libraryResult.permissions)) return notification.error(t('bootstrap.directoryUnavailable', { path: directory.path || directoryName })), false

      const downloadResult = await testDirectoryAccess({ path: directory.download_path })
      if (!isDirectoryAccessible(downloadResult.permissions)) return notification.error(t('bootstrap.downloadDirectoryUnavailable', { path: directory.download_path || directoryName })), false
    }
    return true
  }

  function getDirectoryIncompleteReason() {
    const directories = enabled(config.directories)
    const movies = directories.filter((item) => item.media_type === 'movie')
    const tv = directories.filter((item) => item.media_type === 'tv')
    if (!directories.length) return t('bootstrap.missingDirectory')
    if (!movies.length) return t('bootstrap.missingMovieDirectory')
    if (!tv.length) return t('bootstrap.missingTvDirectory')
    if (!movies.some((item) => item.is_default)) return t('bootstrap.missingDefaultMovieDirectory')
    if (!tv.some((item) => item.is_default)) return t('bootstrap.missingDefaultTvDirectory')
    return ''
  }

  return {
    validateDownloaderStep,
    validateIndexerStep,
    validateMediaServerStep,
    validateTemplateStep,
    getTemplateIncompleteReason,
    validateDirectoryStep,
    getDirectoryIncompleteReason,
  }
}

export function isDirectoryAccessible(permissions) {
  if (!permissions) return false
  return permissions.exists ? !!permissions.readable && !!permissions.writable : !!permissions.writable
}
