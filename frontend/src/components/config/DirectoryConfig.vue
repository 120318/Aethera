<template>
  <div class="flex flex-col gap-container">
    <!-- Directory card grid -->
    <div
      v-if="config.directories && config.directories.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-tall"
    >
      <div
        v-for="directory in config.directories" :key="directory.id"
        class="ui-settings-card h-full"
      >
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h4 class="m-0 text-body font-semibold text-color">{{ directory.name || $t('settings.directory.unnamed') }}</h4>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag :value="directory.media_type === 'movie' ? $t('settings.directory.movie') : $t('settings.directory.tv')" tone="accent" />
            <AppTag
              v-if="directory.is_default"
              :value="$t('common.default')"
              tone="success"
            />
            <ToggleSwitch
              :model-value="directory.enabled"
              :input-id="`directory-enabled-${directory.id}`"
              @update:model-value="toggleDirectoryEnabled(directory)"
            />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.path') }}</strong> {{ directory.path || $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.downloadPath') }}</strong> {{ directory.download_path ||
              $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.mediaServer') }}</strong> {{
              getMediaServerName(directory.media_server_id) || $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.downloader') }}</strong> {{
              getDownloaderName(directory.downloader_id) || $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.downloaderCategory') }}</strong> {{
              directory.download_category || directory.downloader_category || $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.namingTemplate') }}</strong> {{
              getTemplateName(directory) || $t('common.unset') }}</p>
            <p class="info-item m-0"><strong class="font-semibold">{{ $t('settings.directory.transferMode') }}</strong> {{
              formatTransferMode(directory.transfer_mode) }}</p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button
            v-if="!directory.is_default"
            :label="$t('common.setDefault')"
            severity="secondary"
            outlined
            size="small"
            @click="setDefaultDirectory(directory.id)"
          />
          <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="editDirectory(directory)" />
          <Button
            :label="$t('settings.directory.testPermission')" severity="secondary" outlined size="small" :loading="testLoading && currentTestingDirectory === directory.id"
            @click="testDirectoryPermissions(directory)"
          />
          <Button :label="$t('settings.directory.migrate')" severity="secondary" outlined size="small" @click="openMigrationDialog(directory)" />
          <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="removeDirectory(directory.id)" />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addDirectory">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-tall"
    >
      <button type="button" class="ui-settings-add-card" @click="addDirectory">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Directory editor dialog -->
    <ConfigDialog
      v-model:visible="directoryDialogVisible"
      :title="directoryDialogTitle"
      size="md"
      :intro="$t('settings.directory.intro')"
    >
      <div class="ui-dialog-section">
        <label for="dialog-directory-name" class="ui-dialog-item-title block">{{ $t('settings.directory.name') }}</label>
        <InputText id="dialog-directory-name" v-model="currentDirectory.name" :placeholder="$t('settings.directory.namePlaceholder')" class="w-full" />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-directory-media-type" class="ui-dialog-item-title block">{{ $t('settings.directory.mediaType') }}</label>
        <div class="flex flex-wrap gap-container">
          <div class="flex items-center gap-item">
            <RadioButton v-model="currentDirectory.media_type" input-id="mediaType1" name="mediaType" value="movie" />
            <label for="mediaType1">{{ $t('settings.directory.movie') }}</label>
          </div>
          <div class="flex items-center gap-item">
            <RadioButton v-model="currentDirectory.media_type" input-id="mediaType2" name="mediaType" value="tv" />
            <label for="mediaType2">{{ $t('settings.directory.tv') }}</label>
          </div>
        </div>
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-directory-path" class="ui-dialog-item-title block">{{ $t('settings.directory.directoryPath') }}</label>
        <InputText
          id="dialog-directory-path" v-model="currentDirectory.path" :placeholder="$t('settings.directory.directoryPathPlaceholder')"
          class="w-full" :disabled="directoryPathInputLocked"
        />
        <span v-if="directoryDialogMode === 'edit' && isPathLocked" class="ui-dialog-help">{{ $t('settings.directory.pathLocked') }}</span>
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-directory-download-path" class="ui-dialog-item-title block">{{ $t('settings.directory.downloadPathLabel') }}</label>
        <InputText
          id="dialog-directory-download-path" v-model="currentDirectory.download_path"
          :placeholder="$t('settings.directory.downloadPathPlaceholder')" class="w-full" :disabled="directoryDownloadPathInputLocked"
        />
        <span v-if="directoryDialogMode === 'edit' && isDownloadPathLocked" class="ui-dialog-help">{{ $t('settings.directory.downloadPathLocked') }}</span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-container">
        <div v-if="currentDirectory.media_type === 'movie'" class="ui-dialog-section">
          <label for="dialog-directory-movie-template" class="ui-dialog-item-title block">{{ $t('settings.directory.movieTemplate') }}</label>
          <Select
            v-model="currentDirectory.movie_template_id" input-id="dialog-directory-movie-template"
            :placeholder="$t('settings.directory.selectMovieTemplate')" class="w-full" :options="movieTemplates" option-label="name"
            option-value="id" show-clear
          />
        </div>

        <div v-else-if="currentDirectory.media_type === 'tv'" class="ui-dialog-section">
          <label for="dialog-directory-tv-template" class="ui-dialog-item-title block">{{ $t('settings.directory.tvTemplate') }}</label>
          <Select
            v-model="currentDirectory.tv_template_id" input-id="dialog-directory-tv-template"
            :placeholder="$t('settings.directory.selectTvTemplate')" class="w-full" :options="tvTemplates" option-label="name" option-value="id"
            show-clear
          />
        </div>

        <div class="ui-dialog-section">
          <label for="dialog-directory-transfer-mode" class="ui-dialog-item-title block">{{ $t('settings.directory.transferModeLabel') }}</label>
          <Select
            v-model="currentDirectory.transfer_mode"
            input-id="dialog-directory-transfer-mode"
            :options="transferModeOptions"
            option-label="label"
            option-value="value"
            class="w-full"
          />
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-container">
        <div class="ui-dialog-section">
          <label for="dialog-directory-downloader" class="ui-dialog-item-title block">{{ $t('settings.directory.downloader').replace(':', '') }}</label>
          <Select
            v-model="currentDirectory.downloader_id" input-id="dialog-directory-downloader" :placeholder="$t('settings.directory.selectDownloader')"
            class="w-full" :options="config.downloaders" option-label="name" option-value="id" show-clear
          />
        </div>

        <div class="ui-dialog-section">
          <label for="dialog-directory-downloader-category" class="ui-dialog-item-title block">{{ $t('settings.directory.category') }}</label>
          <InputText
            id="dialog-directory-downloader-category" v-model="currentDirectory.downloader_category"
            :placeholder="$t('settings.directory.categoryPlaceholder')" class="w-full"
          />
        </div>
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-directory-media-server" class="ui-dialog-item-title block">{{ $t('settings.directory.mediaServer').replace(':', '') }}</label>
        <Select
          v-model="currentDirectory.media_server_id" input-id="dialog-directory-media-server"
          :placeholder="$t('settings.directory.selectMediaServer')" class="w-full" :options="config.media_servers" option-label="name" option-value="id"
          show-clear
        />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-directory-enabled" class="ui-dialog-item-title block">{{ $t('settings.indexer.enabledLabel') }}</label>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="flex items-center gap-item">
            <ToggleSwitch v-model="currentDirectory.enabled" input-id="dialog-directory-enabled" />
            <span class="text-muted-size text-muted-size font-muted text-muted">{{ currentDirectory.enabled ? $t('common.enabled') :
              $t('common.disabled')
            }}</span>
          </div>
          <div class="flex items-center gap-item">
            <ToggleSwitch v-model="currentDirectory.is_default" input-id="dialog-directory-is-default" />
            <span class="text-muted-size text-muted-size font-muted text-muted">{{ currentDirectory.is_default ? $t('settings.directory.defaultDirectory') :
              $t('common.setDefault')
            }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="directoryDialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" @click="saveDirectory" />
      </template>
    </ConfigDialog>
    <ConfigDialog
      v-model:visible="migrationDialogVisible"
      :title="$t('settings.directory.migrationTitle')"
      size="sm"
    >
      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.directory.targetDirectory') }}</label>
        <Select
          v-model="migrationForm.target_directory_id"
          :options="migrationTargetDirectories"
          option-label="name"
          option-value="id"
          class="w-full"
          :disabled="migrationLoading || migrationSubmitting"
          @change="migrationPreview = null"
        />
      </div>
      <div v-if="migrationPreview" class="ui-dialog-section text-caption text-muted">
        {{ resolveMigrationPreviewMessage() }}
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="migrationDialogVisible = false" />
        <Button :label="$t('settings.directory.previewMigration')" severity="secondary" outlined :loading="migrationLoading" @click="previewMigration" />
        <Button :label="$t('settings.directory.startMigration')" severity="primary" :disabled="!migrationPreview?.ok" :loading="migrationSubmitting" @click="submitMigration" />
      </template>
    </ConfigDialog>
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import RadioButton from 'primevue/radiobutton'
import { useConfirm } from 'primevue/useconfirm'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useDirectoryUsageLocks } from '@/composables/useDirectoryUsageLocks'
import {
  createDirectory,
  deleteDirectoryEntry,
  previewDirectoryMigration,
  setDefaultDirectoryEntry,
  submitDirectoryMigration,
  testDirectoryAccess,
  updateDirectoryEntry,
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

defineEmits(['save'])

const confirm = useConfirm()
const notification = useNotificationStore()
const { t } = useI18n()

const directoryDialogVisible = ref(false)
const currentDirectory = ref(createEmptyDirectory())
const directoryDialogTitle = ref('')
const directoryDialogMode = ref('add')
const originalDirectory = ref(null)
const testLoading = ref(false)
const currentTestingDirectory = ref(null)
const migrationDialogVisible = ref(false)
const migrationSourceDirectory = ref(null)
const migrationForm = ref({ target_directory_id: '' })
const migrationPreview = ref(null)
const migrationLoading = ref(false)
const migrationSubmitting = ref(false)
const {
  usageLoading,
  isPathLocked,
  isDownloadPathLocked,
  loadDirectoryUsage,
  validateDirectoryPathChanges,
} = useDirectoryUsageLocks()

const movieTemplates = computed(() => {
  if (!Array.isArray(props.config.naming_templates)) return []
  return props.config.naming_templates.filter((template) => template.type === 'movie' && template.enabled)
})

const tvTemplates = computed(() => {
  if (!Array.isArray(props.config.naming_templates)) return []
  return props.config.naming_templates.filter((template) => template.type === 'tv' && template.enabled)
})

const transferModeOptions = computed(() => [
  { label: t('settings.directory.transferModes.hardlink'), value: 'hardlink' },
  { label: t('settings.directory.transferModes.copy'), value: 'copy' },
])

const migrationTargetDirectories = computed(() => {
  const source = migrationSourceDirectory.value
  if (!source) return []
  return getDirectories().filter((item) => (
    item.enabled !== false
    && item.id !== source.id
    && normalizeMediaType(item.media_type) === normalizeMediaType(source.media_type)
  ))
})

const directoryPathInputLocked = computed(() => directoryDialogMode.value === 'edit' && (usageLoading.value || isPathLocked.value))
const directoryDownloadPathInputLocked = computed(() => directoryDialogMode.value === 'edit' && (usageLoading.value || isDownloadPathLocked.value))

function createEmptyDirectory() {
  return {
    id: '',
    name: '',
    path: '',
    download_path: '',
    download_category: '',
    media_type: 'movie',
    enabled: true,
    is_default: false,
    media_server_id: null,
    downloader_id: null,
    downloader_category: '',
    movie_template_id: null,
    tv_template_id: null,
    transfer_mode: 'hardlink',
  }
}

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value))
}

