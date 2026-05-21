<template>
  <div class="flex flex-col gap-container">
    <!-- Media server card grid -->
    <div
      v-if="config.media_servers && config.media_servers.length > 0"
      class="media-server-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container"
    >
      <div
        v-for="mediaServer in config.media_servers" :key="mediaServer.id"
        class="ui-settings-card h-full"
      >
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h4 class="m-0 text-body font-semibold text-color">{{ mediaServer.name || $t('settings.mediaServer.unnamed') }}</h4>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag :value="mediaServer.type" tone="accent" />
            <AppTag
              v-if="config.default_media_server_id === mediaServer.id"
              :value="$t('common.default')"
              tone="success"
            />
            <ToggleSwitch
              :model-value="mediaServer.enabled"
              :input-id="`media-server-enabled-${mediaServer.id}`"
              @update:model-value="toggleMediaServerEnabled(mediaServer)"
            />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('common.url') }}:</strong> {{ mediaServer.url || $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.mediaServer.scrape') }}</strong> {{ mediaServer.sync?.enabled ? $t('common.enabled') : $t('settings.mediaServer.notEnabled') }}</p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button
            v-if="config.default_media_server_id !== mediaServer.id"
            :label="$t('common.setDefault')"
            severity="secondary"
            outlined
            size="small"
            @click="setDefaultMediaServer(mediaServer.id)"
          />
          <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="editMediaServer(mediaServer)" />
          <Button
            :label="$t('settings.mediaServer.testConnection')" severity="secondary" outlined size="small" :loading="testLoading && currentTestingMediaServer === mediaServer.id"
            @click="testMediaServerConnection(mediaServer)"
          />
          <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="removeMediaServer(mediaServer.id)" />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addMediaServer">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="media-server-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container"
    >
      <button type="button" class="ui-settings-add-card" @click="addMediaServer">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Media server editor dialog -->
    <ConfigDialog
      v-model:visible="mediaServerDialogVisible"
      :title="mediaServerDialogTitle"
      size="md"
      :intro="$t('settings.mediaServer.intro')"
    >
      <div class="ui-dialog-section">
        <label for="dialog-media-server-name" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.name') }}</label>
        <InputText
          id="dialog-media-server-name" v-model="currentMediaServer.name" :placeholder="$t('settings.mediaServer.namePlaceholder')"
          class="w-full"
        />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-media-server-url" class="ui-dialog-item-title block">{{ $t('common.url') }}</label>
        <InputText
          id="dialog-media-server-url" v-model="currentMediaServer.url" :placeholder="$t('settings.mediaServer.urlPlaceholder')"
          class="w-full"
        />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-media-server-api-key" class="ui-dialog-item-title block">{{ $t('common.apiKey') }}</label>
        <InputText
          id="dialog-media-server-api-key" v-model="currentMediaServer.api_key" :placeholder="$t('common.apiKey')"
          class="w-full"
        />
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.mediaServer.directoryMapping') }}</label>
        <div
          v-if="currentMediaServer.path_mappings && currentMediaServer.path_mappings.length > 0"
          class="mapping-list"
        >
          <div
            v-for="(mapping, index) in currentMediaServer.path_mappings" :key="index"
            class="ui-surface-item"
          >
            <div class="directory-mapping">
              <InputText v-model="mapping.remote_path" :placeholder="$t('settings.mediaServer.remotePathPlaceholder', { index: index + 1 })" class="flex-1" />
              <span class="mapping-separator font-bold">:</span>
              <InputText v-model="mapping.local_path" :placeholder="$t('settings.mediaServer.localPathPlaceholder', { index: index + 1 })" class="flex-1" />
              <Button icon="pi pi-trash" severity="danger" text rounded @click="removeMediaServerMapping(index)" />
            </div>
          </div>
        </div>
        <div
          v-else
          class="mapping-empty-state"
        >
          {{ $t('settings.mediaServer.noMappings') }}
        </div>
        <Button
          :label="$t('settings.mediaServer.addMapping')" icon="pi pi-plus" severity="primary" outlined class="w-full mt-item"
          @click="addMediaServerMapping"
        />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-media-server-enabled" class="ui-dialog-item-title block">{{ $t('settings.indexer.enabledLabel') }}</label>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="flex items-center gap-item">
            <ToggleSwitch
              :model-value="currentMediaServer.enabled"
              input-id="dialog-media-server-enabled"
              @update:model-value="updateDialogMediaServerEnabled"
            />
            <span class="text-muted-size text-muted-size font-muted text-muted">{{ currentMediaServer.enabled ? $t('common.enabled') : $t('common.disabled')
            }}</span>
          </div>
          <div class="flex items-center gap-item">
            <ToggleSwitch
              :model-value="currentMediaServerIsDefault"
              input-id="dialog-media-server-default"
              @update:model-value="updateDialogMediaServerDefault"
            />
            <span class="text-muted-size text-muted-size font-muted text-muted">{{ currentMediaServerIsDefault ? $t('settings.mediaServer.defaultMediaServer') : $t('common.setDefault')
            }}</span>
          </div>
        </div>
      </div>

      <div class="ui-dialog-subsection">
        <div class="flex items-start justify-between gap-item">
          <label for="dialog-media-server-sync-enabled" class="ui-dialog-item-title ui-dialog-subsection-title block m-none">{{ $t('settings.mediaServer.syncEnabled') }}</label>
          <Button
            :label="mediaServerSyncExpanded ? $t('settings.mediaServer.collapse') : $t('settings.mediaServer.expand')"
            :icon="mediaServerSyncExpanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
            severity="secondary"
            text
            size="small"
            @click="mediaServerSyncExpanded = !mediaServerSyncExpanded"
          />
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="flex items-center gap-item">
            <ToggleSwitch
              :model-value="currentMediaServer.sync?.enabled"
              input-id="dialog-media-server-sync-enabled"
              @update:model-value="updateDialogMediaServerSyncEnabled"
            />
            <span class="text-muted-size text-muted-size font-muted text-muted">
              {{ currentMediaServer.sync?.enabled ? $t('common.enabled') : $t('common.disabled') }}
            </span>
          </div>
        </div>

        <div v-if="currentMediaServer.sync?.enabled && mediaServerSyncExpanded" class="flex flex-col gap-item">
          <div class="ui-dialog-grid">
            <div class="ui-dialog-section">
              <label for="dialog-media-server-sync-interval" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.syncInterval') }}</label>
              <InputNumber
                v-model="currentMediaServer.sync.interval_hours"
                input-id="dialog-media-server-sync-interval"
                class="w-full"
                :min="1"
                :max="168"
              />
            </div>
            <div class="ui-dialog-section">
              <label for="dialog-media-server-sync-batch" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.batchSize') }}</label>
              <InputNumber
                v-model="currentMediaServer.sync.batch_size"
                input-id="dialog-media-server-sync-batch"
                class="w-full"
                :min="1"
                :max="200"
              />
            </div>
          </div>

          <div class="ui-dialog-grid">
            <div class="ui-dialog-section">
              <label for="dialog-media-server-sync-backoff" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.maxBackoff') }}</label>
              <InputNumber
                v-model="currentMediaServer.sync.max_backoff_hours"
                input-id="dialog-media-server-sync-backoff"
                class="w-full"
                :min="1"
                :max="168"
              />
            </div>
            <div class="ui-dialog-section">
              <label for="dialog-media-server-sync-movie-stale" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.movieStale') }}</label>
              <InputNumber
                v-model="currentMediaServer.sync.stale_after_days_movie"
                input-id="dialog-media-server-sync-movie-stale"
                class="w-full"
                :min="1"
                :max="365"
              />
            </div>
          </div>

          <div class="ui-dialog-grid">
            <div class="ui-dialog-section">
              <label for="dialog-media-server-sync-tv-stale" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.tvStale') }}</label>
              <InputNumber
                v-model="currentMediaServer.sync.stale_after_days_tvshow"
                input-id="dialog-media-server-sync-tv-stale"
                class="w-full"
                :min="1"
                :max="365"
              />
            </div>
            <div class="ui-dialog-section">
              <label for="dialog-media-server-sync-ongoing-stale" class="ui-dialog-item-title block">{{ $t('settings.mediaServer.ongoingStale') }}</label>
              <InputNumber
                v-model="currentMediaServer.sync.stale_after_days_ongoing_tv"
                input-id="dialog-media-server-sync-ongoing-stale"
                class="w-full"
                :min="1"
                :max="30"
              />
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="mediaServerDialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" @click="saveMediaServer" />
      </template>
    </ConfigDialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import {
  clearDefaultMediaServer,
  createMediaServer,
  deleteMediaServer,
  setDefaultMediaServerEntry,
  testServiceConnection,
  updateMediaServer,
} from '@/api/config'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
  applyConfigPatch: {
    type: Function,
    required: true,
  },
})

