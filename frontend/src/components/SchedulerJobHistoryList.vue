<template>
  <div class="flex flex-col gap-item w-full min-h-tab-content">
    <div v-if="initialLoading && items.length === 0" class="ui-tab-empty">
      <i class="pi pi-spinner pi-spin text-display mb-item opacity-50"></i>
      <p class="text-title font-medium">{{ $t('scheduler.historyLoading') }}</p>
      <p class="text-caption text-muted">{{ $t('scheduler.historyLoadingDescription') }}</p>
    </div>

    <div v-else-if="!listLoading && totalRecords === 0" class="ui-tab-empty">
      <p class="text-title font-medium mb-item">{{ $t('scheduler.noHistory') }}</p>
      <p class="text-caption text-muted">{{ $t('scheduler.noHistoryDescription') }}</p>
    </div>

    <DataView
      v-else
      :value="items"
      paginator
      :rows="rows"
      :first="first"
      :total-records="totalRecords"
      lazy
      layout="list"
      paginator-position="both"
      class="overflow-hidden ui-dataview-balanced-paginator ui-dataview-flat"
      @page="onPage"
    >
      <template #paginatorstart>
        <div class="hidden md:flex items-center text-muted">
          {{ $t('taskLive.totalPrefix') }} <span class="text-primary mx-inline">{{ totalRecords }}</span> {{ $t('events.totalSuffix') }}
        </div>
      </template>

      <template #paginatorend>
        <div class="hidden md:flex items-center" aria-hidden="true"></div>
      </template>

      <template #list="slotProps">
        <div
          v-for="(action, index) in slotProps.items"
          :key="action.id || `${action.ts || 'no-ts'}_${index}`"
          class="flex flex-col gap-inline py-container relative border-b border-separator last:border-0"
        >
          <div class="flex items-start gap-item">
            <div class="flex items-center gap-item min-w-0 flex-1">
              <div :class="getActionIconWrapClass(action)">
                <i :class="[getActionIcon(action), 'text-caption']"></i>
              </div>
              <p class="text-body break-words m-none min-w-0">
                {{ getActionHeadline(action) }}
              </p>
            </div>
          </div>

          <div class="ui-record-meta-row">
            <div class="flex flex-wrap items-center gap-inline min-w-0">
              <AppTag :tone="statusTone(action.status)" :value="getStatusLabel(action.status)" />
              <AppTag v-if="action.duration_ms != null" :value="formatDuration(action.duration_ms)" />
              <AppTag :value="resolveActionKindLabel(action.kind)" />
              <AppTag v-if="action.trigger" :value="getTriggerLabel(action.trigger)" />
              <p v-if="getActionMessage(action)" class="text-caption text-muted break-words m-none min-w-0">
                {{ getActionMessage(action) }}
              </p>
            </div>
            <div
              v-tooltip.top="formatAbsoluteDateTime(action.ts)"
              class="ui-record-meta-time"
            >
              {{ formatRelativeTime(action.ts) }}
            </div>
          </div>

          <p v-if="action.error" class="m-none text-caption text-status-error break-words">
            {{ action.error }}
          </p>
        </div>
      </template>
    </DataView>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import DataView from 'primevue/dataview'

import AppTag from '@/components/common/AppTag.vue'
import { useSchedulerJobHistory } from '@/composables/useSchedulerJobHistory'
import { resolveActionKindLabel, resolveActionStatusMeta, resolveActionNameLabel } from '@/constants/actionTypes'
import { formatAbsoluteDateTime, formatDurationMs, formatRelativeTime } from '@/utils/formatters'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  jobId: {
    type: String,
    default: '',
  },
})

const jobId = toRef(props, 'jobId')
const { t } = useI18n()

const TRIGGER_LABELS = {
  manual: 'scheduler.trigger.manual',
  scheduler: 'scheduler.trigger.scheduler',
  event: 'scheduler.trigger.event',
  api: 'scheduler.trigger.api',
  system: 'scheduler.trigger.system',
}

function getActionHeadline(action) {
  return resolveActionNameLabel(action?.action_name)
}

function getActionMessage(action) {
  return resolveLocalizedRecordMessage(action)
}

function getActionIcon(action) {
  return resolveActionStatusMeta(action?.status)?.icon || 'pi pi-bolt'
}

function getActionIconWrapClass(action) {
  const tone = resolveActionStatusMeta(action?.status)?.tone
  if (tone === 'danger') return 'text-status-error shrink-0'
  if (tone === 'warn') return 'text-status-warning shrink-0'
  if (tone === 'success') return 'text-status-success shrink-0'
  return 'text-primary shrink-0'
}

function getStatusLabel(status) {
  return resolveActionStatusMeta(status)?.label || status || t('taskLive.unknownStatus')
}

function getTriggerLabel(trigger) {
  return TRIGGER_LABELS[trigger] ? t(TRIGGER_LABELS[trigger]) : (trigger || t('scheduler.unknownTrigger'))
}

function statusTone(status) {
  const tone = resolveActionStatusMeta(status)?.tone
  if (tone === 'danger') return 'danger'
  if (tone === 'warn') return 'warn'
  if (tone === 'success') return 'success'
  return 'accent'
}

function formatDuration(durationMs) {
  return formatDurationMs(durationMs)
}

const {
  first,
  initialLoading,
  items,
  listLoading,
  onPage,
  rows,
  totalRecords,
} = useSchedulerJobHistory(jobId)
</script>