function normalizeDirectory(directory) {
  const normalized = {
    ...createEmptyDirectory(),
    ...(directory || {}),
  }
  normalized.downloader_category = normalized.downloader_category || normalized.download_category || ''
  normalized.download_category = normalized.download_category || normalized.downloader_category || ''
  normalized.transfer_mode = normalized.transfer_mode || 'hardlink'
  return normalized
}

function buildDirectoryPayload(directory) {
  const payload = normalizeDirectory(directory)
  payload.downloader_category = payload.downloader_category || payload.download_category || ''
  return payload
}

function getDirectories() {
  return Array.isArray(props.config.directories) ? props.config.directories : []
}

function normalizeMediaType(mediaType) {
  return String(mediaType || '').includes('tv') ? 'tv' : 'movie'
}

function shouldDefaultDirectory(mediaType) {
  const normalizedMediaType = normalizeMediaType(mediaType)
  return !getDirectories().some((item) => (
    normalizeMediaType(item?.media_type) === normalizedMediaType && item?.is_default
  ))
}

function patchDirectories(directories) {
  props.applyConfigPatch({ directories })
}

function addDirectory() {
  directoryDialogVisible.value = true
  directoryDialogTitle.value = t('settings.directory.addTitle')
  directoryDialogMode.value = 'add'
  originalDirectory.value = null
  currentDirectory.value = normalizeDirectory({
    id: `directory_${Date.now()}`,
    name: t('settings.directory.newDirectory'),
    is_default: shouldDefaultDirectory('movie'),
  })
}

