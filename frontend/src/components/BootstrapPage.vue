<template>
  <div class="w-full min-h-full flex items-center justify-center px-block py-item">
    <div v-if="redirecting || shouldSkipWizard" class="w-full max-w-dialog-sm">
      <section class="ui-panel overflow-hidden">
        <div class="flex items-center justify-center py-block">
          <i class="pi pi-spin pi-spinner text-title text-primary" />
        </div>
      </section>
    </div>
    <div v-else-if="!loading && !bootstrapError && !authStore.isInitialized" class="w-full max-w-dialog-sm">
      <Card class="w-full">
        <template #title>
          <div class="flex items-baseline justify-between gap-item">
            <span>{{ pageTitle }}</span>
          </div>
        </template>
        <template #content>
          <div class="flex flex-col gap-container">
            <p v-if="pageDescription" class="m-none text-caption text-muted">{{ pageDescription }}</p>

            <div class="flex flex-col gap-item">
              <label class="font-bold">{{ $t('settings.system.newPassword') }}</label>
              <InputText v-model="password" class="w-full" type="password" autocomplete="new-password" />
            </div>

            <div class="flex flex-col gap-item">
              <label class="font-bold">{{ $t('settings.system.confirmNewPassword') }}</label>
              <InputText v-model="passwordConfirm" class="w-full" type="password" autocomplete="new-password" />
            </div>

            <div class="flex justify-end gap-item pt-item">
              <Button :label="$t('bootstrap.setAdminPassword')" icon="pi pi-lock" :loading="working" @click="handleBootstrap" />
            </div>
          </div>
        </template>
      </Card>
    </div>
    <div v-else :class="['w-full', pageWidthClass]">
      <section class="ui-panel overflow-hidden">
        <div class="ui-panel-body pb-item">
          <div class="ui-panel-copy">
            <h2 class="m-none text-subtitle font-semibold text-color">{{ pageTitle }}</h2>
            <p v-if="pageDescription" class="m-none text-caption text-muted">{{ pageDescription }}</p>
          </div>
        </div>

        <div class="ui-dialog-body px-container pt-none pb-container">
          <div v-if="loading" class="flex items-center justify-center py-block">
            <i class="pi pi-spin pi-spinner text-title text-primary" />
          </div>

          <div v-else-if="bootstrapError" class="ui-dialog-body">
            <div class="ui-dialog-section">
              <p class="m-none text-body text-color">{{ $t('bootstrap.statusLoadFailed') }}</p>
              <p class="m-none ui-dialog-help">{{ $t('bootstrap.statusLoadFailedHint') }}</p>
            </div>
            <div class="flex justify-end">
              <Button :label="$t('common.retry')" icon="pi pi-refresh" @click="retryRefresh" />
            </div>
          </div>

          <div v-else-if="!authStore.isAuthenticated" class="ui-dialog-body">
            <div class="ui-dialog-section">
              <p class="m-none text-body text-color">{{ $t('bootstrap.loginRequired') }}</p>
              <p class="m-none ui-dialog-help">{{ $t('bootstrap.loginRequiredHint') }}</p>
            </div>
            <div class="flex justify-end">
              <Button :label="$t('bootstrap.goLogin')" icon="pi pi-sign-in" @click="goLogin" />
            </div>
          </div>

          <div v-else class="ui-dialog-body">
            <div v-if="selectedStep === 'tmdb'" class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.metadata.tmdbApiKey') }}</label>
              <SecretInput
                v-model="config.themoviedb.api_key"
                :placeholder="$t('settings.metadata.apiKeyPlaceholder')"
                autocomplete="off"
              />
              <small class="ui-dialog-help">{{ $t('bootstrap.tmdbApiKeyHint') }}</small>
            </div>

            <div v-else-if="selectedStep === 'downloader'" class="ui-dialog-section">
              <div class="flex items-center justify-between gap-item">
                <label class="ui-dialog-item-title block">{{ $t('settings.tabs.downloader') }}</label>
              </div>
              <button
                v-if="!config.downloaders?.length"
                type="button"
                class="ui-settings-add-card w-full"
                @click="openAddDownloader"
              >
                <i class="pi pi-plus text-title" aria-hidden="true" />
                <span class="text-body font-medium">{{ $t('settings.downloader.addDownloader') }}</span>
              </button>
              <div v-else class="flex flex-col gap-item">
                <div
                  v-for="downloader in config.downloaders.slice(0, 1)"
                  :key="downloader.id"
                  class="ui-settings-card min-h-0"
                >
                  <div class="ui-settings-card-header">
                    <div class="ui-settings-card-copy">
                      <strong class="text-body text-color">{{ downloader.name || $t('settings.downloader.unnamed') }}</strong>
                    </div>
                    <div class="flex items-center gap-item">
                      <AppTag :value="downloader.type" tone="accent" />
                      <AppTag
                        v-if="config.download.default_downloader_id === downloader.id"
                        :value="$t('common.default')"
                        tone="success"
                      />
                    </div>
                  </div>
                  <div class="ui-settings-card-body">
                    <p class="m-none text-caption text-muted">
                      <strong class="font-semibold">{{ $t('common.url') }}:</strong> {{ downloader.url || $t('common.notSet') }}
                    </p>
                  </div>
                  <div class="ui-settings-card-actions">
                    <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="openEditDownloader(downloader)" />
                    <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="removeDownloader(downloader.id)" />
                  </div>
                </div>
              </div>
            </div>

            <div v-else-if="selectedStep === 'indexer'" class="ui-dialog-section">
              <div class="flex items-center justify-between gap-item">
                <label class="ui-dialog-item-title block">{{ $t('settings.tabs.indexer') }}</label>
              </div>
              <button
                v-if="!config.indexers?.length"
                type="button"
                class="ui-settings-add-card w-full"
                @click="openAddIndexer"
              >
                <i class="pi pi-plus text-title" aria-hidden="true" />
                <span class="text-body font-medium">{{ $t('settings.indexer.addIndexer') }}</span>
              </button>
              <div v-else class="flex flex-col gap-item">
                <div v-for="indexer in config.indexers" :key="indexer.id" class="ui-settings-card min-h-0">
                  <div class="ui-settings-card-header">
                    <div class="ui-settings-card-copy">
                      <strong class="text-body text-color">{{ indexer.name || $t('settings.indexer.unnamed') }}</strong>
                    </div>
                    <div class="flex items-center gap-item">
                      <AppTag :value="indexer.type || $t('settings.tabs.indexer')" tone="accent" />
                    </div>
                  </div>
                  <div class="ui-settings-card-body">
                    <p class="m-none text-caption text-muted">
                      <strong class="font-semibold">{{ $t('common.url') }}:</strong> {{ indexer.url || $t('common.notSet') }}
                    </p>
                  </div>
                  <div class="ui-settings-card-actions">
                    <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="openEditIndexer(indexer)" />
                    <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="removeIndexer(indexer.id)" />
                  </div>
                </div>
              </div>
            </div>

            <div v-else-if="selectedStep === 'template'" class="ui-dialog-section">
              <div class="flex items-center justify-between gap-item">
                <label class="ui-dialog-item-title block">{{ $t('settings.tabs.naming') }}</label>
                <Button :label="$t('common.add')" icon="pi pi-plus" severity="secondary" text @click="openAddTemplate" />
              </div>
              <div class="ui-dialog-help">{{ $t('bootstrap.templateRequirement') }}</div>
              <div v-if="config.naming_templates?.length" class="flex flex-col gap-item">
                <div v-for="template in config.naming_templates" :key="template.id" class="ui-settings-card min-h-0">
                  <div class="ui-settings-card-body">
                    <div class="ui-settings-card-copy">
                      <strong class="text-body text-color">{{ template.name || $t('settings.naming.unnamed') }}</strong>
                      <span class="text-caption text-muted">{{ template.type === 'movie' ? $t('bootstrap.movieTemplate') : $t('bootstrap.tvTemplate') }}</span>
                      <span v-if="template.is_default" class="text-caption text-muted">{{ $t('settings.naming.defaultTemplate') }}</span>
                    </div>
                  </div>
                  <div class="ui-settings-card-actions">
                    <Button
                      v-if="!template.is_default"
                      :label="$t('common.setDefault')"
                      severity="secondary"
                      text
                      size="small"
                      @click="setDefaultTemplate(template)"
                    />
                    <Button :label="$t('common.edit')" severity="secondary" text size="small" @click="openEditTemplate(template)" />
                    <Button
                      :label="$t('common.delete')"
                      severity="secondary"
                      text
                      size="small"
                      :disabled="template.is_default"
                      @click="removeTemplate(template.id)"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="bootstrap-empty-state">{{ $t('bootstrap.templateEmpty') }}</div>
            </div>

            <div v-else-if="selectedStep === 'media_server'" class="ui-dialog-section">
              <div class="flex items-center justify-between gap-item">
                <label class="ui-dialog-item-title block">{{ $t('bootstrap.mediaLibrarySettings') }}</label>
              </div>
              <div v-if="config.media_servers?.length" class="flex flex-col gap-item">
                <div v-for="mediaServer in config.media_servers" :key="mediaServer.id" class="ui-settings-card min-h-0">
                  <div class="ui-settings-card-header">
                    <div class="ui-settings-card-copy">
                      <strong class="text-body text-color">{{ mediaServer.name || $t('settings.mediaServer.unnamed') }}</strong>
                    </div>
                    <div class="flex items-center gap-item">
                      <AppTag :value="mediaServer.type || $t('settings.tabs.mediaServer')" tone="accent" />
                      <AppTag v-if="mediaServer.sync?.enabled" :value="$t('bootstrap.syncEnabled')" tone="success" />
                    </div>
                  </div>
                  <div class="ui-settings-card-body">
                    <p class="m-none text-caption text-muted">
                      <strong class="font-semibold">{{ $t('common.url') }}:</strong> {{ mediaServer.url || $t('common.notSet') }}
                    </p>
                  </div>
                  <div class="ui-settings-card-actions">
                    <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="openEditMediaServer(mediaServer)" />
                    <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="removeMediaServer(mediaServer.id)" />
                  </div>
                </div>
              </div>
              <button
                v-else
                type="button"
                class="ui-settings-add-card w-full"
                @click="openAddMediaServer"
              >
                <i class="pi pi-plus text-title" aria-hidden="true" />
                <span class="text-body font-medium">{{ $t('bootstrap.addMediaLibrary') }}</span>
              </button>
              <div class="ui-dialog-help">{{ $t('bootstrap.optionalLater') }}</div>
            </div>

            <div v-else-if="selectedStep === 'directory'" class="ui-dialog-section">
              <div class="flex items-center justify-between gap-item">
                <label class="ui-dialog-item-title block">{{ $t('settings.tabs.directory') }}</label>
                <Button :label="$t('common.add')" icon="pi pi-plus" severity="secondary" text @click="openAddDirectory" />
              </div>
              <div class="ui-dialog-help">{{ $t('bootstrap.directoryRequirement') }}</div>
              <div v-if="config.directories?.length" class="flex flex-col gap-item">
                <div v-for="directory in config.directories" :key="directory.id" class="ui-settings-card min-h-0">
                  <div class="ui-settings-card-body">
                    <div class="ui-settings-card-copy">
                      <strong class="text-body text-color">{{ directory.name || $t('settings.directory.unnamed') }}</strong>
                      <span class="text-caption text-muted">{{ directory.media_type === 'movie' ? $t('bootstrap.movieDirectory') : $t('bootstrap.tvDirectory') }}</span>
                      <span class="text-caption text-muted">{{ directory.path || $t('bootstrap.pathNotSet') }}</span>
                      <span v-if="directory.is_default" class="text-caption text-muted">{{ $t('settings.directory.defaultDirectory') }}</span>
                    </div>
                  </div>
                  <div class="ui-settings-card-actions">
                    <Button
                      v-if="!directory.is_default"
                      :label="$t('common.setDefault')"
                      severity="secondary"
                      text
                      size="small"
                      @click="setDefaultDirectory(directory.id)"
                    />
                    <Button :label="$t('common.edit')" severity="secondary" text size="small" @click="openEditDirectory(directory)" />
                    <Button :label="$t('common.delete')" severity="secondary" text size="small" @click="removeDirectory(directory.id)" />
                  </div>
                </div>
              </div>
              <div v-else class="bootstrap-empty-state">{{ $t('bootstrap.directoryEmpty') }}</div>
            </div>

            <div v-else class="ui-dialog-section">
              <p class="m-none text-body text-color">{{ $t('bootstrap.completeMessage') }}</p>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-item">
              <Button
                :label="$t('bootstrap.previous')"
                icon="pi pi-arrow-left"
                severity="secondary"
                text
                :disabled="!previousStepKey"
                @click="goPrevious"
              />
              <div class="flex flex-wrap justify-end gap-item">
                <Button
                  v-if="!authStore.isSetupComplete"
                  :label="$t('bootstrap.next')"
                  icon="pi pi-arrow-right"
                  :loading="working || tmdbSaving"
                  @click="advanceStep"
                />
                <Button
                  v-else
                  :label="$t('bootstrap.enterApp')"
                  icon="pi pi-check"
                  @click="enterApp"
                />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
    <div class="hidden">
      <DownloaderConfig ref="downloaderConfigRef" :config="config" @save="fetchConfig" />
      <IndexerConfig ref="indexerConfigRef" :config="config" />
      <MediaServerConfig ref="mediaServerConfigRef" :config="config" />
      <NamingTemplateConfig ref="templateConfigRef" :config="config" />
      <DirectoryConfig ref="directoryConfigRef" :config="config" />
    </div>
  </div>
