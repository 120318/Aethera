<template>
  <div class="flex flex-col gap-item py-item border-b border-separator last:border-0">
    <div class="flex flex-col sm:flex-row items-start sm:items-stretch gap-item min-w-0">
      <div class="min-w-0 flex flex-col gap-inline flex-1">
        <div class="flex flex-wrap items-center gap-inline min-w-0">
          <RouterLink
            v-if="detailRoute"
            :to="detailRoute"
            class="text-body font-semibold break-words text-color no-underline transition-colors hover:text-primary"
            @click.stop
          >
            {{ displayTitle }}
          </RouterLink>
          <span v-else class="text-body font-semibold break-words text-color">{{ displayTitle }}</span>
        </div>

        <div class="flex flex-wrap items-center gap-inline min-w-0">
          <div class="flex flex-wrap items-center gap-inline min-w-0">
            <AppTag :label="mediaTypeLabel" />
            <AppTag v-if="item.monitor.subscribed" :label="t('subscription.subscribed')" tone="success" />
            <AppTag v-if="item.monitor.followed" :label="t('subscription.followed')" tone="accent" />
            <AppTag v-if="deletePending" :label="t('mediaManagement.status.deleting')" tone="danger" />
            <AppTag v-if="item.active_task_count > 0" :label="t('mediaManagement.labels.downloadingCount', { count: item.active_task_count })" tone="warn" />
            <AppTag v-else-if="isDownloaded" :label="t('mediaManagement.status.downloaded')" tone="warn" />
            <AppTag v-if="libraryEpisodeCount > 0" :label="t('mediaManagement.labels.libraryEpisodes', { count: libraryEpisodeCount })" />
            <AppTag v-if="originalDiscPackageCount > 0" :label="t('mediaManagement.labels.libraryOriginalDiscs', { count: originalDiscPackageCount })" />
            <AppTag v-if="showLibraryFileCount" :label="t('mediaManagement.labels.libraryFiles', { count: item.library_count })" />
            <AppTag v-if="item.issues?.has_issues" :label="issueSummaryLabel" tone="danger" />
          </div>
        </div>
      </div>

      <div class="media-management-card-side flex w-full sm:w-auto sm:self-stretch flex-col items-end gap-inline shrink-0">
        <div class="media-management-card-actions flex flex-wrap justify-end gap-inline">
          <Button
            v-if="item.monitor.followed"
            v-tooltip.top="item.monitor.subscribed ? t('mediaManagement.tooltips.cancelSubscriptionFirst') : t('mediaDetail.cancelFollow')"
            icon="pi pi-heart-fill"
            severity="secondary"
            text
            :disabled="item.monitor.subscribed || deletePending"
            :loading="actionLoading === 'follow'"
            @click.stop="$emit('toggle-follow', item)"
          />
          <Button
            v-if="item.monitor.subscribed"
            v-tooltip.top="t('mediaDetail.cancelSubscription')"
            icon="pi pi-star-fill"
            severity="success"
            text
            :disabled="deletePending"
            :loading="actionLoading === 'subscription'"
            @click.stop="$emit('toggle-subscription', item)"
          />
          <Button
            v-tooltip.top="deletePending ? t('mediaManagement.tooltips.deletePending') : t('mediaManagement.tooltips.deleteFiles')"
            icon="pi pi-trash"
            severity="danger"
            text
            :disabled="deletePending"
            :loading="actionLoading === 'delete' || deletePending"
            @click.stop="$emit('delete-files', item)"
          />
        </div>

        <div
          v-tooltip.top="lastActivityAbsoluteText"
          class="mt-auto text-right text-caption text-muted"
        >
          {{ t('mediaManagement.labels.lastActivity', { value: lastActivityText }) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'

import AppTag from '@/components/common/AppTag.vue'
import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'

const props = defineProps({
  item: {
    type: Object,
    required: true
  },
  actionLoading: {
    type: String,
    default: ''
  },
  deletePending: {
    type: Boolean,
    default: false
  }
})

defineEmits(['toggle-follow', 'toggle-subscription', 'delete-files'])

const { t } = useI18n()

const mediaTypeLabel = computed(() => {
  if (props.item.media_type === 'movie') return t('mediaManagement.mediaType.movie')
  if (props.item.media_type === 'tv') return t('mediaManagement.mediaType.tv')
  return props.item.media_type || '-'
})

const displayTitle = computed(() => {
  const title = props.item.title || '-'
  const year = props.item.year ? ` (${props.item.year})` : ''
  const season = props.item.season_number
    ? ` · ${t('taskLive.seasonLabel', { number: props.item.season_number })}`
    : ''
  return `${title}${year}${season}`
})

const isDownloaded = computed(() => {
  const taskCount = props.item?.task_count || 0
  const activeTaskCount = props.item?.active_task_count || 0
  const libraryCount = props.item?.library_count || 0
  return taskCount > 0 && activeTaskCount === 0 && libraryCount === 0
})

const libraryEpisodeCount = computed(() => Number(props.item?.library_episode_count || 0))
const originalDiscPackageCount = computed(() => Number(props.item?.original_disc_package_count || 0))
const showLibraryFileCount = computed(() => {
  if (Number(props.item?.library_count || 0) <= 0) return false
  if (props.item?.media_type === 'tv' && libraryEpisodeCount.value > 0) return false
  return originalDiscPackageCount.value <= 0
})
const issueSummaryLabel = computed(() => {
  const issues = props.item?.issues || {}
  if (issues.summary_key) return t(issues.summary_key, issues.summary_params || {})
  return issues.summary || t('mediaManagement.status.issues')
})

const detailRoute = computed(() => {
  if (!props.item?.media_id) return null
  if (props.item?.media_type === 'tv' && !props.item.season_number) return null
  return {
    name: 'MediaDetail',
    params: { mediaId: props.item.media_id },
    query: props.item.season_number ? { season: props.item.season_number } : {},
  }
})

const lastActivityText = computed(() => {
  if (!props.item.last_activity_at) return t('common.noData')
  return formatRelativeTime(props.item.last_activity_at)
})

const lastActivityAbsoluteText = computed(() => {
  if (!props.item.last_activity_at) return t('common.noData')
  return formatAbsoluteDateTime(props.item.last_activity_at)
})
</script>

<style scoped>
.media-management-card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--spacing-item);
}
</style>