async function editDirectory(directory) {
  directoryDialogVisible.value = true
  directoryDialogTitle.value = t('settings.directory.editTitle')
  directoryDialogMode.value = 'edit'
  const normalized = normalizeDirectory(cloneValue(directory))
  currentDirectory.value = normalized
  originalDirectory.value = cloneValue(normalized)
  try {
    await loadDirectoryUsage(directory.id)
  } catch (error) {
    notification.error(t('settings.directory.usageLoadFailed', { message: error.message }))
  }
}

watch(
  () => currentDirectory.value.media_type,
  (mediaType) => {
    if (directoryDialogMode.value !== 'add') return
    currentDirectory.value.is_default = shouldDefaultDirectory(mediaType)
  },
)

async function saveDirectory() {
  const directories = cloneValue(getDirectories())

  try {
    let nextDirectories = directories
    if (directoryDialogMode.value === 'add') {
      const response = await createDirectory(buildDirectoryPayload(currentDirectory.value))
      const savedDirectory = response.directory
      if (savedDirectory.is_default) {
        nextDirectories = directories.map((item) => {
          if (item.media_type === savedDirectory.media_type) {
            return { ...item, is_default: false }
          }
          return item
        })
      }
      nextDirectories = [...nextDirectories, { ...savedDirectory }]
    } else {
      const guard = await validateDirectoryPathChanges(originalDirectory.value, currentDirectory.value)
      if (!guard.allowed) {
        const key = guard.reason === 'path' ? 'settings.directory.pathLocked' : 'settings.directory.downloadPathLocked'
        notification.warn(t(key))
        return
      }
      const response = await updateDirectoryEntry(buildDirectoryPayload(currentDirectory.value))
      const savedDirectory = response.directory
      const index = directories.findIndex((item) => item.id === currentDirectory.value.id)
      if (index !== -1) {
        nextDirectories = [...directories]
        if (savedDirectory.is_default) {
          nextDirectories = nextDirectories.map((item, itemIndex) => {
            if (itemIndex !== index && item.media_type === savedDirectory.media_type) {
              return { ...item, is_default: false }
            }
            return item
          })
        }
        nextDirectories[index] = { ...savedDirectory }
      }
    }
    patchDirectories(nextDirectories)
    directoryDialogVisible.value = false
    notification.success(directoryDialogMode.value === 'add' ? t('settings.directory.added') : t('settings.directory.updated'))
  } catch (error) {
    notification.error(t('common.saveFailed', { message: error.message }))
  }
}