const notification = useNotificationStore()
const { t } = useI18n()

const mediaServerDialogVisible = ref(false)
const currentMediaServer = ref(createEmptyMediaServer())
const currentMediaServerIsDefault = ref(false)
const mediaServerSyncExpanded = ref(false)
const mediaServerDialogTitle = ref('')
const mediaServerDialogMode = ref('add')
const currentTestingMediaServer = ref(null)
const testLoading = ref(false)

function createDefaultSyncConfig() {
  return {
    enabled: true,
    fetch_metadata: true,
    write_nfo: true,
    download_images: true,
    refresh_after_sync: true,
    interval_hours: 6,
    batch_size: 20,
    stale_after_days_movie: 30,
    stale_after_days_tvshow: 7,
    stale_after_days_ongoing_tv: 1,
    max_backoff_hours: 24,
  }
}

function createEmptyMediaServer() {
  return {
    id: '',
    name: '',
    type: 'jellyfin',
    enabled: true,
    url: '',
    api_key: '',
    path_mappings: [],
    sync: createDefaultSyncConfig(),
  }
}

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value))
}

function normalizeMediaServer(mediaServer) {
  return {
    ...createEmptyMediaServer(),
    ...(mediaServer || {}),
    path_mappings: Array.isArray(mediaServer?.path_mappings) ? cloneValue(mediaServer.path_mappings) : [],
    sync: {
      ...createDefaultSyncConfig(),
      ...(mediaServer?.sync || {}),
    },
  }
}

