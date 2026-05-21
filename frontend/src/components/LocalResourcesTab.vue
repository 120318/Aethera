<template>
  <div class="animate-fadein">
    <div class="flex flex-col gap-container w-full min-h-tab-content">
      <!-- Header: Filters -->
      <div v-if="loading" class="resources-list">
        <div v-for="index in 3" :key="`resource-loading-${index}`" class="flex flex-col gap-inline py-container border-b border-separator last:border-0">
          <div class="flex items-start justify-between gap-item">
            <div class="flex flex-col gap-inline flex-1 min-w-0">
              <Skeleton width="72%" height="1rem" />
              <div class="flex flex-wrap gap-inline">
                <Skeleton v-for="tagIndex in 6" :key="`resource-loading-${index}-${tagIndex}`" width="4rem" height="1.25rem" border-radius="var(--radius-item)" />
              </div>
            </div>
            <div class="flex items-center gap-item">
              <Skeleton shape="circle" size="2rem" />
              <Skeleton shape="circle" size="2rem" />
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="seasonFilteredResources.length > 0" class="flex flex-col gap-item">
        <div v-if="showEpisodeFilterSkeleton" class="episode-grid local-resources-episode-grid">
          <Skeleton v-for="index in episodeSkeletonItems" :key="index" class="w-control-badge-sm h-control-badge-sm" />
        </div>
        <div v-else-if="showEpisodeFilter" class="episode-grid local-resources-episode-grid">
          <button
            v-for="episode in episodes"
            :key="episode"
            :class="getEpisodeButtonClass(episode)"
            :disabled="!isEpisodeExisting(episode)"
            @click="toggleEpisode(episode)"
          >
            {{ episode }}
          </button>
        </div>
        <div class="grid grid-cols-1 gap-item">
          <InputText v-model="localFilters.keyword" :placeholder="$t('resourceSearch.keywordFilter')" class="w-full" />
        </div>
      </div>

      <div v-if="showEmptyState" :class="emptyStateClass">
        <p class="text-title font-medium mb-item">{{ $t('localResources.emptyTitle') }}</p>
        <p class="text-caption text-muted">{{ $t('localResources.emptyDescription') }}</p>
      </div>

      <div v-else-if="seasonFilteredResources.length > 0" class="resources-list">
        <DataView
          :value="sortedResources"
          paginator
          :rows="RESOURCES_ROWS_PER_PAGE"
          layout="list"
          paginator-position="both"
          class="overflow-hidden ui-dataview-balanced-paginator"
          :pt="{
            header: { class: 'p-none' }
          }"
        >
          <template #paginatorstart>
            <div class="hidden md:flex items-center text-muted">
              {{ $t('taskLive.totalPrefix') }}
              <span class="text-primary mx-inline">{{ totalVisibleResources }}</span>
              {{ $t('resourceSearch.foundSuffix') }}
              <span v-if="filteredResources.length !== totalVisibleResources" class="text-muted ml-inline">
                {{ $t('resourceSearch.filteredCount', { count: filteredResources.length }) }}
              </span>
            </div>
          </template>

          <template #paginatorend>
            <div class="flex items-center gap-item ml-0 md:ml-block">
              <Button
                v-if="hasActiveFilters" severity="secondary" :label="$t('resourceSearch.clearFilters')" icon="pi pi-filter-slash" link
                size="small" @click="clearFilters"
              />
              <SortControl v-model="resourceSortModel" :options="resourceSortOptions" />
            </div>
          </template>

          <template #list="slotProps">
            <div
              v-for="(resource, index) in slotProps.items" :key="resource.id || resource.info_hash || index"
              class="flex flex-col gap-inline py-container relative border-b border-separator last:border-0 group"
            >
              <div class="flex flex-col sm:flex-row min-w-0 gap-item">
                <div class="flex flex-col flex-1 min-w-0 gap-inline">
                  <span class="text-body break-words whitespace-normal">
                    {{ resource.file_name || resource.resource_title || resource.name }}
                  </span>
                  <div class="flex items-center gap-x-inline gap-y-inline flex-wrap min-w-0">
                    <ResourceAttributes
                      :attributes="{ ...resource.attributes, directory: resource.directory_name }"
                      :created-at="resource.created_at"
                      :size="resource.size"
                      :visible-tags="localResourceVisibleTags"
                    />
                  </div>
                </div>
                <div class="flex items-start justify-end gap-item shrink-0">
                  <Button
                    v-if="isResourceActionAvailable(resource, 'media_server_open')"
                    v-tooltip.top="$t('localResources.openInMediaServer')"
                    icon="pi pi-external-link"
                    variant="text"
                    severity="secondary"
                    :loading="isResolvingMediaServerLink(resource)"
                    :disabled="isResolvingMediaServerLink(resource)"
                    @click="openResourceInMediaServer(resource)"
                  />
                  <Button
                    v-show="!isTorrentRemoved(resource)" v-tooltip.top="$t('taskLive.actions.detail')" icon="pi pi-info-circle"
                    variant="text" severity="secondary"
                    @click=" $emit('view-details', resource)"
                  />
                  <Button
                    v-tooltip.top="$t('common.delete')" icon="pi pi-trash" variant="text" severity="danger"
                    :loading="hasActiveDeleteCommand(resource)" :disabled="hasActiveDeleteCommand(resource)"
                    @click=" $emit('delete', resource)"
                  />
                  <Button
                    v-if="hasResourceMenu(resource)"
                    v-tooltip.top="$t('localResources.moreActions')"
                    icon="pi pi-ellipsis-v"
                    variant="text"
                    severity="secondary"
                    :loading="hasActiveResourceOperationCommand(resource)"
                    :disabled="hasActiveResourceOperationCommand(resource)"
                    @click="showResourceMenu($event, resource)"
                  />
                </div>
              </div>
            </div>
          </template>
        </DataView>
      </div>
    </div>
    <Menu
      ref="resourceMenuRef"
      :model="activeResourceMenuItems"
      class="resource-action-menu"
      popup
      append-to="body"
    />
    <Dialog v-model:visible="directoryChangeVisible" :header="$t('localResources.changeDirectory.title')" modal :dismissable-mask="true" class="w-full max-w-dialog-md">
      <div class="ui-dialog-body">
        <div class="ui-dialog-section">
          <label for="library-directory-change-target" class="ui-dialog-item-title block">{{ $t('localResources.changeDirectory.targetDirectory') }}</label>
          <Select
            v-model="directoryChangeForm.target_directory_id"
            input-id="library-directory-change-target"
            :options="directoryChangeTargetDirectories"
            option-label="name"
            option-value="id"
            class="w-full"
            :disabled="directoryChangeLoading || directoryChangeSubmitting"
            @change="directoryChangePreview = null"
          />
        </div>
      </div>
      <template #footer>
        <section class="w-full flex flex-col items-center gap-inline">
          <p
            v-if="directoryChangePreview"
            class="text-caption text-center m-none"
            :class="directoryChangePreview.blockers?.length ? 'text-danger' : 'text-muted'"
          >
            {{ resolveDirectoryChangePreviewMessage() }}
          </p>
          <div class="flex items-center justify-center gap-item flex-wrap w-full">
            <Button :label="$t('common.cancel')" severity="secondary" outlined @click="directoryChangeVisible = false" />
            <Button :label="$t('localResources.changeDirectory.preview')" severity="secondary" :loading="directoryChangeLoading" @click="previewDirectoryChange" />
            <Button
              :label="$t('localResources.changeDirectory.execute')"
              severity="primary"
              :loading="directoryChangeSubmitting"
              :disabled="!directoryChangePreview?.ok"
              @click="submitDirectoryChange"
            />
          </div>
        </section>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import InputText from 'primevue/inputtext'
