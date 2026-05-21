<template>
  <div class="flex flex-col gap-item w-full min-h-tab-content">
    <div v-if="initialLoading && items.length === 0" class="ui-tab-empty">
      <i class="pi pi-spinner pi-spin text-display mb-item opacity-50"></i>
      <p class="text-title font-medium">{{ $t('events.loading') }}</p>
      <p class="text-caption text-muted">{{ $t('resourceSearch.autoRefreshHint') }}</p>
    </div>

    <template v-else>
      <div v-if="shouldShowFilters" class="flex flex-col gap-item">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-item">
          <InputText v-model="keyword" :placeholder="$t('events.keywordSearch')" class="w-full" />
          <MultiSelect
            v-model="selectedLevels"
            :options="levelOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('events.level')"
            class="w-full"
            display="chip"
            :max-selected-labels="1"
            filter
          />
          <MultiSelect
            v-model="selectedTypes"
            :options="typeOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('common.type')"
            class="w-full"
            display="chip"
            :max-selected-labels="1"
            filter
          />
          <MultiSelect
            v-model="selectedSources"
            :options="sourceOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('resourceSearch.source')"
            class="w-full"
            display="chip"
            :max-selected-labels="1"
            filter
          />
        </div>
      </div>

      <div v-if="!listLoading && totalRecords === 0" class="ui-tab-empty">
        <p class="text-title font-medium mb-item">{{ $t('events.emptyTitle') }}</p>
        <p class="text-caption text-muted">{{ $t('events.emptyDescription') }}</p>
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
        class="overflow-hidden ui-dataview-balanced-paginator"
        @page="onPage"
      >
        <template v-if="showPaginator" #paginatorstart>
          <div class="hidden md:flex items-center text-muted">
            {{ $t('taskLive.totalPrefix') }} <span class="text-primary mx-inline">{{ totalRecords }}</span> {{ $t('events.totalSuffix') }}
          </div>
        </template>

        <template v-if="showPaginator" #paginatorend>
          <div class="flex items-center gap-item">
            <Button
              v-if="showFilters && hasActiveFilters"
              severity="secondary"
              :label="$t('resourceSearch.clearFilters')"
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
            v-for="(event, index) in slotProps.items"
            :key="event.id || `${event.ts || 'no-ts'}_${index}`"
            class="flex flex-col gap-inline py-container relative border-b border-separator last:border-0"
          >
            <div class="ui-inline-icon-text">
              <div :class="[getEventIconWrapClass(event), 'ui-inline-icon-text-icon']">
                <i :class="[getEventIcon(event), 'text-caption']"></i>
              </div>
              <div class="ui-inline-icon-text-copy">
                <RouterLink
                  v-if="shouldShowEventMedia(event)"
                  :to="getMediaDetailRoute(event)"
                  class="text-body font-medium break-words m-none text-muted no-underline transition-colors hover:text-primary"
                >
                  {{ getEventDisplayTitle(event) }}
                </RouterLink>
                <span
                  v-if="shouldShowEventMedia(event)"
                  class="text-body text-color shrink-0"
                >
                  ·
                </span>
                <p class="text-body break-words m-none min-w-0">
                  {{ getEventHeadline(event) }}
                </p>
              </div>
            </div>

            <div class="ui-record-meta-row">
              <div class="event-meta-inline min-w-0 flex-1">
                <AppTag :tone="levelTone(event.level)" :value="translateTag(event.level, 'level')" />
                <AppTag v-if="event.source" :value="translateTag(event.source, 'source')" />
                <AppTag v-if="event.addon_name" :value="event.addon_name" />
                <span v-if="getEventSubline(event)" class="text-caption text-muted break-words">
                  {{ getEventSubline(event) }}
                </span>
              </div>
              <div
                v-tooltip.top="formatAbsoluteTs(event.ts)"
                class="ui-record-meta-time"
              >
                {{ formatRelativeTs(event.ts) }}
              </div>
            </div>
          </div>
        </template>

        <template #empty>
          <div class="ui-tab-empty">
            <p class="text-title font-medium mb-item">{{ $t('events.emptyTitle') }}</p>
            <p class="text-caption text-muted">{{ $t('events.emptyDescription') }}</p>
          </div>
        </template>
      </DataView>
    </template>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'

import AppTag from '@/components/common/AppTag.vue'
import { useEventList } from '@/composables/useEventList'
import { isDanmuNotFoundEvent, resolveEventTypeMeta } from '@/constants/eventTypes'
import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  mediaId: { type: String, default: null },
  seasonNumber: { type: Number, default: null },
  showFilters: { type: Boolean, default: true },
  refreshKey: { type: Number, default: 0 },
})
const mediaId = toRef(props, 'mediaId')
const seasonNumber = toRef(props, 'seasonNumber')
const showFilters = toRef(props, 'showFilters')
const refreshKey = toRef(props, 'refreshKey')
const { t } = useI18n()

const TAG_TRANSLATIONS = {
  level: {
    info: 'events.levelInfo',
    warning: 'events.levelWarning',
    error: 'events.levelError',
  },
  source: {
    base: 'events.sourceSystem',
    core: 'events.sourceSystem',
    addon: 'events.sourceAddon',
  },
}

