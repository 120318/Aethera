<template>
  <div class="flex flex-col gap-container">
    <div :class="['grid grid-cols-1 gap-item', episodeOptions.length > 0 ? 'md:grid-cols-3' : 'md:grid-cols-2']">
      <InputText v-model="localFilters.keyword" :placeholder="$t('resourceSearch.keywordFilter')" class="w-full" />

      <MultiSelect
        v-model="localFilters.statuses" :options="statusOptions" option-label="label" option-value="value" filter
        :placeholder="$t('taskLive.state')" display="chip" class="w-full" :max-selected-labels="1"
      />

      <MultiSelect
        v-if="episodeOptions.length > 0"
        v-model="localFilters.episodes" :options="episodeOptions" option-label="label" option-value="value" filter
        :placeholder="$t('resourceSearch.episodes')" display="chip" class="w-full" :max-selected-labels="1"
      />
    </div>

    <!-- DataView layout. -->
    <DataView
      :value="filteredAndSortedTasks" paginator :rows="ROWS_PER_PAGE" :first="currentFirst"
      layout="list" :paginator-position="paginatorPosition" class="overflow-hidden ui-dataview-balanced-paginator"
      @update:first="currentFirst = $event"
    >

      <!-- Paginator start: stats. -->
      <template #paginatorstart>
        <div class="hidden md:flex items-center text-muted">
          {{ $t('taskLive.totalPrefix') }} <span class="text-primary mx-inline">{{ enhancedTasks.length }}</span> {{ $t('taskLive.totalSuffix') }}
          <span v-if="filteredAndSortedTasks.length !== enhancedTasks.length" class="text-muted">
            {{ $t('resourceSearch.filteredCount', { count: filteredAndSortedTasks.length }) }}
          </span>
        </div>
      </template>

      <!-- Paginator end: sort and clear. -->
      <template #paginatorend>
        <div class="flex items-center gap-item ml-0 md:ml-block">
          <Button
            v-if="hasActiveFilters" severity="secondary" :label="$t('resourceSearch.clearFilters')" icon="pi pi-filter-slash" link size="small"
            @click="clearFilters"
          />
          <SortControl v-model="sortModel" :options="sortOptions" />
        </div>
      </template>

      <!-- List item. -->
      <template #list="slotProps">
        <TaskLiveListItem
          v-for="(task, index) in slotProps.items"
          :key="task.id || task.info_hash || task.hash || index"
          :task="task"
          :actions="TASK_ACTIONS_CONFIG"
          :visible-tags="taskCardVisibleTags"
          :get-sorted-tags="getSortedTags"
          :resolve-site-name="resolveSiteName"
          :get-task-detail-url="getTaskDetailUrl"
          :format-task-added-at-label="formatTaskAddedAtLabel"
          :format-task-added-at-tooltip="formatTaskAddedAtTooltip"
          :is-downloading-task="isDownloadingTask"
          :get-task-progress-value="getTaskProgressValue"
          :format-task-progress="formatTaskProgress"
          :should-show-progress-line="shouldShowProgressLine"
          :get-task-status-text-class="getTaskStatusTextClass"
          :get-task-status-label="getTaskStatusLabel"
          :should-show-status-info="shouldShowStatusInfo"
          :get-task-status-tooltip="getTaskStatusTooltip"
          :get-status-button-severity="getStatusButtonSeverity"
          :is-action-visible="isActionVisible"
          :is-action-loading="isActionLoading"
          :is-action-disabled="isActionDisabled"
        />
      </template>

      <template #empty>
        <div class="ui-tab-empty">
          <i class="pi pi-inbox text-display mb-item opacity-50"></i>
          <p>{{ $t('taskLive.noTasks') }}</p>
        </div>
      </template>
    </DataView>

    <!-- Task detail dialog. -->
    <ConfigDialog
      :model-value="detailVisible"
      size="md"
      :closable="false"
      :scroll="!detailShowRaw"
      :content-scroll="detailShowRaw"
      @update:model-value="detailVisible = $event"
    >
      <template #header>
        <div class="flex items-center justify-between w-full">
          <span class="p-dialog-title">{{ $t('taskLive.detailTitle') }}</span>
          <div class="flex items-center gap-item">
            <Button
              :icon="detailShowRaw ? 'pi pi-list' : 'pi pi-code'"
              :title="detailShowRaw ? $t('taskLive.viewStructured') : $t('taskLive.viewRawFields')"
              severity="secondary"
              text
              @click="toggleDetailRaw"
            />
            <Button
              icon="pi pi-times"
              severity="secondary"
              text
              @click="detailVisible = false"
            />
          </div>
        </div>
      </template>

      <div v-if="currentTask && detailShowRaw" class="task-detail-raw">
        <pre class="task-detail-raw__content text-caption text-muted m-none whitespace-pre-wrap break-all">{{ prettyCurrentTask }}</pre>
      </div>
      <div v-else-if="detailLoading" class="ui-dialog-section">
        <div class="flex flex-col gap-item">
          <Skeleton width="100%" height="1.25rem" />
          <Skeleton width="80%" height="1.25rem" />
          <Skeleton width="100%" height="1.25rem" />
        </div>
      </div>
      <div v-else-if="currentTask" class="flex flex-col gap-item">
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.taskName') }}</label>
          <div class="text-body break-all">{{ currentTask.title || '-' }}</div>
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.taskDescription') }}</label>
          <div class="text-body break-all">{{ currentTask.description || '-' }}</div>
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.torrentLink') }}</label>
          <div class="text-body break-all">
            <a
              v-if="currentTaskDetailUrl"
              :href="currentTaskDetailUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="hover:text-primary-emphasis"
            >
              {{ currentTaskDetailUrl }}
            </a>
            <span v-else>-</span>
          </div>
        </div>
        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.hash') }}</label>
              <div class="text-body font-mono break-all">{{ currentTaskHash }}</div>
            </div>
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.state') }}</label>
              <div class="text-body">{{ getTaskStatusBaseLabel(currentTask) || '-' }}</div>
            </div>
          </div>
        </div>
        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.directory') }}</label>
              <div class="text-body">{{ currentTask.directory_name || '-' }}</div>
            </div>
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('downloadDialog.downloader') }}</label>
              <div class="text-body">{{ currentTask.download_client || currentTask.task_data?.download_client || '-' }}</div>
            </div>
          </div>
        </div>
        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.savePath') }}</label>
              <div class="text-body break-all">{{ currentTask.save_path || '-' }}</div>
            </div>
          </div>
        </div>
        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.addedAt') }}</label>
              <div class="text-body">{{ formatAbsoluteDateTime(currentTask.added_on) }}</div>
            </div>
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.tracker') }}</label>
              <div class="text-body break-all">{{ currentTaskTracker }}</div>
            </div>
          </div>
        </div>
        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('resourceSearch.size') }}</label>
              <div class="text-body">{{ formatSizeBytes(currentTask.size) || '-' }}</div>
            </div>
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.category') }}</label>
              <div class="text-body">{{ currentTask.category || '-' }}</div>
            </div>
          </div>
        </div>
        <div v-if="isCurrentTaskTv && (currentTaskSeasonDisplay || currentTaskEpisodeDisplay)" class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('resourceSearch.seasons') }}</label>
              <div class="text-body">{{ currentTaskSeasonDisplay || '-' }}</div>
            </div>
            <div class="flex flex-col gap-inline">
              <label class="ui-dialog-item-title text-caption text-muted">{{ $t('resourceSearch.episodes') }}</label>
              <div class="text-body">{{ currentTaskEpisodeDisplay || '-' }}</div>
            </div>
          </div>
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.specs') }}</label>
          <div class="text-body">
            <ResourceAttributes
              v-if="hasCurrentTaskSpecs"
              :attributes="currentTask.attributes || {}"
              :size="currentTask.size || 0"
              :site="resolveSiteName(currentTask.site || currentTask.indexer || currentTask.tracker || '')"
              :visible-tags="taskSpecVisibleTags"
            />
            <span v-else>-</span>
          </div>
        </div>
        <div v-if="currentTaskFileStructure.length > 0" class="ui-dialog-section">
          <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.fileStructure') }}</label>
          <FileStructureTree :files="currentTaskFileStructure" :root-name="currentTaskFileStructureRootName" />
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title text-caption text-muted">{{ $t('taskLive.errorInfo') }}</label>
          <div class="text-body break-all text-muted">{{ combinedTaskError }}</div>
        </div>
      </div>
      <div v-else class="ui-dialog-section">
        <p class="text-body text-muted m-none">{{ $t('taskLive.noDetailData') }}</p>
      </div>
    </ConfigDialog>

    <Dialog v-model:visible="deleteConfirmVisible" :header="$t('taskLive.deleteConfirmTitle')" modal :dismissable-mask="true" class="w-full max-w-dialog-sm">
      <div class="ui-dialog-body">
        <div class="ui-dialog-section">
          <p class="text-body m-none">
            {{ $t('taskLive.deleteConfirmPrefix') }} <strong>{{ deleteTargetLabel }}</strong> {{ $t('taskLive.deleteConfirmSuffix') }}
          </p>
        </div>

        <div class="ui-dialog-section">
          <div
            class="flex items-center gap-item cursor-pointer"
            @click="deleteFiles = !deleteFiles"
          >
            <Checkbox v-model="deleteFiles" binary input-id="delete-files-check" @click.stop />
            <label for="delete-files-check" class="cursor-pointer select-none text-caption font-medium">
              {{ $t('taskLive.deleteFiles') }}
            </label>
          </div>
          <p class="text-caption text-muted m-none mt-inline">
            {{ $t('taskLive.deleteFilesHint') }}
          </p>
        </div>

        <div
          v-if="deleteMeta.hasLibraryFiles"
          class="ui-dialog-section"
        >
          <div
            class="flex items-center gap-item cursor-pointer"
            @click="deleteLibraryFiles = !deleteLibraryFiles"
          >
            <Checkbox v-model="deleteLibraryFiles" binary input-id="delete-library-check" @click.stop />
            <label for="delete-library-check" class="cursor-pointer select-none text-caption font-medium">
              {{ $t('taskLive.deleteLibraryFiles', { count: deleteMeta.libraryFilesCount }) }}
            </label>
          </div>
        </div>

        <div class="ui-dialog-section">
          <div
            class="flex items-center gap-item cursor-pointer"
            @click="forceDelete = !forceDelete"
          >
            <Checkbox v-model="forceDelete" binary input-id="force-delete-check" @click.stop />
            <label
              for="force-delete-check"
              class="cursor-pointer select-none text-caption font-medium"
            >{{ $t('taskLive.forceDelete') }}</label>
          </div>
        </div>
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" outlined @click="deleteConfirmVisible = false" />
        <Button
          :label="$t('taskLive.confirmDelete')" severity="primary" :loading="deleteExecuting"
          @click="executeDelete"
        />
      </template>
    </Dialog>

    <Dialog v-model:visible="downloaderChangeVisible" :header="$t('taskLive.changeDownloader.title')" modal :dismissable-mask="true" class="w-full max-w-dialog-md">
      <div class="ui-dialog-body">
        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-item">
            <div class="flex flex-col gap-inline min-w-0">
              <label for="change-directory-target" class="ui-dialog-item-title block">{{ $t('taskLive.changeDownloader.targetDirectory') }}</label>
              <Select
                v-model="downloaderChangeForm.target_directory_id"
                input-id="change-directory-target"
                :options="downloaderChangeConfig.directories"
                option-label="name"
                option-value="id"
                class="w-full"
                :disabled="downloaderChangeLoading || downloaderChangeExecuting"
                @change="downloaderChangePreview = null"
              />
            </div>
            <div class="flex flex-col gap-inline min-w-0">
              <label for="change-downloader-target" class="ui-dialog-item-title block">{{ $t('taskLive.changeDownloader.targetDownloader') }}</label>
              <Select
                v-model="downloaderChangeForm.target_downloader_id"
                input-id="change-downloader-target"
                :options="downloaderChangeDownloaderOptions"
                option-label="name"
                option-value="id"
                option-disabled="disabled"
                class="w-full"
                :disabled="downloaderChangeLoading || downloaderChangeExecuting"
                @change="downloaderChangePreview = null"
              />
            </div>
          </div>
        </div>

      </div>
      <template #footer>
        <section class="w-full flex flex-col items-center gap-inline">
          <p
            v-if="downloaderChangePreview"
            class="text-caption text-center m-none"
            :class="downloaderChangePreview.blockers?.length ? 'text-danger' : (downloaderChangePreview.warnings?.length ? 'text-warning' : 'text-muted')"
          >
            {{ resolveDownloaderChangePreviewMessage() }}
          </p>
          <div class="flex items-center justify-center gap-item flex-wrap w-full">
            <Button :label="$t('common.cancel')" severity="secondary" outlined @click="downloaderChangeVisible = false" />
            <Button :label="$t('taskLive.changeDownloader.preview')" severity="secondary" :loading="downloaderChangeLoading" @click="previewDownloaderChange" />
            <Button
              :label="$t('taskLive.changeDownloader.execute')"
              severity="primary"
              :loading="downloaderChangeExecuting"
              :disabled="!downloaderChangePreview?.ok"
              @click="executeDownloaderChange"
            />
          </div>
        </section>
      </template>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import DataView from 'primevue/dataview'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import Skeleton from 'primevue/skeleton'
