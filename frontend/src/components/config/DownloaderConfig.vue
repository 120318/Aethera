<template>
  <div class="flex flex-col gap-container">
    <!-- Downloader card grid -->
    <div
      v-if="config.downloaders && config.downloaders.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular"
    >
      <div
        v-for="downloader in config.downloaders"
        :key="downloader.id"
        class="ui-settings-card h-full"
      >
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h4 class="m-none text-body font-semibold text-color">
              {{ downloader.name || $t('settings.downloader.unnamed') }}
            </h4>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag :value="downloader.type" tone="accent" />
            <AppTag
              v-if="config.download.default_downloader_id === downloader.id"
              :value="$t('common.default')"
              tone="success"
            />
            <ToggleSwitch
              :model-value="downloader.enabled"
              :input-id="`downloader-enabled-${downloader.id}`"
              @update:model-value="toggleDownloaderEnabled(downloader)"
            />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p class="info-item m-none">
              <strong class="font-semibold">{{ $t('common.url') }}:</strong> {{ downloader.url || $t('common.unset') }}
            </p>
            <p class="info-item m-none">
              <strong class="font-semibold">{{ $t('common.username') }}:</strong>
              {{ downloader.username || $t('common.unset') }}
            </p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button
            v-if="config.download.default_downloader_id !== downloader.id"
            :label="$t('common.setDefault')"
            severity="secondary"
            outlined
            size="small"
            @click="setDefaultDownloader(downloader.id)"
          />
          <Button
            :label="$t('common.edit')"
            severity="secondary"
            outlined
            size="small"
            @click="editDownloader(downloader)"
          />
          <Button
            :label="$t('settings.downloader.testConnection')"
            severity="secondary"
            outlined
            size="small"
            :loading="testLoading && currentTestingDownloader === downloader.id"
            @click="testDownloaderConnection(downloader)"
          />
          <Button
            :label="$t('common.delete')"
            severity="secondary"
            outlined
            size="small"
            @click="removeDownloader(downloader.id)"
          />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addDownloader">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular"
    >
      <button type="button" class="ui-settings-add-card" @click="addDownloader">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Downloader editor dialog -->
    <ConfigDialog
      v-model:visible="downloaderDialogVisible"
      :title="dialogTitle"
      size="md"
      :intro="$t('settings.downloader.intro')"
    >
      <div class="ui-dialog-section">
        <label for="dialog-downloader-name" class="ui-dialog-item-title block">{{ $t('settings.downloader.name') }}</label>
        <InputText
          id="dialog-downloader-name"
          v-model="currentDownloader.name"
          :placeholder="$t('settings.downloader.namePlaceholder')"
          class="w-full"
        />
      </div>

      <!-- Downloader type -->
      <div class="ui-dialog-section">
        <label for="dialog-downloader-type" class="ui-dialog-item-title block">{{ $t('settings.downloader.type') }}</label>
        <Select
          v-model="currentDownloader.type"
          input-id="dialog-downloader-type"
          :options="availableDownloaderTypes"
          option-label="label"
          option-value="value"
          class="w-full"
          :disabled="dialogMode === 'edit'"
        />
      </div>

      <!-- HTTP downloader fields -->
      <template v-if="usesHttpDownloaderFields">
        <div class="ui-dialog-section">
          <label for="dialog-downloader-url" class="ui-dialog-item-title block">{{ $t('common.url') }}</label>
          <InputText
            id="dialog-downloader-url"
            v-model="currentDownloader.url"
            :placeholder="$t('settings.downloader.urlPlaceholder')"
            class="w-full"
            :disabled="dialogMode === 'edit'"
          />
          <span v-if="dialogMode === 'edit'" class="ui-dialog-help">{{ $t('settings.downloader.urlLocked') }}</span>
        </div>
        <div class="ui-dialog-section">
          <label for="dialog-downloader-username" class="ui-dialog-item-title block">{{ $t('common.username') }}</label>
          <InputText
            id="dialog-downloader-username"
            v-model="currentDownloader.username"
            :placeholder="$t('common.username')"
            class="w-full"
            autocomplete="off"
            name="downloader-service-user"
            data-lpignore="true"
          />
        </div>
        <div class="ui-dialog-section">
          <label for="dialog-downloader-password" class="ui-dialog-item-title block">{{ $t('common.password') }}</label>
          <InputText
            id="dialog-downloader-password"
            v-model="currentDownloader.password"
            type="password"
            :placeholder="$t('common.password')"
            class="w-full"
            autocomplete="new-password"
            name="downloader-service-secret"
            data-lpignore="true"
          />
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.downloader.directoryMapping') }}</label>
          <div
            v-if="
              currentDownloader.path_mappings &&
                currentDownloader.path_mappings.length > 0
            "
            class="mapping-list"
          >
            <div
              v-for="(mapping, index) in currentDownloader.path_mappings"
              :key="index"
              class="ui-surface-item"
            >
              <div class="directory-mapping">
                <InputText
                  v-model="mapping.remote_path"
                  :placeholder="$t('settings.downloader.remotePathPlaceholder', { index: index + 1 })"
                  class="flex-1"
                />
                <span class="mapping-separator font-bold">:</span>
                <InputText
                  v-model="mapping.local_path"
                  :placeholder="$t('settings.downloader.localPathPlaceholder', { index: index + 1 })"
                  class="flex-1"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  @click="removeDownloaderMapping(index)"
                />
              </div>
            </div>
          </div>
          <div
            v-else
            class="mapping-empty-state"
          >
            {{ $t('settings.downloader.noMappings') }}
          </div>
          <Button
            :label="$t('settings.downloader.addMapping')"
            icon="pi pi-plus"
            severity="primary"
            outlined
            class="w-full mt-item"
            @click="addDownloaderMapping"
          />
        </div>
      </template>

      <!-- Common fields -->
      <div class="ui-dialog-section">
        <label for="dialog-downloader-enabled" class="ui-dialog-item-title block">{{ $t('settings.downloader.enabledStatus') }}</label>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="flex items-center gap-item">
            <ToggleSwitch
              :model-value="currentDownloader.enabled"
              input-id="dialog-downloader-enabled"
              @update:model-value="updateDialogDownloaderEnabled"
            />
            <span class="text-muted-size text-muted-size font-muted text-muted">{{
              currentDownloader.enabled ? $t('common.enabled') : $t('common.disabled')
            }}</span>
          </div>
          <div class="flex items-center gap-item">
            <ToggleSwitch
              :model-value="currentDownloaderIsDefault"
              input-id="dialog-downloader-default"
              @update:model-value="updateDialogDownloaderDefault"
            />
            <span class="text-muted-size text-muted-size font-muted text-muted">{{
              currentDownloaderIsDefault ? $t('settings.downloader.defaultDownloader') : $t('common.setDefault')
            }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          severity="secondary"
          text
          @click="downloaderDialogVisible = false"
        />
        <Button :label="$t('common.save')" severity="primary" @click="saveDownloader" />
      </template>
    </ConfigDialog>
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import { useConfirm } from 'primevue/useconfirm'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useNotificationStore } from '@/stores/notification'
import {
  clearDefaultDownloader,
  createDownloader,
  deleteDownloader,
  getDownloaderUsage,
  setDefaultDownloaderEntry,
  testServiceConnection,
  updateDownloader,
} from '@/api/config'

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

