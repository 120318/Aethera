<template>
  <div class="flex flex-col gap-item w-full min-h-tab-content">
    <div v-if="initialLoading && items.length === 0" class="ui-tab-empty">
      <i class="pi pi-spinner pi-spin text-display mb-item opacity-50"></i>
      <p class="text-title font-medium">{{ $t('actionList.loadingTitle') }}</p>
      <p class="text-caption text-muted">{{ $t('actionList.loadingDescription') }}</p>
    </div>

    <template v-else>
      <div v-if="shouldShowFilters" class="flex flex-col gap-item">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-item">
          <InputText v-model="keyword" :placeholder="$t('events.keywordSearch')" class="w-full" />
          <MultiSelect
            v-model="selectedKinds"
            :options="kindOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('common.type')"
            class="w-full"
            display="chip"
            :max-selected-labels="1"
            filter
          />
          <MultiSelect
            v-model="selectedStatuses"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('actionList.status')"
            class="w-full"
            display="chip"
            :max-selected-labels="1"
            filter
          />
          <MultiSelect
            v-model="selectedTriggers"
            :options="triggerOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('actionList.trigger')"
            class="w-full"
            display="chip"
            :max-selected-labels="1"
            filter
          />
        </div>
      </div>

      <div v-if="!listLoading && totalRecords === 0" class="ui-tab-empty">
        <p class="text-title font-medium mb-item">{{ $t('actionList.emptyTitle') }}</p>
        <p class="text-caption text-muted">{{ $t('actionList.emptyDescription') }}</p>
      </div>

      <DataView
        v-else
        :value="items"
        :paginator="showPaginator"
        :rows="rows"
        :first="first"
        :total-records="totalRecords"
        lazy
        layout="list"
        paginator-position="both"
        :class="['overflow-hidden ui-dataview-balanced-paginator', { 'ui-dataview-flat': flat }]"
        @page="onPage"
      >
        <template v-if="showPaginator" #paginatorstart>
          <div class="hidden md:flex items-center text-muted">
            {{ $t('actionList.totalPrefix') }}
            <span class="text-primary mx-inline">{{ totalRecords }}</span>
            {{ $t('actionList.totalSuffix') }}
          </div>
        </template>

        <template v-if="showPaginator" #paginatorend>
          <div class="flex items-center gap-item">
            <Button
              v-if="showFilters && hasActiveFilters"
              severity="secondary"
              :label="$t('actionList.clearFilters')"
              icon="pi pi-filter-slash"
              link
              size="small"
              :loading="listLoading"
              @click="resetFilters"
            />
          </div>
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
                <p v-if="getActionSubline(action)" class="text-caption text-muted break-words m-none min-w-0">
                  {{ getActionSubline(action) }}
                </p>
              </div>
              <div
                v-tooltip.top="formatAbsoluteTs(action.ts)"
                class="ui-record-meta-time"
              >
                {{ formatRelativeTs(action.ts) }}
              </div>
            </div>
          </div>
        </template>
      </DataView>
    </template>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'

import AppTag from '@/components/common/AppTag.vue'
import { useActionList } from '@/composables/useActionList'
import { resolveActionKindLabel, resolveActionStatusMeta, resolveActionNameLabel } from '@/constants/actionTypes'
import { formatAbsoluteDateTime, formatDurationMs, formatRelativeTime } from '@/utils/formatters'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'

const props = defineProps({
  mediaId: { type: String, default: null },
  targetType: { type: String, default: null },
  targetId: { type: String, default: null },
  showFilters: { type: Boolean, default: true },
  flat: { type: Boolean, default: false },
})
const mediaId = toRef(props, 'mediaId')
const showFilters = toRef(props, 'showFilters')
const targetId = toRef(props, 'targetId')
const targetType = toRef(props, 'targetType')
const { t } = useI18n()

const TRIGGER_LABELS = {
  manual: 'events.trigger.manual',
  scheduler: 'events.trigger.scheduler',
  event: 'events.trigger.event',
  api: 'events.trigger.api',
  system: 'events.trigger.system',
}

function getActionHeadline(action) {
  return resolveActionNameLabel(action?.action_name)
}

function getActionSubline(action) {
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
  const labelKey = TRIGGER_LABELS[trigger]
  return labelKey ? t(labelKey) : trigger || t('scheduler.unknownTrigger')
}

function statusTone(status) {
  const tone = resolveActionStatusMeta(status)?.tone
  if (tone === 'danger') return 'danger'
  if (tone === 'warn') return 'warn'
  if (tone === 'success') return 'success'
  return 'accent'
}

function formatAbsoluteTs(ts) {
  return formatAbsoluteDateTime(ts)
}

function formatRelativeTs(ts) {
  return formatRelativeTime(ts)
}

function formatDuration(durationMs) {
  return formatDurationMs(durationMs)
}

function resetFilters() {
  keyword.value = ''
  selectedKinds.value = []
  selectedStatuses.value = []
  selectedTriggers.value = []
}

const {
  first,
  hasActiveFilters,
  initialLoading,
  initialize,
  items,
  keyword,
  kindOptions,
  listLoading,
  onPage,
  rows,
  selectedKinds,
  selectedStatuses,
  selectedTriggers,
  shouldShowFilters,
  showPaginator,
  statusOptions,
  totalRecords,
  triggerOptions,
} = useActionList({
  mediaId,
  showFilters,
  targetId,
  targetType,
})

initialize({
  mapKindLabel: resolveActionKindLabel,
  mapStatusLabel: getStatusLabel,
  mapTriggerLabel: getTriggerLabel,
})
</script>