import SortControl from '@/components/common/filter/SortControl.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import FileStructureTree from '@/components/common/FileStructureTree.vue'
import ResourceAttributes from '@/components/common/ResourceAttributes.vue'
import TaskLiveListItem from '@/components/task-live/TaskLiveListItem.vue'
import { ResourceTagType } from '@/constants/resourceTagTypes'
import { formatAbsoluteDateTime, formatRelativeTime, formatSizeBytes } from '@/utils/formatters'
import { useSiteDisplay } from '@/composables/useSiteDisplay'
import { useTaskLivePage } from '@/composables/useTaskLivePage'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  activeTab: { type: String, default: 'resources' },
  mediaId: { type: String, default: '' },
  mediaType: { type: String, default: '' },
  operationCommands: { type: Array, default: null },
  operationRealtimeOverrides: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['task-updated', 'command-submitted', 'task-view-updated'])
const { t } = useI18n()
const { ensureSiteDisplayLoaded, resolveSiteName } = useSiteDisplay()
const taskCardVisibleTags = [
  ResourceTagType.DIRECTORY,
  ResourceTagType.DISC,
  ResourceTagType.EPISODE,
  ResourceTagType.RESOLUTION,
  ResourceTagType.HDR_TYPE,
  ResourceTagType.COLOR_DEPTH,
  ResourceTagType.RESOURCE_FORM,
  ResourceTagType.PACKAGE_LAYOUT,
  ResourceTagType.VERSION,
  ResourceTagType.LANGUAGE,
  ResourceTagType.SUBTITLE,
  ResourceTagType.SIZE,
  ResourceTagType.SITE,
]
const taskSpecVisibleTags = [
  ResourceTagType.DIRECTORY,
  ResourceTagType.DISC,
  ResourceTagType.EPISODE,
  ResourceTagType.RESOLUTION,
  ResourceTagType.HDR_TYPE,
  ResourceTagType.COLOR_DEPTH,
  ResourceTagType.RESOURCE_FORM,
  ResourceTagType.PACKAGE_LAYOUT,
  ResourceTagType.VERSION,
  ResourceTagType.LANGUAGE,
  ResourceTagType.SUBTITLE,
  ResourceTagType.SIZE,
  ResourceTagType.SITE,
]