const emit = defineEmits(['save'])

const confirm = useConfirm()
const notification = useNotificationStore()
const { t } = useI18n()

const downloaderDialogVisible = ref(false)
const currentDownloader = ref(createEmptyDownloader())
const currentDownloaderIsDefault = ref(false)
const dialogTitle = ref('')
const dialogMode = ref('add')
const testLoading = ref(false)
const currentTestingDownloader = ref(null)

const availableDownloaderTypes = computed(() => [
  { value: 'qbittorrent', label: t('settings.downloader.qbittorrent') },
  { value: 'rtorrent', label: t('settings.downloader.rtorrent') },
])

const usesHttpDownloaderFields = computed(() => ['qbittorrent', 'rtorrent'].includes(currentDownloader.value.type))

function createEmptyDownloader() {
  return {
    id: '',
    name: '',
    type: 'qbittorrent',
    enabled: true,
    url: '',
    username: '',
    password: '',
    path_mappings: [],
  }
}

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value))
}

function normalizeDownloader(downloader) {
  return {
    ...createEmptyDownloader(),
    ...(downloader || {}),
    path_mappings: Array.isArray(downloader?.path_mappings) ? cloneValue(downloader.path_mappings) : [],
  }
}

function getDownloadConfig() {
  return props.config.download || { default_downloader_id: null }
}

