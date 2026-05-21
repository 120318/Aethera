import { t } from '@/i18n'

export const bootstrapStepOrder = ['password', 'tmdb', 'downloader', 'indexer', 'template', 'media_server', 'directory', 'complete']

export const bootstrapStepLabels = {
  tmdb: 'TMDB',
  downloader: 'settings.tabs.downloader',
  indexer: 'settings.tabs.indexer',
  template: 'settings.tabs.naming',
  media_server: 'bootstrap.mediaLibrarySettings',
  directory: 'settings.tabs.directory',
}

export function resolveBootstrapNextPath(route) {
  const raw = route.query.next
  return typeof raw === 'string' && raw.startsWith('/') ? raw : '/discover'
}

export function resolveBootstrapPageTitle(authStore) {
  if (!authStore.isInitialized) return t('bootstrap.initAdminTitle')
  if (!authStore.isAuthenticated) return t('bootstrap.continueInitTitle')
  return authStore.isSetupComplete ? t('bootstrap.completeTitle') : t('bootstrap.wizardTitle')
}

export function resolveBootstrapPageDescription(authStore) {
  if (!authStore.isInitialized) return t('bootstrap.initAdminDescription')
  if (!authStore.isAuthenticated) return t('bootstrap.continueInitDescription')
  return ''
}

export function resolveBootstrapPageWidthClass(authStore) {
  return !authStore.isInitialized || !authStore.isAuthenticated ? 'max-w-dialog-sm' : 'max-w-dialog-md'
}

export function getBootstrapNextStepKey(step) {
  const index = bootstrapStepOrder.indexOf(step)
  if (index === -1 || index >= bootstrapStepOrder.length - 1) {
    return 'complete'
  }
  return bootstrapStepOrder[index + 1]
}

export function isBootstrapStepReady(step, state) {
  if (step === 'password') return !!state.password_ready
  if (step === 'tmdb') return !!state.tmdb_ready
  if (step === 'downloader') return !!state.downloaders_ready
  if (step === 'indexer') return !!state.indexers_ready
  if (step === 'template') return !!state.templates_ready
  if (step === 'media_server') return true
  if (step === 'directory') return !!state.directories_ready
  if (step === 'complete') return !!state.completed
  return false
}

export function syncBootstrapSelectedStep(authStore, selectedStep) {
  selectedStep.value = !authStore.isInitialized
    ? 'password'
    : authStore.isSetupComplete ? 'complete' : authStore.currentStep
}

export function createBootstrapConfigActions(refs) {
  return {
    openAddDownloader: () => refs.downloaderConfigRef.value?.addDownloader(),
    openEditDownloader: (downloader) => refs.downloaderConfigRef.value?.editDownloader(downloader),
    removeDownloader: (downloaderId) => refs.downloaderConfigRef.value?.removeDownloader(downloaderId),
    openAddIndexer: () => refs.indexerConfigRef.value?.addIndexer(),
    openEditIndexer: (indexer) => refs.indexerConfigRef.value?.editIndexer(indexer),
    removeIndexer: (indexerId) => refs.indexerConfigRef.value?.removeIndexer(indexerId),
    openAddTemplate: () => refs.templateConfigRef.value?.addTemplate(),
    openEditTemplate: (template) => refs.templateConfigRef.value?.editTemplate(template),
    removeTemplate: (templateId) => refs.templateConfigRef.value?.removeTemplate(templateId),
    setDefaultTemplate: (template) => refs.templateConfigRef.value?.setDefaultTemplate(template),
    openAddMediaServer: () => refs.mediaServerConfigRef.value?.addMediaServer(),
    openEditMediaServer: (mediaServer) => refs.mediaServerConfigRef.value?.editMediaServer(mediaServer),
    removeMediaServer: (mediaServerId) => refs.mediaServerConfigRef.value?.removeMediaServer(mediaServerId),
    openAddDirectory: () => refs.directoryConfigRef.value?.addDirectory(),
    openEditDirectory: (directory) => refs.directoryConfigRef.value?.editDirectory(directory),
    removeDirectory: (directoryId) => refs.directoryConfigRef.value?.removeDirectory(directoryId),
    setDefaultDirectory: (directoryId) => refs.directoryConfigRef.value?.setDefaultDirectory(directoryId),
  }
}