const {
  getSortedTags,
  currentFirst,
  localFilters,
  sortModel,
  statusOptions,
  sortOptions,
  episodeOptions,
  hasActiveFilters,
  paginatorPosition,
  filteredAndSortedTasks,
  clearFilters,
  ROWS_PER_PAGE,
  enhancedTasks,
  detailVisible,
  currentTask,
  detailShowRaw,
  detailLoading,
  deleteConfirmVisible,
  deleteExecuting,
  forceDelete,
  deleteFiles,
  deleteLibraryFiles,
  deleteMeta,
  deleteTargetLabel,
  prettyCurrentTask,
  currentTaskDetailUrl,
  currentTaskHash,
  currentTaskTracker,
  isCurrentTaskTv,
  currentTaskSeasonDisplay,
  currentTaskEpisodeDisplay,
  hasCurrentTaskSpecs,
  combinedTaskError,
  getTaskDetailUrl,
  toggleDetailRaw,
  executeDelete,
  downloaderChangeVisible,
  downloaderChangeLoading,
  downloaderChangeExecuting,
  downloaderChangePreview,
  downloaderChangeConfig,
  downloaderChangeDownloaderOptions,
  downloaderChangeForm,
  previewDownloaderChange,
  executeDownloaderChange,
  resolveDownloaderChangePreviewMessage,
  TASK_ACTIONS_CONFIG,
  getStatusButtonSeverity,
  getTaskStatusTooltip,
  getTaskStatusLabel,
  shouldShowStatusInfo,
  isActionVisible,
  isActionLoading,
  isActionDisabled,
} = useTaskLivePage(props, emit)