async function removeDirectory(id) {
  const directories = getDirectories()
  const directory = directories.find((item) => item.id === id)
  if (!directory) return

  if (directory.is_default) {
    notification.warn(t('settings.directory.defaultCannotDelete'))
    return
  }

  let usage = { task_count: 0, subscription_count: 0, directory_count: 0, is_default: false }
  try {
    usage = await loadDirectoryUsage(id)
  } catch (error) {
    notification.error(t('settings.directory.usageLoadFailed', { message: error.message }))
    return
  }

  const warnings = []
  if (usage.task_count > 0) warnings.push(t('settings.directory.deleteWarningTask', { count: usage.task_count }))
  if (usage.subscription_count > 0) warnings.push(t('settings.directory.deleteWarningSubscription', { count: usage.subscription_count }))
  if (usage.library_file_count > 0) warnings.push(t('settings.directory.deleteWarningLibraryFile', { count: usage.library_file_count }))
  const detail = warnings.length > 0 ? `\n\n${t('settings.directory.deleteImpact')}\n- ${warnings.join('\n- ')}` : ''

  confirm.require({
    message: t('settings.directory.deleteMessage', { name: directory.name || t('settings.directory.unnamed'), detail }),
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
        await deleteDirectoryEntry(id)
        patchDirectories(directories.filter((item) => item.id !== id))
        notification.success(t('settings.directory.deleted'))
      } catch (error) {
        notification.error(t('common.deleteFailed', { message: error.message }))
      }
    },
  })
}