function getDownloaders() {
  return Array.isArray(props.config.downloaders) ? props.config.downloaders : []
}

function patchDownloaderConfig(downloaders, defaultDownloaderId = getDownloadConfig().default_downloader_id || null) {
  props.applyConfigPatch({
    downloaders,
    download: {
      ...getDownloadConfig(),
      default_downloader_id: defaultDownloaderId,
    },
  })
}

function addDownloader() {
  dialogTitle.value = t('settings.downloader.addTitle')
  dialogMode.value = 'add'
  currentDownloader.value = normalizeDownloader({
    id: `downloader_${Date.now()}`,
    name: t('settings.downloader.newQbittorrent'),
  })
  currentDownloaderIsDefault.value = !getDownloadConfig().default_downloader_id
  downloaderDialogVisible.value = true
}

function editDownloader(downloader) {
  dialogTitle.value = t('settings.downloader.editTitle')
  dialogMode.value = 'edit'
  currentDownloader.value = normalizeDownloader(downloader)
  currentDownloaderIsDefault.value = getDownloadConfig().default_downloader_id === downloader.id
  downloaderDialogVisible.value = true
}

function addDownloaderMapping() {
  if (!Array.isArray(currentDownloader.value.path_mappings)) {
    currentDownloader.value.path_mappings = []
  }
  currentDownloader.value.path_mappings.push({
    remote_path: '',
    local_path: '',
  })
}

function removeDownloaderMapping(index) {
  if (!Array.isArray(currentDownloader.value.path_mappings)) return
  currentDownloader.value.path_mappings.splice(index, 1)
}

async function saveDownloader() {
  const previousDefaultDownloaderId = getDownloadConfig().default_downloader_id || null
  const currentDownloaders = cloneValue(getDownloaders())

  try {
    const payload = { downloader: currentDownloader.value }
    let nextDownloaders = currentDownloaders
    if (dialogMode.value === 'add') {
      await createDownloader(payload)
      nextDownloaders = [...currentDownloaders, cloneValue(currentDownloader.value)]
    } else {
      await updateDownloader(currentDownloader.value.id, payload)
      const index = currentDownloaders.findIndex((item) => item.id === currentDownloader.value.id)
      if (index !== -1) {
        nextDownloaders = [...currentDownloaders]
        nextDownloaders[index] = cloneValue(currentDownloader.value)
      }
    }

    let nextDefaultDownloaderId = previousDefaultDownloaderId
    if (currentDownloaderIsDefault.value) {
      await setDefaultDownloaderEntry(currentDownloader.value.id)
      nextDefaultDownloaderId = currentDownloader.value.id
    } else if (previousDefaultDownloaderId === currentDownloader.value.id) {
      await clearDefaultDownloader()
      nextDefaultDownloaderId = null
    }

    patchDownloaderConfig(nextDownloaders, nextDefaultDownloaderId)
    downloaderDialogVisible.value = false
    emit('save')
    notification.success(dialogMode.value === 'add' ? t('settings.downloader.added') : t('settings.downloader.updated'))
  } catch (error) {
    if (!error?.response) {
      notification.error(t('common.saveFailed', { message: error.message || t('common.unknownError') }))
    }
  }
}