const currentTaskFileStructure = computed(() => {
  const files = currentTask.value?.file_structure || currentTask.value?.task_data?.metadata?.files || currentTask.value?.metadata?.files || []
  return Array.isArray(files) ? files : []
})
const currentTaskFileStructureRootName = computed(() => {
  const name = currentTask.value?.task_data?.metadata?.name || currentTask.value?.metadata?.name || currentTask.value?.title || ''
  return String(name || '').replace(/\\/g, '/').split('/').filter(Boolean).pop() || ''
})

onMounted(async () => {
  await ensureSiteDisplayLoaded()
})

function isDownloadingTask(task) {
  return task?.phase_group === 'downloading'
}

function getTaskStatusBaseLabel(task) {
  if (task?._taskCreatePlaceholder) {
    return t('taskLive.waitingDownload')
  }
  if (task?.phase_label_key) return t(task.phase_label_key, task.phase_label_params || {})
  return task?.phase_label || t('taskLive.unknownStatus')
}

function getTaskProgressValue(task) {
  const progress = Number(task?.progress || 0) * 100
  if (!Number.isFinite(progress)) return 0
  return Math.min(100, Math.max(0, progress))
}

function formatTaskProgress(task) {
  return `${getTaskProgressValue(task).toFixed(1)}%`
}

