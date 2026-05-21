<template>
  <div
    class="task-live-item flex flex-col gap-inline relative py-container border-b border-separator last:border-0 group"
  >
    <div class="flex flex-col sm:flex-row min-w-0 gap-item">
      <div class="flex flex-col flex-1 min-w-0 gap-inline">
        <div v-if="task._taskCreatePlaceholder" class="flex flex-col gap-inline">
          <Skeleton width="62%" height="var(--text-body)" />
          <Skeleton width="42%" height="var(--text-caption)" />
        </div>
        <div v-else>
          <a
            v-if="getTaskDetailUrl(task)" :href="getTaskDetailUrl(task)" target="_blank"
            rel="noopener noreferrer" :title="task.title" class="task-live-title text-body hover:text-primary-emphasis"
          >
            {{ task.title }}
          </a>
          <span v-else :title="task.title" class="task-live-title text-body">
            {{ task.title }}
          </span>
        </div>
        <div v-if="task._taskCreatePlaceholder" class="flex items-center gap-inline overflow-hidden">
          <Skeleton width="4.5rem" height="1.5rem" />
          <Skeleton width="3.5rem" height="1.5rem" />
          <Skeleton width="5rem" height="1.5rem" />
        </div>
        <div v-else-if="task.description" class="task-live-description text-caption text-muted">
          {{ task.description }}
        </div>
        <div v-if="!task._taskCreatePlaceholder" class="flex items-center gap-x-inline gap-y-inline flex-wrap min-w-0">
          <a
            v-if="task.download_client && task.download_client_url"
            :href="task.download_client_url" target="_blank" rel="noopener noreferrer"
          >
            <AppTag :label="task.download_client" interactive />
          </a>
          <AppTag v-else-if="task.download_client" :label="task.download_client" />
          <AppTag
            v-if="task.added_on"
            :label="formatTaskAddedAtLabel(task.added_on)"
            icon="pi pi-clock"
            :tooltip="formatTaskAddedAtTooltip(task.added_on)"
          />
          <AppTag v-if="task.partial_selection" :label="$t('taskLive.partialDownload')" tone="warn" />
          <AppTag
            v-for="(tag, idx) in sortedTags"
            :key="idx" :value="tag.value" :icon="tag.icon" :tone="tag.tone" :tooltip="tag.tooltip || ''"
          />
        </div>
      </div>

      <div class="task-live-side flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-inline shrink-0 w-full sm:w-auto">
        <div v-if="!task._taskCreatePlaceholder" class="task-actions-row order-2 sm:order-1 flex flex-wrap justify-end gap-item shrink-0">
          <template v-for="action in actions" :key="action.id">
            <Button
              v-if="!action.menuOnly && isActionVisible(action, task)" v-tooltip.top="action.tooltip" :icon="action.icon"
              text
              :severity="action.severity || 'secondary'"
              :loading="isActionLoading(action, task)" :disabled="isActionDisabled(action, task)"
              @click.stop="handleActionClick(action, $event)"
            >
            </Button>
          </template>
          <Button
            v-if="hasTaskMenuActions"
            v-tooltip.top="$t('localResources.moreActions')"
            icon="pi pi-ellipsis-v"
            text
            severity="secondary"
            :loading="isTaskMenuLoading"
            :disabled="isTaskMenuDisabled"
            @click.stop="showTaskMenu"
          />
        </div>
        <div v-else class="task-actions-row order-2 sm:order-1 flex gap-item task-action-ghosts shrink-0" aria-hidden="true">
          <Button
            v-for="action in ghostActions"
            :key="action.id"
            :icon="action.icon"
            text
            severity="secondary"
            class="task-action-ghost"
            disabled
            tabindex="-1"
          />
        </div>
        <div class="task-status-footer order-1 sm:order-2 flex items-center justify-start sm:justify-end gap-inline mt-0 sm:mt-auto min-w-0 flex-1 sm:flex-none w-auto sm:w-full">
          <Button
            v-if="shouldShowStatusInfo(task)"
            v-tooltip.top="getTaskStatusTooltip(task)"
            text
            size="small"
            icon="pi pi-info-circle"
            :severity="getStatusButtonSeverity(task)"
            class="task-status-info-button ui-inline-icon-button"
          />
          <div v-if="task._taskCreatePlaceholder" class="flex items-center justify-end gap-inline">
            <Skeleton width="7rem" height="var(--text-caption)" />
          </div>
          <div
            v-else v-tooltip.top="task.realtime_unavailable ? $t('taskLive.realtimeStatusUnavailable') : null"
            class="task-status-row flex items-center justify-start sm:justify-end gap-inline flex-wrap text-caption text-left sm:text-right"
          >
            <template v-if="isDownloadingTask(task)">
              <span :class="getTaskStatusTextClass(task)">{{ getTaskStatusLabel(task) }}</span>
              <span class="task-status-meta text-muted">{{ formatTaskProgress(task) }}</span>
              <span class="task-status-meta text-muted">↓ {{ formatSpeed(task.dlspeed || 0) }}</span>
              <span v-if="task.eta && task.eta > 0" class="task-status-meta text-muted">ETA {{ formatETA(task.eta) }}</span>
            </template>
            <span v-else :class="getTaskStatusTextClass(task)">{{ getTaskStatusLabel(task) }}</span>
          </div>
        </div>
      </div>
    </div>
    <Menu
      ref="taskMenuRef"
      :model="activeTaskMenuItems"
      class="resource-action-menu"
      popup
      append-to="body"
    />
    <div v-if="shouldShowProgressLine(task)" class="task-progress-edge" aria-hidden="true">
      <progress class="task-progress-edge__bar" :value="getTaskProgressValue(task)" max="100"></progress>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import Skeleton from 'primevue/skeleton'
