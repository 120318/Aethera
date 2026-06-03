<template>
  <ConfigDialog
    :model-value="visible"
    :title="$t('notificationCenter.title')"
    size="lg"
    @update:model-value="handleVisibleChange"
  >
    <section class="flex flex-col gap-container min-h-tab-content">
      <div v-if="lastError" class="flex items-center gap-item px-item py-item border border-separator rounded-container text-status-error bg-surface">
        <i class="pi pi-exclamation-triangle text-caption" />
        <span class="text-caption">{{ lastError }}</span>
      </div>

      <div class="flex flex-wrap items-center gap-item text-caption text-muted">
        <AppTag :label="$t('notificationCenter.runningCount', { count: summary.active_action_count || 0 })" tone="accent" />
        <AppTag :label="$t('notificationCenter.warningCount', { count: summary.warning_event_count || 0 })" tone="warn" />
        <AppTag :label="$t('notificationCenter.errorCount', { count: summary.error_event_count || 0 })" tone="danger" />
        <Button
          v-if="unreadEventCount > 0"
          :label="$t('notificationCenter.markAllRead')"
          icon="pi pi-check"
          severity="secondary"
          outlined
          size="small"
          class="ml-auto"
          :loading="markingAllRead"
          @click="handleMarkAllRead"
        />
      </div>

      <section class="flex flex-col gap-item">
        <div v-if="loading && !centerItems.length" class="ui-tab-empty">
          <EmptyState :border="false" :description="$t('notificationCenter.loadingStatus')" image="pi pi-spin pi-spinner" />
        </div>
        <div v-else-if="centerItems.length === 0" class="ui-tab-empty">
          <p class="text-title font-medium mb-item">{{ $t('notificationCenter.noEventsTitle') }}</p>
          <p class="text-caption text-muted">{{ $t('notificationCenter.noEventsDescription') }}</p>
        </div>
        <DataView v-else :value="centerItems" layout="list" class="overflow-hidden" :pt="listPt">
          <template #list="slotProps">
            <div>
              <article
                v-for="item in slotProps.items"
                :key="item.id"
                class="py-container border-b border-separator bg-transparent group last:border-0"
              >
                <div class="flex flex-col sm:flex-row sm:items-start gap-item">
                  <div class="min-w-0 flex flex-col gap-inline flex-1">
                    <div class="flex items-center gap-inline min-w-0 text-body text-color">
                      <AppTag
                        :label="itemStatusLabel(item)"
                        :tone="itemStatusTone(item)"
                        :icon="itemStatusIcon(item)"
                      />
                      <RouterLink
                        v-if="getItemMediaRoute(item)"
                        v-tooltip.top="itemTarget(item)"
                        :to="getItemMediaRoute(item)"
                        class="truncate font-medium text-muted no-underline transition-colors hover:text-color"
                        @click.stop
                      >
                        {{ itemTarget(item) }}
                      </RouterLink>
                      <span v-else v-tooltip.top="itemTarget(item)" class="truncate font-medium text-muted">
                        {{ itemTarget(item) }}
                      </span>
                      <span class="shrink-0 text-muted">·</span>
                      <span class="truncate">{{ itemTypeLabel(item) }}</span>
                    </div>
                    <div v-tooltip.top="itemMessage(item)" class="text-body break-words">
                      {{ itemMessage(item) }}
                    </div>
                    <div class="flex items-center justify-between gap-inline text-caption text-muted">
                      <span>{{ itemMetaText(item) }}</span>
                      <span v-tooltip.top="formatAbsoluteDateTime(itemTimestamp(item))">
                        {{ formatRelativeTs(itemTimestamp(item)) }}
                      </span>
                    </div>
                  </div>
                  <div class="flex items-center gap-inline shrink-0 self-start">
                    <Button
                      v-if="item.kind === 'event'"
                      v-tooltip.top="$t('notificationCenter.markRead')"
                      icon="pi pi-check"
                      severity="secondary"
                      text
                      rounded
                      :aria-label="$t('notificationCenter.markRead')"
                      class="w-control-icon h-control-icon p-none transition-colors"
                      :loading="markingReadEventIds.has(item.record.id)"
                      @click="handleMarkEventRead(item.record)"
                    />
                    <Button
                      v-if="canCancelAction(item.record)"
                      v-tooltip.top="$t('operationCenter.cancelTask')"
                      icon="pi pi-times"
                      severity="danger"
                      text
                      rounded
                      :aria-label="$t('operationCenter.cancelTask')"
                      class="w-control-icon h-control-icon p-none transition-colors"
                      :loading="cancellingActionIds.has(item.record.id)"
                      @click="handleCancelAction(item.record)"
                    />
                  </div>
                </div>
              </article>
            </div>
          </template>
        </DataView>
      </section>
    </section>
  </ConfigDialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import AppTag from '@/components/common/AppTag.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useNotificationCenterStore } from '@/stores/notification-center'
import { useOperationsStore } from '@/stores/operations'
import { resolveActionKindLabel, resolveActionNameLabel, resolveActionStatusMeta, resolvePilotEpisodeActionLabel } from '@/constants/actionTypes'
import { resolveEventTypeMeta } from '@/constants/eventTypes'
import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:visible'])
const notificationCenter = useNotificationCenterStore()
const operationsStore = useOperationsStore()
const { summary, centerItems, lastError, loading, markingAllRead } = storeToRefs(notificationCenter)
const { t } = useI18n()
const cancellingActionIds = reactive(new Set())
const markingReadEventIds = reactive(new Set())
const listPt = {
  content: { class: 'p-none bg-transparent border-none' },
}
const unreadEventCount = computed(() => (summary.value.warning_event_count || 0) + (summary.value.error_event_count || 0))