function formatTaskAddedAtLabel(value) {
  return formatRelativeTime(value)
}

function formatTaskAddedAtTooltip(value) {
  return formatAbsoluteDateTime(value)
}

function shouldShowProgressLine(task) {
  const progress = getTaskProgressValue(task)
  return isDownloadingTask(task) && progress > 0 && progress < 100
}

function getTaskStatusTone(task) {
  if (task?.realtime_unavailable) return 'error'

  const phaseGroup = String(task?.phase_group || '').toLowerCase()
  const phase = String(task?.phase || '').toLowerCase()

  if (phaseGroup === 'failed') return 'error'
  if (phaseGroup === 'attention') return 'warning'
  if (phaseGroup === 'completed') return 'success'
  if (phaseGroup === 'importing') {
    if (phase === 'transferring') return 'accent'
    return 'ready'
  }
  if (phaseGroup === 'downloading') {
    if (phase === 'paused') return 'paused'
    return 'downloading'
  }

  if (phase === 'finished') return 'ready'
  if (phase === 'completed') return 'success'
  if (phase === 'paused') return 'paused'
  if (phase === 'error' || phase === 'failed') return 'error'

  return 'neutral'
}

function getTaskStatusTextClass(task) {
  return [
    'task-status-text',
    `task-status-text--${getTaskStatusTone(task)}`
  ]
}
</script>

<style scoped>
.task-detail-raw {
  min-height: 0;
}

.task-detail-raw__content {
  overflow: visible;
}

</style>