import Skeleton from 'primevue/skeleton'
import Menu from 'primevue/menu'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import ResourceAttributes from './common/ResourceAttributes.vue'
import SortControl from '@/components/common/filter/SortControl.vue'
import { getDirectoriesTabConfig } from '@/api/config'
import { previewLibraryFileDirectoryChange, resolveLibraryMediaServerLink, submitLibraryFileDirectoryChange } from '@/api/resource'
import { ResourceTagType } from '@/constants/resourceTagTypes'
import { useLocalResourcesList } from '@/composables/useLocalResourcesList'
import { useLocalResourcesOverview } from '@/composables/useLocalResourcesOverview'
import { useOperationsStore } from '@/stores/operations'
import { useNotificationStore } from '@/stores/notification'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  mediaId: {
    type: String,
    default: ''
  },
  detail: {
    type: Object,
    default: () => ({})
  },
  overview: {
    type: Object,
    default: null
  },
  overviewLoading: {
    type: Boolean,
    default: false
  },
  resources: {
    type: Array,
    default: () => []
  },
  totalEpisodes: {
    type: Number,
    default: 0
  },
  tasks: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  detailLoading: {
    type: Boolean,
    default: false
  },
  operationCommands: {
    type: Array,
    default: null
  },
  seasonNumber: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['view-details', 'delete', 'command-submitted'])