function handleVisibleChange(value) {
  emit('update:visible', value)
}

function parseMeta(record) {
  if (!record?.meta) return {}
  if (typeof record.meta === 'object') return record.meta
  try {
    const parsed = JSON.parse(record.meta)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function getActionTypeLabel(action) {
  if (action?.action_name === 'pilot.episode') {
    return resolvePilotEpisodeActionLabel(action?.media_id || action?.target_id)
  }
  return resolveActionNameLabel(action?.action_name)
}

function getStatusLabel(status) {
  return resolveActionStatusMeta(status)?.label || status
}

function getStatusTone(status) {
  return resolveActionStatusMeta(status)?.tone || 'neutral'
}

function actionTarget(action) {
  if (action?.kind === 'scheduler' || action?.target_type === 'scheduler_job') {
    return resolveActionKindLabel('scheduler')
  }
  const meta = parseMeta(action)
  const media = action?.media
  if (media?.title && media?.year) return `${media.title} (${media.year})`
  return meta.target_label || action?.media_id || action?.task_id || action?.target_id || '-'
}

function actionMessage(action) {
  return action?.error || resolveLocalizedRecordMessage(action, t('operationCenter.noMessage'))
}

function positiveSeasonNumber(value) {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? number : null
}

function recordSeasonNumber(record) {
  const meta = parseMeta(record)
  return positiveSeasonNumber(
    record?.media?.season_number
    ?? record?.target?.season_number
    ?? record?.target_season_number
    ?? meta?.target?.season_number
    ?? meta?.season_number
  )
}

function mediaRouteFor(record) {
  const mediaId = record?.media?.media_id || record?.media_id || (record?.target_type === 'media' ? record?.target_id : '')
  if (!mediaId) return null
  const seasonNumber = recordSeasonNumber(record)
  if (String(mediaId).includes(':tv:') && !seasonNumber) return null
  return {
    name: 'MediaDetail',
    params: { mediaId },
    query: seasonNumber ? { season: seasonNumber } : {},
  }
}

function eventTarget(event) {
  const media = event?.media
  if (media?.title && media?.year) return `${media.title} (${media.year})`
  return event?.message_params?.target || event?.message_params?.task || event?.task_id || event?.subscription_id || event?.action_id || '-'
}

function eventTypeLabel(event) {
  const eventMeta = resolveEventTypeMeta(event?.type)
  if (!eventMeta) return event?.type || ''
  const subject = eventMeta.subjectKey ? t(eventMeta.subjectKey) : ''
  const action = eventMeta.actionKey ? t(eventMeta.actionKey) : ''
  return [subject, action].filter(Boolean).join(' · ') || event.type
}

function eventMessage(event) {
  return resolveLocalizedRecordMessage(event, t('notificationCenter.noMessage'))
}

function itemRecord(item) {
  return item?.record || {}
}

function itemStatusLabel(item) {
  if (item?.kind === 'event') return t(`notificationCenter.levels.${itemRecord(item).level}`)
  return getStatusLabel(itemRecord(item).status)
}

function itemStatusTone(item) {
  if (item?.kind === 'event') return itemRecord(item).level === 'error' ? 'danger' : 'warn'
  return getStatusTone(itemRecord(item).status)
}

function itemStatusIcon(item) {
  if (item?.kind === 'event') return itemRecord(item).level === 'error' ? 'pi pi-times-circle' : 'pi pi-exclamation-triangle'
  return itemRecord(item).status === 'running' ? 'pi pi-spin pi-spinner' : ''
}

function itemTypeLabel(item) {
  const record = itemRecord(item)
  if (item?.kind === 'event') return eventTypeLabel(record)
  return getActionTypeLabel(record)
}

function itemTarget(item) {
  const record = itemRecord(item)
  return item?.kind === 'event' ? eventTarget(record) : actionTarget(record)
}

function itemMessage(item) {
  const record = itemRecord(item)
  return item?.kind === 'event' ? eventMessage(record) : actionMessage(record)
}

function itemTimestamp(item) {
  const record = itemRecord(item)
  return item?.kind === 'event' ? record.ts : actionTimestamp(record)
}

function itemMetaText(item) {
  if (item?.kind === 'event') {
    return t('notificationCenter.eventMeta')
  }
  return t('notificationCenter.runningMeta')
}

function getItemMediaRoute(item) {
  return mediaRouteFor(itemRecord(item))
}

function formatRelativeTs(value) {
  return formatRelativeTime(value)
}

function actionTimestamp(action) {
  return action?.started_at || action?.ts
}

function canCancelAction(action) {
  return action?.kind === 'command' && action?.status === 'queued'
}

async function handleCancelAction(action) {
  if (!canCancelAction(action) || cancellingActionIds.has(action.id)) return
  cancellingActionIds.add(action.id)
  try {
    await operationsStore.cancelCommand(action.id)
    await notificationCenter.refreshCenter()
  } finally {
    cancellingActionIds.delete(action.id)
  }
}

async function handleMarkEventRead(event) {
  if (!event?.id || markingReadEventIds.has(event.id)) return
  markingReadEventIds.add(event.id)
  try {
    await notificationCenter.markEventRead(event.id)
  } finally {
    markingReadEventIds.delete(event.id)
  }
}

async function handleMarkAllRead() {
  if (markingAllRead.value || unreadEventCount.value <= 0) return
  await notificationCenter.markAllRead()
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) notificationCenter.refreshCenter()
  },
  { immediate: true }
)
</script>