import AppTag from '@/components/common/AppTag.vue'
import { formatETA, formatSizeBytes, formatSpeed } from '@/utils/formatters'

const props = defineProps({
  task: { type: Object, required: true },
  actions: { type: Array, default: () => [] },
  visibleTags: { type: Array, default: () => [] },
  getSortedTags: { type: Function, required: true },
  resolveSiteName: { type: Function, required: true },
  getTaskDetailUrl: { type: Function, required: true },
  formatTaskAddedAtLabel: { type: Function, required: true },
  formatTaskAddedAtTooltip: { type: Function, required: true },
  isDownloadingTask: { type: Function, required: true },
  getTaskProgressValue: { type: Function, required: true },
  formatTaskProgress: { type: Function, required: true },
  shouldShowProgressLine: { type: Function, required: true },
  getTaskStatusTextClass: { type: Function, required: true },
  getTaskStatusLabel: { type: Function, required: true },
  shouldShowStatusInfo: { type: Function, required: true },
  getTaskStatusTooltip: { type: Function, required: true },
  getStatusButtonSeverity: { type: Function, required: true },
  isActionVisible: { type: Function, required: true },
  isActionLoading: { type: Function, required: true },
  isActionDisabled: { type: Function, required: true },
})

const taskMenuRef = ref(null)
const activeTaskMenuItems = ref([])

const sortedTags = computed(() => props.getSortedTags({
  resource: {
    directory: props.task.directory_name,
    size: props.task._taskCreatePlaceholder ? '' : formatSizeBytes(props.task.size),
    site: props.resolveSiteName(props.task.site || props.task.indexer || props.task.tracker || ''),
  },
  attributes: props.task.attributes,
  displayAttributes: {
    ...props.task.attributes,
    seasons: props.task.selected_season ? [props.task.selected_season] : props.task.attributes?.seasons,
    episodes: Array.isArray(props.task.selected_episodes) && props.task.selected_episodes.length > 0
      ? props.task.selected_episodes
      : props.task.attributes?.episodes,
  },
}, { visibleTags: props.visibleTags }))

const taskMenuActions = computed(() => props.actions.filter(action => (
  action.menuOnly && props.isActionVisible(action, props.task)
)))

const hasTaskMenuActions = computed(() => taskMenuActions.value.length > 0)

const isTaskMenuLoading = computed(() => taskMenuActions.value.some(action => (
  props.isActionLoading(action, props.task)
)))

const isTaskMenuDisabled = computed(() => (
  !hasTaskMenuActions.value
  || isTaskMenuLoading.value
  || taskMenuActions.value.every(action => props.isActionDisabled(action, props.task))
))

const ghostActions = computed(() => {
  const primary = props.actions.filter(action => !action.menuOnly)
  return hasTaskMenuActions.value
    ? [...primary, { id: 'more', icon: 'pi pi-ellipsis-v' }]
    : primary
})

function handleActionClick(action, event) {
  if (props.isActionDisabled(action, props.task) || props.isActionLoading(action, props.task)) return
  action.handler(event, props.task)
}

function buildTaskMenuItems() {
  return taskMenuActions.value.map(action => ({
    label: action.label || action.tooltip || action.id,
    icon: action.icon,
    disabled: props.isActionDisabled(action, props.task) || props.isActionLoading(action, props.task),
    command: (event) => handleActionClick(action, event),
  }))
}

async function showTaskMenu(event) {
  const items = buildTaskMenuItems()
  if (!items.length) {
    taskMenuRef.value?.hide?.()
    return
  }
  activeTaskMenuItems.value = items
  await nextTick()
  taskMenuRef.value?.toggle?.({
    ...event,
    currentTarget: event.currentTarget,
    target: event.currentTarget,
  })
}
</script>

<style scoped>
.task-action-ghosts {
  opacity: 0;
  pointer-events: none;
}

.task-live-item {
  overflow: hidden;
}

.task-live-title,
.task-live-description {
  overflow-wrap: anywhere;
  white-space: normal;
}

.task-progress-edge {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  pointer-events: none;
}

.task-progress-edge__bar {
  display: block;
  width: 100%;
  height: 100%;
  appearance: none;
  border: 0;
  background: var(--surface-subtle);
}

.task-progress-edge__bar::-webkit-progress-bar {
  background: var(--surface-subtle);
}

.task-progress-edge__bar::-webkit-progress-value {
  background: var(--accent-primary);
}

.task-progress-edge__bar::-moz-progress-bar {
  background: var(--accent-primary);
}

.task-status-text {
  font-size: var(--text-caption);
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}

.task-status-footer {
  align-items: center;
}

.task-status-info-button.p-button {
  width: 1.5em;
  min-width: 1.5em;
  height: 1.5em;
  padding: 0;
}

.task-status-row {
  align-items: baseline;
  line-height: 1.5;
}

.task-status-meta {
  display: inline-flex;
  align-items: center;
  line-height: 1.5;
  white-space: nowrap;
}

.task-status-text--neutral {
  color: var(--text-muted);
}

.task-status-text--downloading {
  color: var(--state-warn);
}

.task-status-text--paused {
  color: color-mix(in srgb, var(--text-default) 62%, var(--text-muted) 38%);
}

.task-status-text--ready {
  color: var(--accent-primary);
}

.task-status-text--accent {
  color: color-mix(in srgb, var(--accent-primary) 82%, var(--text-default) 18%);
}

.task-status-text--success {
  color: var(--state-success);
}

.task-status-text--warning {
  color: var(--state-warn);
}

.task-status-text--error {
  color: var(--state-error);
}
</style>