</template>

<script setup>
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import AppTag from '@/components/common/AppTag.vue'
import SecretInput from '@/components/common/SecretInput.vue'
import DirectoryConfig from '@/components/config/DirectoryConfig.vue'
import DownloaderConfig from '@/components/config/DownloaderConfig.vue'
import IndexerConfig from '@/components/config/IndexerConfig.vue'
import MediaServerConfig from '@/components/config/MediaServerConfig.vue'
import NamingTemplateConfig from '@/components/config/NamingTemplateConfig.vue'
import { useBootstrapWizard } from '@/composables/useBootstrapWizard'

const {
  authStore,
  config,
  loading,
  working,
  tmdbSaving,
  password,
  passwordConfirm,
  selectedStep,
  bootstrapError,
  redirecting,
  downloaderConfigRef,
  indexerConfigRef,
  mediaServerConfigRef,
  templateConfigRef,
  directoryConfigRef,
  pageTitle,
  pageDescription,
  pageWidthClass,
  shouldSkipWizard,
  previousStepKey,
  handleBootstrap,
  goLogin,
  openAddDownloader,
  openEditDownloader,
  removeDownloader,
  openAddIndexer,
  openEditIndexer,
  removeIndexer,
  openAddTemplate,
  openEditTemplate,
  removeTemplate,
  setDefaultTemplate,
  openAddMediaServer,
  openEditMediaServer,
  removeMediaServer,
  openAddDirectory,
  openEditDirectory,
  removeDirectory,
  setDefaultDirectory,
  goPrevious,
  advanceStep,
  enterApp,
  retryRefresh,
  fetchConfig,
} = useBootstrapWizard()
</script>

<style scoped>
.bootstrap-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-item);
  min-height: var(--size-placeholder-action);
  padding: var(--spacing-block);
  text-align: center;
  color: var(--text-muted);
  border: 1px solid var(--border-settings);
  border-radius: var(--radius-container);
  background-color: var(--surface-settings-card);
}
</style>