async function setDefaultDirectory(directoryId) {
  const directories = cloneValue(getDirectories())
  const directory = directories.find((item) => item.id === directoryId)
  if (!directory) {
    notification.error(t('settings.directory.notFound'))
    return
  }

  const mediaType = String(directory.media_type || '').includes('tv') ? 'tv' : 'movie'
  const nextDirectories = directories.map((item) => {
    const itemMediaType = String(item.media_type || '').includes('tv') ? 'tv' : 'movie'
    if (itemMediaType === mediaType) {
      return { ...item, is_default: false }
    }
    return item
  }).map((item) => item.id === directoryId ? { ...item, is_default: true } : item)

  try {
    await setDefaultDirectoryEntry({
      directory_id: directoryId,
      media_type: mediaType,
    })
    patchDirectories(nextDirectories)
    notification.success(t('settings.directory.defaultSet', { type: mediaType === 'movie' ? t('settings.directory.movie') : t('settings.directory.tv') }))
  } catch {
    notification.error(t('settings.directory.defaultSetFailed'))
  }
}

async function toggleDirectoryEnabled(directory) {
  const directories = cloneValue(getDirectories())
  const index = directories.findIndex((item) => item.id === directory.id)
  if (index === -1) return

  const nextEnabled = !directories[index].enabled
  directories[index].enabled = nextEnabled

  if (!nextEnabled && directories[index].is_default) {
    directories[index].is_default = false
  }

  try {
    await updateDirectoryEntry(directories[index])
    patchDirectories(directories)
    notification.success(nextEnabled ? t('settings.directory.enabled') : t('settings.directory.disabled'))
  } catch (error) {
    notification.error(t('common.settingFailed', { message: error.message }))
  }
}

function openMigrationDialog(directory) {
  migrationSourceDirectory.value = directory
  migrationPreview.value = null
  migrationForm.value = {
    target_directory_id: migrationTargetDirectories.value[0]?.id || '',
  }
  migrationDialogVisible.value = true
}