async function removeDownloader(downloaderId) {
  const downloaders = getDownloaders()
  const downloader = downloaders.find((item) => item.id === downloaderId)
  if (!downloader) return

  let usage = { task_count: 0, subscription_count: 0, directory_count: 0, is_default: false }
  try {
    usage = (await getDownloaderUsage(downloaderId)).usage
  } catch (error) {
    notification.error(t('settings.downloader.usageLoadFailed', { message: error.message }))
    return
  }

  const warnings = []
  if (usage.task_count > 0) warnings.push(t('settings.downloader.deleteWarningTask', { count: usage.task_count }))
  if (usage.directory_count > 0) warnings.push(t('settings.downloader.deleteWarningDirectory', { count: usage.directory_count }))
  if (usage.is_default) warnings.push(t('settings.downloader.deleteWarningDefault'))
  const detail = warnings.length > 0 ? `\n\n${t('settings.downloader.deleteImpact')}\n- ${warnings.join('\n- ')}` : ''

  confirm.require({
    message: t('settings.downloader.deleteMessage', { name: downloader.name || t('settings.downloader.unnamed'), detail }),
    header: t('settings.downloader.deleteHeader'),
    rejectLabel: t('common.cancel'),
    acceptLabel: t('settings.downloader.confirmDelete'),
    rejectProps: {
      severity: 'secondary',
      outlined: true,
    },
    acceptProps: {
      severity: 'primary',
    },
    accept: async () => {
      try {
        await deleteDownloader(downloaderId)
        const nextDownloaders = downloaders.filter((item) => item.id !== downloaderId)
        const nextDefaultDownloaderId = getDownloadConfig().default_downloader_id === downloaderId ? null : getDownloadConfig().default_downloader_id
        patchDownloaderConfig(nextDownloaders, nextDefaultDownloaderId)
        emit('save')
        notification.success(t('settings.downloader.deleted'))
      } catch (error) {
        if (!error?.response) {
          notification.error(t('common.deleteFailed', { message: error.message || t('common.unknownError') }))
        }
      }
    },
  })
}

async function setDefaultDownloader(downloaderId) {
  try {
    await setDefaultDownloaderEntry(downloaderId)
    patchDownloaderConfig(getDownloaders(), downloaderId)
    emit('save')
    notification.success(t('settings.downloader.defaultSet'))
  } catch (error) {
    if (!error?.response) {
      notification.error(t('common.settingFailed', { message: error.message || t('common.unknownError') }))
    }
  }
}

async function toggleDownloaderEnabled(downloader) {
  const downloaders = cloneValue(getDownloaders())
  const index = downloaders.findIndex((item) => item.id === downloader.id)
  if (index === -1) return

  const previousDefaultDownloaderId = getDownloadConfig().default_downloader_id || null
  const nextEnabled = !downloaders[index].enabled
  downloaders[index].enabled = nextEnabled

  let nextDefaultDownloaderId = previousDefaultDownloaderId
  if (!nextEnabled && props.config.download.default_downloader_id === downloader.id) {
    nextDefaultDownloaderId = null
  }

  try {
    await updateDownloader(downloader.id, {
      downloader: downloaders[index],
    })
    if (!nextEnabled && previousDefaultDownloaderId === downloader.id) {
      await clearDefaultDownloader()
    }
    patchDownloaderConfig(downloaders, nextDefaultDownloaderId)
    emit('save')
    notification.success(nextEnabled ? t('settings.downloader.enabled') : t('settings.downloader.disabled'))
  } catch (error) {
    if (!error?.response) {
      notification.error(t('common.settingFailed', { message: error.message || t('common.unknownError') }))
    }
  }
}

async function testDownloaderConnection(downloader) {
  if (!downloader.url) {
    notification.warn(t('settings.downloader.urlRequired'))
    return
  }

  testLoading.value = true
  currentTestingDownloader.value = downloader.id

  try {
    await testServiceConnection({
      type: downloader.type,
      config: {
        url: downloader.url,
        username: downloader.username || '',
        password: downloader.password || '',
      },
    })
    notification.success(t('common.connectionSuccess'))
  } catch (error) {
    console.error(t('settings.downloader.connectionTestFailed'), error)
  } finally {
    testLoading.value = false
    currentTestingDownloader.value = null
  }
}

function updateDialogDownloaderEnabled(enabled) {
  currentDownloader.value.enabled = enabled
  if (!enabled) {
    currentDownloaderIsDefault.value = false
  }
}

function updateDialogDownloaderDefault(isDefault) {
  currentDownloaderIsDefault.value = isDefault
  if (isDefault) {
    currentDownloader.value.enabled = true
  }
}

defineExpose({
  addDownloader,
  editDownloader,
  removeDownloader,
})
</script>

<style scoped>
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

.status-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-item);
  margin-top: var(--spacing-item);
}

/* Empty state styles */
.no-downloaders {
  text-align: center;
  padding: var(--spacing-section);
  color: var(--text-muted);
  background-color: var(--surface-subtle);
  border-radius: var(--radius-container);
}
</style>
