<template>
  <ConfigDialog
    :model-value="visible"
    :title="$t('alertCenter.title')"
    size="lg"
    @update:model-value="handleVisibleChange"
  >
    <section class="flex flex-col gap-container min-h-tab-content">
      <div v-if="lastError" class="flex items-center gap-item px-item py-item border border-separator rounded-container text-status-error bg-surface">
        <i class="pi pi-exclamation-triangle text-caption" />
        <span class="text-caption">{{ lastError }}</span>
      </div>

      <div class="flex flex-wrap items-center gap-item text-caption text-muted">
        <AppTag :label="$t('alertCenter.runningCount', { count: summary.active_action_count || 0 })" tone="accent" />
        <AppTag :label="$t('alertCenter.errorCount', { count: summary.unacknowledged_error_count || 0 })" tone="danger" />
      </div>

      <section class="flex flex-col gap-item">
        <div v-if="loading && !centerItems.length" class="ui-tab-empty">
          <EmptyState :border="false" :description="$t('alertCenter.loadingStatus')" image="pi pi-spin pi-spinner" />
        </div>
        <div v-else-if="centerItems.length === 0" class="ui-tab-empty">
          <p class="text-title font-medium mb-item">{{ $t('alertCenter.noAlertsTitle') }}</p>
          <p class="text-caption text-muted">{{ $t('alertCenter.noAlertsDescription') }}</p>
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
                  <Button
                    v-if="item.kind === 'alert'"
                    v-tooltip.top="$t('alertCenter.acknowledge')"
                    icon="pi pi-times"
                    severity="secondary"
                    text
                    rounded
                    :aria-label="$t('alertCenter.acknowledge')"
                    class="w-control-icon h-control-icon p-none shrink-0 self-start transition-colors"
                    :loading="acknowledgingAlertIds.has(item.record.id)"
                    @click="handleAcknowledge(item.record)"
                  />
                  <Button
                    v-else-if="canCancelAction(item.record)"
                    v-tooltip.top="$t('operationCenter.cancelTask')"
                    icon="pi pi-times"
                    severity="danger"
                    text
                    rounded
                    :aria-label="$t('operationCenter.cancelTask')"
                    class="w-control-icon h-control-icon p-none shrink-0 self-start transition-colors"
                    :loading="cancellingActionIds.has(item.record.id)"
                    @click="handleCancelAction(item.record)"
                  />
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
import { reactive, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import AppTag from '@/components/common/AppTag.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useAlertCenterStore } from '@/stores/alert-center'
import { useOperationsStore } from '@/stores/operations'
import { resolveActionKindLabel, resolveActionNameLabel, resolveActionStatusMeta, resolvePilotEpisodeActionLabel } from '@/constants/actionTypes'
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
const alertCenter = useAlertCenterStore()
const operationsStore = useOperationsStore()
const { summary, centerItems, lastError, loading } = storeToRefs(alertCenter)
const { t } = useI18n()
const cancellingActionIds = reactive(new Set())
const acknowledgingAlertIds = reactive(new Set())
const listPt = {
  content: { class: 'p-none bg-transparent border-none' },
}

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

function alertTarget(alert) {
  const media = alert?.media
  if (media?.title && media?.year) return `${media.title} (${media.year})`
  return alert?.message_params?.task || alert?.task_id || alert?.target_id || '-'
}

function alertCategoryLabel(alert) {
  const key = alert?.category ? `alertCenter.categories.${alert.category}` : ''
  if (!key) return ''
  const label = t(key)
  return label && label !== key ? label : alert.category
}

function alertMessage(alert) {
  return resolveLocalizedRecordMessage(alert, t('alertCenter.noMessage'))
}

function itemRecord(item) {
  return item?.record || {}
}

function itemStatusLabel(item) {
  if (item?.kind === 'alert') return t('alertCenter.status.error')
  return getStatusLabel(itemRecord(item).status)
}

function itemStatusTone(item) {
  if (item?.kind === 'alert') return 'danger'
  return getStatusTone(itemRecord(item).status)
}

function itemStatusIcon(item) {
  if (item?.kind === 'alert') return 'pi pi-exclamation-triangle'
  return itemRecord(item).status === 'running' ? 'pi pi-spin pi-spinner' : ''
}

function itemTypeLabel(item) {
  const record = itemRecord(item)
  if (item?.kind === 'alert') return alertCategoryLabel(record)
  return getActionTypeLabel(record)
}

function itemTarget(item) {
  const record = itemRecord(item)
  return item?.kind === 'alert' ? alertTarget(record) : actionTarget(record)
}

function itemMessage(item) {
  const record = itemRecord(item)
  return item?.kind === 'alert' ? alertMessage(record) : actionMessage(record)
}

function itemTimestamp(item) {
  const record = itemRecord(item)
  return item?.kind === 'alert' ? (record.last_seen_at || record.updated_at || record.created_at) : actionTimestamp(record)
}

function itemMetaText(item) {
  const record = itemRecord(item)
  if (item?.kind === 'alert') {
    return t('alertCenter.occurrenceCount', { count: record.occurrence_count || 1 })
  }
  return t('alertCenter.runningMeta')
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
    await alertCenter.refreshCenter()
  } finally {
    cancellingActionIds.delete(action.id)
  }
}

async function handleAcknowledge(alert) {
  if (!alert?.id || acknowledgingAlertIds.has(alert.id)) return
  acknowledgingAlertIds.add(alert.id)
  try {
    await alertCenter.acknowledge(alert.id)
  } finally {
    acknowledgingAlertIds.delete(alert.id)
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) alertCenter.refreshCenter()
  },
  { immediate: true }
)
</script>