const { t } = useI18n()
const operations = useOperationsStore()
const notification = useNotificationStore()
const resourceMenuRef = ref(null)
const activeResourceMenuItems = ref([])
const resolvingMediaServerLinkTargets = ref(new Set())
const directoryChangeVisible = ref(false)
const directoryChangeResource = ref(null)
const directoryChangeLoading = ref(false)
const directoryChangeSubmitting = ref(false)
const directoryChangePreview = ref(null)
const directoryChangeConfig = ref({ directories: [] })
const directoryChangeForm = ref({ target_directory_id: '' })

const RESOURCES_ROWS_PER_PAGE = 10
const LIBRARY_FILE_COMMAND_TYPES = [
  'library_file.delete',
  'library_file.storage_change',
  'library_file.media_server_sync',
  'library_file.danmu_generate',
]
const localResourceVisibleTags = [
  ResourceTagType.DIRECTORY,
  ResourceTagType.CREATED_AT,
  ResourceTagType.RESOURCE_FORM,
  ResourceTagType.PACKAGE_LAYOUT,
  ResourceTagType.DISC,
  ResourceTagType.RESOLUTION,
  ResourceTagType.VIDEO_CODEC,
  ResourceTagType.AUDIO_CODEC,
  ResourceTagType.HDR_TYPE,
  ResourceTagType.AUDIO_CHANNELS,
  ResourceTagType.COLOR_DEPTH,
  ResourceTagType.GROUP,
  ResourceTagType.SOURCE,
  ResourceTagType.LANGUAGE,
  ResourceTagType.SUBTITLE,
]

const {
  selectedEpisodes,
  seasonFilteredResources,
  showEpisodeFilter,
  showEpisodeFilterSkeleton,
  episodeSkeletonItems,
  episodes,
  isEpisodeExisting,
  toggleEpisode,
  getEpisodeButtonClass,
} = useLocalResourcesOverview(props)

const {
  localFilters,
  resourceSortModel,
  resourceSortOptions,
  hasActiveFilters,
  filteredResources,
  sortedResources,
  totalVisibleResources,
  clearFilters,
  isTorrentRemoved,
} = useLocalResourcesList(seasonFilteredResources, selectedEpisodes)

const showEmptyState = computed(() => (
  !props.loading && filteredResources.value.length === 0
))

const directoryChangeTargetDirectories = computed(() => {
  const resource = directoryChangeResource.value
  const currentDirectoryId = resource?.directory_id || ''
  const currentDirectory = directoryChangeConfig.value.directories.find(item => item.id === currentDirectoryId) || null
  return directoryChangeConfig.value.directories.filter((item) => (
    item.id !== currentDirectoryId
    && (!currentDirectory?.media_type || item.media_type === currentDirectory.media_type)
  ))
})

const emptyStateClass = computed(() => (
  showEpisodeFilter.value || showEpisodeFilterSkeleton.value
    ? 'flex flex-1 flex-col items-center justify-center gap-item text-center text-muted py-block'
    : 'ui-tab-empty'
))

function getResourceTargetId(resource) {
  return resource?.is_package ? resource.package_root : resource?.id
}

function getResourceActionState(resource, action) {
  const states = Array.isArray(resource?.action_states) ? resource.action_states : []
  return states.find(item => item?.action === action) || null
}

function isResourceActionAvailable(resource, action) {
  const state = getResourceActionState(resource, action)
  return !!state && state.available !== false
}