function getMediaServers() {
  return Array.isArray(props.config.media_servers) ? props.config.media_servers : []
}

function patchMediaServerConfig(mediaServers, defaultMediaServerId = props.config.default_media_server_id || null) {
  props.applyConfigPatch({
    media_servers: mediaServers,
    default_media_server_id: defaultMediaServerId,
  })
}

function addMediaServer() {
  mediaServerDialogVisible.value = true
  mediaServerDialogTitle.value = t('settings.mediaServer.addTitle')
  mediaServerDialogMode.value = 'add'
  currentMediaServer.value = normalizeMediaServer({
    id: `media_server_${Date.now()}`,
    name: t('settings.mediaServer.newJellyfin'),
  })
  currentMediaServerIsDefault.value = false
  mediaServerSyncExpanded.value = false
}

function editMediaServer(mediaServer) {
  mediaServerDialogVisible.value = true
  mediaServerDialogTitle.value = t('settings.mediaServer.editTitle')
  mediaServerDialogMode.value = 'edit'
  currentMediaServer.value = normalizeMediaServer(cloneValue(mediaServer))
  currentMediaServerIsDefault.value = props.config.default_media_server_id === mediaServer.id
  mediaServerSyncExpanded.value = false
}

async function saveMediaServer() {
  const currentMediaServers = cloneValue(getMediaServers())
  const previousDefaultMediaServerId = props.config.default_media_server_id || null

  try {
    currentMediaServer.value.sync = {
      ...currentMediaServer.value.sync,
      enabled: currentMediaServer.value.sync?.enabled ?? true,
      fetch_metadata: true,
      write_nfo: true,
      download_images: true,
      refresh_after_sync: true,
    }

    let nextMediaServers = currentMediaServers
    if (mediaServerDialogMode.value === 'add') {
      await createMediaServer({ media_server: currentMediaServer.value })
      nextMediaServers = [...currentMediaServers, cloneValue(currentMediaServer.value)]
    } else {
      await updateMediaServer(currentMediaServer.value.id, { media_server: currentMediaServer.value })
      const index = currentMediaServers.findIndex((item) => item.id === currentMediaServer.value.id)
      if (index !== -1) {
        nextMediaServers = [...currentMediaServers]
        nextMediaServers[index] = cloneValue(currentMediaServer.value)
      }
    }

    let nextDefaultMediaServerId = previousDefaultMediaServerId
    if (currentMediaServerIsDefault.value) {
      await setDefaultMediaServerEntry(currentMediaServer.value.id)
      nextDefaultMediaServerId = currentMediaServer.value.id
    } else if (previousDefaultMediaServerId === currentMediaServer.value.id) {
      await clearDefaultMediaServer()
      nextDefaultMediaServerId = null
    }

    patchMediaServerConfig(nextMediaServers, nextDefaultMediaServerId)
    mediaServerDialogVisible.value = false
    notification.success(mediaServerDialogMode.value === 'add' ? t('settings.mediaServer.added') : t('settings.mediaServer.updated'))
  } catch (error) {
    notification.error(t('common.saveFailed', { message: error.message }))
  }
}