async function previewMigration() {
  if (!migrationSourceDirectory.value || !migrationForm.value.target_directory_id) return
  migrationLoading.value = true
  try {
    migrationPreview.value = await previewDirectoryMigration(migrationSourceDirectory.value.id, migrationForm.value)
  } catch (error) {
    notification.error(error.message || t('settings.directory.migrationPreviewFailed'))
  } finally {
    migrationLoading.value = false
  }
}

async function submitMigration() {
  if (!migrationSourceDirectory.value || !migrationPreview.value?.ok) return
  migrationSubmitting.value = true
  try {
    const result = await submitDirectoryMigration(migrationSourceDirectory.value.id, migrationForm.value)
    notification.success(t('settings.directory.migrationSubmitted', {
      count: result.commands?.length || 0,
      subscriptions: result.migrated_subscription_count || 0,
    }))
    migrationDialogVisible.value = false
  } catch (error) {
    notification.error(error.message || t('settings.directory.migrationSubmitFailed'))
  } finally {
    migrationSubmitting.value = false
  }
}

function resolveMigrationPreviewMessage() {
  const preview = migrationPreview.value
  if (!preview) return ''
  if (!preview.ok) return t('settings.directory.migrationBlocked', { reason: formatMigrationReasons(preview.blockers) })
  return t('settings.directory.migrationPreviewPassed', {
    tasks: preview.migratable_task_count || 0,
    files: preview.library_file_count || 0,
    subscriptions: preview.migratable_subscription_count || 0,
  })
}

function formatMigrationReasons(reasons = []) {
  const values = Array.isArray(reasons) ? reasons : []
  const labels = values.map((reason) => t(`settings.directory.migrationBlockers.${reason}`, reason))
  return labels.length ? labels.join('；') : '-'
}

function getMediaServerName(serverId) {
  if (!serverId || !Array.isArray(props.config.media_servers)) return ''
  const server = props.config.media_servers.find((item) => item.id === serverId)
  return server ? server.name : ''
}

function getDownloaderName(downloaderId) {
  if (!downloaderId || !Array.isArray(props.config.downloaders)) return ''
  const downloader = props.config.downloaders.find((item) => item.id === downloaderId)
  return downloader ? downloader.name : ''
}

function getTemplateName(directory) {
  if (!directory || !Array.isArray(props.config.naming_templates)) return ''
  const templateId = directory.media_type === 'movie' ? directory.movie_template_id : directory.tv_template_id
  if (!templateId) return ''
  const template = props.config.naming_templates.find((item) => item.id === templateId)
  return template ? template.name : ''
}

function formatTransferMode(mode) {
  return mode === 'copy' ? t('settings.directory.transferModes.copy') : t('settings.directory.transferModes.hardlink')
}

async function testDirectoryPermissions(directory) {
  testLoading.value = true
  currentTestingDirectory.value = directory.id

  try {
    const response = await testDirectoryAccess({
      path: directory.path,
    })
    const permissions = response.permissions
    if (permissions.exists && permissions.readable && permissions.writable) {
      notification.success(t('settings.directory.permissionOk'))
      return
    }

    let errorMessage = t('settings.directory.permissionFailedPrefix')
    if (!permissions.exists) {
      errorMessage += t('settings.directory.missing')
    } else {
      if (!permissions.readable) errorMessage += t('settings.directory.unreadable')
      if (!permissions.writable) errorMessage += t('settings.directory.unwritable')
    }
    notification.error(errorMessage)
  } catch (error) {
    notification.error(t('common.networkError', { message: error.message || error }))
  } finally {
    testLoading.value = false
    currentTestingDirectory.value = null
  }
}

defineExpose({
  addDirectory,
  editDirectory,
  removeDirectory,
  setDefaultDirectory,
})
</script>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-block);
}

.info-item {
  margin: 0;
  font-size: var(--text-small);
  line-height: 1.5;
  color: var(--text-muted);
}

.no-directories {
  text-align: center;
  padding: var(--spacing-section);
  color: var(--text-muted);
  background-color: var(--surface-subtle);
  border-radius: var(--radius-container);
}
</style>