function isResolvingMediaServerLink(resource) {
  const targetId = getResourceTargetId(resource)
  return !!targetId && resolvingMediaServerLinkTargets.value.has(targetId)
}

function getActiveLibraryFileCommand(resource, commandTypes = LIBRARY_FILE_COMMAND_TYPES) {
  const targetId = getResourceTargetId(resource)
  if (!targetId) return null
  if (Array.isArray(props.operationCommands)) {
    return props.operationCommands.find(command => (
      command?.target_type === 'library_file'
      && command?.target_id === targetId
      && commandTypes.includes(command?.type)
    )) || null
  }
  return operations.getActiveCommandByTarget('library_file', targetId, commandTypes)
}

function isResourceActionBusy(resource, action, commandTypes) {
  const state = getResourceActionState(resource, action)
  if (state?.loading || state?.disabled) return true
  return !!getActiveLibraryFileCommand(resource, commandTypes)
}

function getResourceTarget() {
  return {
    media_id: props.mediaId,
    ...(props.seasonNumber ? { season_number: props.seasonNumber } : {}),
  }
}

async function submitResourceCommand(type, resource) {
  if (!resource?.id || !props.mediaId) return null
  const targetId = getResourceTargetId(resource)
  const command = await operations.submitCommand(
    {
      type,
      payload: {
        file_id: resource.id,
        target: getResourceTarget(),
        package_root: resource.is_package ? resource.package_root || '' : '',
      },
    },
    { dedupeKey: `library_file:${targetId}:${type}` },
  )
  if (command) {
    emit('command-submitted', command)
  }
  return command
}

async function openResourceInMediaServer(resource) {
  const targetId = getResourceTargetId(resource)
  if (!targetId || !resource?.id || !props.mediaId || isResolvingMediaServerLink(resource)) return
  const detailWindow = window.open('', '_blank')
  if (detailWindow) {
    detailWindow.opener = null
  }
  resolvingMediaServerLinkTargets.value = new Set([...resolvingMediaServerLinkTargets.value, targetId])
  try {
    const result = await resolveLibraryMediaServerLink({
      file_id: resource.id,
      target: getResourceTarget(),
      package_root: resource.is_package ? resource.package_root || '' : '',
    })
    if (result?.detail_url) {
      if (detailWindow) {
        detailWindow.location.href = result.detail_url
      } else {
        window.location.href = result.detail_url
      }
      return
    }
    detailWindow?.close()
    notification.warn(t('localResources.mediaServerLinkResolveFailed'))
  } catch {
    detailWindow?.close()
    // API interceptor already shows the localized backend message.
  } finally {
    const next = new Set(resolvingMediaServerLinkTargets.value)
    next.delete(targetId)
    resolvingMediaServerLinkTargets.value = next
  }
}

function getResourceMenuItems(resource) {
  const items = []
  const disabled = hasActiveResourceOperationCommand(resource)
  if (isResourceActionAvailable(resource, 'change_directory')) {
    items.push({
      label: t('localResources.changeDirectory.action'),
      disabled,
      command: () => openDirectoryChangeDialog(resource),
    })
  }
  if (isResourceActionAvailable(resource, 'media_server_sync')) {
    items.push({
      label: t('taskLive.actions.mediaServerSync'),
      disabled,
      command: () => submitResourceCommand('library_file.media_server_sync', resource),
    })
  }
  if (isResourceActionAvailable(resource, 'danmu_generate')) {
    items.push({
      label: t('taskLive.actions.danmuGenerate'),
      disabled,
      command: () => submitResourceCommand('library_file.danmu_generate', resource),
    })
  }
  return items
}

function hasResourceMenu(resource) {
  return !!getResourceTargetId(resource) && getResourceMenuItems(resource).length > 0
}

async function showResourceMenu(event, resource) {
  const items = getResourceMenuItems(resource)
  if (!items.length) {
    resourceMenuRef.value?.hide?.()
    return
  }
  activeResourceMenuItems.value = items
  await nextTick()
  resourceMenuRef.value?.toggle?.({
    ...event,
    currentTarget: event.currentTarget,
    target: event.currentTarget,
  })
}