async function removeMediaServer(id) {
  try {
    await deleteMediaServer(id)
    const nextMediaServers = getMediaServers().filter((item) => item.id !== id)
    const nextDefaultMediaServerId = props.config.default_media_server_id === id ? null : props.config.default_media_server_id
    patchMediaServerConfig(nextMediaServers, nextDefaultMediaServerId)
    notification.success(t('settings.mediaServer.deleted'))
  } catch (error) {
    notification.error(t('common.deleteFailed', { message: error.message }))
  }
}

async function testMediaServerConnection(mediaServer) {
  testLoading.value = true
  currentTestingMediaServer.value = mediaServer.id

  try {
    await testServiceConnection({
      type: mediaServer.type,
      config: {
        url: mediaServer.url,
        api_key: mediaServer.api_key,
      },
    })
    notification.success(t('common.connectionSuccess'))
  } catch (error) {
    notification.error(t('common.networkError', { message: error.message || error }))
  } finally {
    testLoading.value = false
    currentTestingMediaServer.value = null
  }
}

async function setDefaultMediaServer(mediaServerId) {
  try {
    await setDefaultMediaServerEntry(mediaServerId)
    patchMediaServerConfig(getMediaServers(), mediaServerId)
    notification.success(t('settings.mediaServer.defaultSet'))
  } catch (error) {
    notification.error(t('common.settingFailed', { message: error.message }))
  }
}

async function toggleMediaServerEnabled(mediaServer) {
  const mediaServers = cloneValue(getMediaServers())
  const index = mediaServers.findIndex((item) => item.id === mediaServer.id)
  if (index === -1) return

  const previousDefaultMediaServerId = props.config.default_media_server_id || null
  const nextEnabled = !mediaServers[index].enabled
  mediaServers[index].enabled = nextEnabled
  const shouldClearDefault = !nextEnabled && props.config.default_media_server_id === mediaServer.id

  const nextDefaultMediaServerId = shouldClearDefault ? null : previousDefaultMediaServerId

  try {
    await updateMediaServer(mediaServer.id, {
      media_server: mediaServers[index],
    })
    if (shouldClearDefault) {
      await clearDefaultMediaServer()
    }
    patchMediaServerConfig(mediaServers, nextDefaultMediaServerId)
    notification.success(nextEnabled ? t('settings.mediaServer.enabled') : t('settings.mediaServer.disabled'))
  } catch (error) {
    notification.error(t('common.settingFailed', { message: error.message }))
  }
}

function updateDialogMediaServerEnabled(enabled) {
  currentMediaServer.value.enabled = enabled
  if (!enabled) {
    currentMediaServerIsDefault.value = false
  }
}

function updateDialogMediaServerDefault(isDefault) {
  currentMediaServerIsDefault.value = isDefault
  if (isDefault) {
    currentMediaServer.value.enabled = true
  }
}

function updateDialogMediaServerSyncEnabled(enabled) {
  currentMediaServer.value.sync = {
    ...createDefaultSyncConfig(),
    ...(currentMediaServer.value.sync || {}),
    enabled,
  }
}

function addMediaServerMapping() {
  if (!Array.isArray(currentMediaServer.value.path_mappings)) {
    currentMediaServer.value.path_mappings = []
  }
  currentMediaServer.value.path_mappings.push({
    remote_path: '',
    local_path: '',
  })
}

function removeMediaServerMapping(index) {
  if (!Array.isArray(currentMediaServer.value.path_mappings)) return
  currentMediaServer.value.path_mappings.splice(index, 1)
}

defineExpose({
  addMediaServer,
  editMediaServer,
  removeMediaServer,
})
</script>

<style scoped>
.media-server-grid {
  --settings-card-min-height: var(--size-settings-card-min-height-compact);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-block);
}

.directory-mapping-item {
  margin-bottom: var(--spacing-item);
}

.no-mappings {
  padding: var(--spacing-block);
  text-align: center;
  color: var(--text-muted);
  background-color: var(--surface-subtle);
  border-radius: var(--radius-container);
  margin-bottom: var(--spacing-item);
}

.info-item {
  margin: 0;
  font-size: var(--text-small);
  line-height: 1.5;
  color: var(--text-muted);
}

/* Empty state styles */
.no-media-servers {
  text-align: center;
  padding: var(--spacing-section);
  color: var(--text-muted);
  background-color: var(--surface-subtle);
  border-radius: var(--radius-container);
}
</style>