function levelTone(value) {
  if (value === 'error') return 'danger'
  if (value === 'warning') return 'warn'
  if (value === 'info') return 'accent'
  return 'neutral'
}

function getEventMeta(event) {
  if (event?.type === 'pilot.episode.queued' && String(event?.media?.media_id || '').includes(':movie:')) {
    return { subjectKey: 'events.subject.download', actionKey: 'events.action.started', icon: 'pi pi-bolt', tone: 'accent' }
  }
  if (isDanmuNotFoundEvent(event)) {
    return { subjectKey: '', actionKey: 'events.action.danmuNotFound', icon: 'pi pi-comments', tone: 'warn' }
  }
  return resolveEventTypeMeta(event?.type)
}

function translateEventMeta(eventMeta) {
  if (!eventMeta) return null
  return {
    ...eventMeta,
    subject: eventMeta.subjectKey ? t(eventMeta.subjectKey) : '',
    action: eventMeta.actionKey ? t(eventMeta.actionKey) : '',
  }
}

function getEventHeadline(event) {
  const eventMeta = translateEventMeta(getEventMeta(event))
  if (eventMeta) return `${eventMeta.action}${eventMeta.subject}`.trim()
  if (event?.type) return event.type
  return t('events.systemEvent')
}

function getEventTypeLabel(typeValue) {
  const eventMeta = translateEventMeta(resolveEventTypeMeta(typeValue))
  if (eventMeta) return `${eventMeta.subject} ${eventMeta.action}`.trim()
  return typeValue
}

function getEventSubline(event) {
  const message = isDanmuNotFoundEvent(event)
    ? t('eventMessages.danmuNotFound', event?.message_params || {})
    : resolveLocalizedRecordMessage(event)
  if (event?.addon_name && message) return `${event.addon_name} · ${message}`
  if (message) return message
  if (event?.addon_name) return event.addon_name
  return ''
}

function getEventDisplayTitle(event) {
  const title = event?.media?.title || ''
  const year = event?.media?.year
  const seasonNumber = getEventSeasonNumber(event)
  const seasonLabel = seasonNumber ? t('taskLive.seasonLabel', { number: seasonNumber }) : ''
  const baseTitle = title && year ? `${title} (${year})` : title
  if (baseTitle && seasonLabel) return `${baseTitle} · ${seasonLabel}`
  if (baseTitle) return baseTitle
  return null
}

function shouldShowEventMedia(event) {
  return !props.mediaId && !!event?.media?.media_id && !!getEventDisplayTitle(event) && !!getMediaDetailRoute(event)
}

function getEventSeasonNumber(event) {
  const raw = event?.media?.season_number ?? event?.season_number ?? null
  const value = Number(raw)
  return Number.isInteger(value) && value > 0 ? value : null
}

function getMediaDetailRoute(event) {
  const mediaId = event?.media?.media_id
  const seasonNumber = getEventSeasonNumber(event)
  if (String(mediaId || '').includes(':tv:') && !seasonNumber) return null
  return {
    path: `/media/${String(mediaId)}`,
    query: seasonNumber ? { season: seasonNumber } : {},
  }
}

function getEventIcon(event) {
  const eventMeta = getEventMeta(event)
  if (eventMeta?.icon) return eventMeta.icon
  if (event?.level === 'error') return 'pi pi-times-circle'
  if (event?.level === 'warning') return 'pi pi-exclamation-triangle'
  return 'pi pi-info-circle'
}

function getEventIconWrapClass(event) {
  const tone = getEventMeta(event)?.tone
  if (tone === 'danger') return 'text-status-error shrink-0'
  if (tone === 'warn') return 'text-status-warning shrink-0'
  if (tone === 'success') return 'text-status-success shrink-0'
  return 'text-primary shrink-0'
}

function translateTag(value, category) {
  if (!value) return '-'
  const categoryMap = TAG_TRANSLATIONS[category] || {}
  return categoryMap[value] ? t(categoryMap[value]) : value
}

function formatAbsoluteTs(ts) {
  return formatAbsoluteDateTime(ts)
}

function formatRelativeTs(ts) {
  return formatRelativeTime(ts)
}

const {
  first,
  hasActiveFilters,
  initialLoading,
  initialize,
  items,
  keyword,
  levelOptions,
  listLoading,
  onPage,
  resetFilters,
  rows,
  selectedLevels,
  selectedSources,
  selectedTypes,
  shouldShowFilters,
  showPaginator,
  sourceOptions,
  totalRecords,
  typeOptions,
} = useEventList(mediaId, showFilters, refreshKey, seasonNumber)

initialize({
  mapLevelLabel: value => translateTag(value, 'level'),
  mapTypeLabel: getEventTypeLabel,
  mapSourceLabel: value => translateTag(value, 'source'),
})
</script>

<style scoped>
.event-meta-inline {
  line-height: 1.75;
}

.event-meta-inline :deep(.ui-tag) {
  display: inline-flex;
  margin-right: var(--spacing-inline);
  vertical-align: middle;
}

.event-meta-inline > span {
  vertical-align: middle;
}
</style>