async function openDirectoryChangeDialog(resource) {
  directoryChangeResource.value = resource
  directoryChangePreview.value = null
  directoryChangeVisible.value = true
  directoryChangeLoading.value = true
  try {
    const payload = await getDirectoriesTabConfig()
    directoryChangeConfig.value = {
      directories: (payload.directories || []).filter(item => item.enabled !== false),
    }
    directoryChangeForm.value = {
      target_directory_id: directoryChangeTargetDirectories.value[0]?.id || '',
    }
  } catch (error) {
    notification.error(error?.message || t('localResources.changeDirectory.loadFailed'))
  } finally {
    directoryChangeLoading.value = false
  }
}

function buildDirectoryChangePayload(includeTarget = false) {
  const resource = directoryChangeResource.value
  const targetDirectoryId = directoryChangeForm.value.target_directory_id || ''
  if (!resource?.id || !targetDirectoryId) return null
  return {
    file_id: resource.id,
    target_directory_id: targetDirectoryId,
    package_root: resource.is_package ? resource.package_root || '' : '',
    ...(includeTarget ? { target: getResourceTarget() } : {}),
  }
}

async function previewDirectoryChange() {
  const payload = buildDirectoryChangePayload()
  if (!payload) return
  directoryChangeLoading.value = true
  try {
    directoryChangePreview.value = await previewLibraryFileDirectoryChange(payload)
  } catch (error) {
    notification.error(error?.message || t('localResources.changeDirectory.previewFailed'))
  } finally {
    directoryChangeLoading.value = false
  }
}

async function submitDirectoryChange() {
  const payload = buildDirectoryChangePayload(true)
  if (!payload) return
  directoryChangeSubmitting.value = true
  try {
    const result = await submitLibraryFileDirectoryChange(payload)
    const command = result?.command || result
    operations.registerSubmittedCommand(command)
    emit('command-submitted', command)
    notification.success(t('localResources.changeDirectory.success'))
    directoryChangeVisible.value = false
  } catch {
    // Shared HTTP interceptor surfaces backend errors.
  } finally {
    directoryChangeSubmitting.value = false
  }
}

function resolveDirectoryChangePreviewMessage() {
  const preview = directoryChangePreview.value
  if (!preview) return ''
  if (preview.blockers?.length) return t('localResources.changeDirectory.previewBlocked')
  return t('localResources.changeDirectory.previewPassed', { count: preview.file_count || 0 })
}

// Helper: Clear Filters
const hasActiveDeleteCommand = (resource) => {
  return isResourceActionBusy(resource, 'delete', LIBRARY_FILE_COMMAND_TYPES)
}

const hasActiveResourceOperationCommand = (resource) => {
  return isResourceActionBusy(
    resource,
    'media_server_sync',
    LIBRARY_FILE_COMMAND_TYPES
  ) || isResourceActionBusy(
    resource,
    'danmu_generate',
    LIBRARY_FILE_COMMAND_TYPES
  )
}
</script>

<style>
.resource-action-menu.p-menu {
  --p-menu-list-padding: var(--p-select-list-padding, var(--p-list-padding, 0.25rem 0.25rem));
  --p-menu-list-gap: var(--p-select-list-gap, var(--p-list-gap, 2px));
  --p-menu-item-padding: var(--p-select-option-padding, var(--p-list-option-padding, 0.2rem 0.375rem));
  --p-menu-item-border-radius: var(--p-select-option-border-radius, var(--p-list-option-border-radius, var(--radius-item)));
  width: fit-content !important;
  min-width: 0 !important;
  inline-size: fit-content !important;
  min-inline-size: 0 !important;
}

.resource-action-menu .p-menu-list {
  padding: var(--p-menu-list-padding);
  gap: var(--p-menu-list-gap);
}

.resource-action-menu .p-menu-item-content {
  border-radius: var(--p-menu-item-border-radius);
}

.resource-action-menu .p-menu-item-link {
  padding: var(--p-menu-item-padding) !important;
  white-space: nowrap;
}

.resource-action-menu .p-menu-item-label {
  line-height: normal;
}

.local-resources-episode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, var(--size-badge-card));
  justify-content: space-evenly;
  row-gap: var(--spacing-item);
  column-gap: var(--spacing-inline);
}
</style>
