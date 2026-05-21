<template>
  <div>
    <MediaSourceMappingPanel
      v-if="sourceMappingRequired"
      :mapping="sourceMappingRequired"
      :form="sourceMappingForm"
      :candidates="sourceMappingCandidates"
      :candidates-loading="sourceMappingCandidatesLoading"
      :douban-url="sourceMappingDoubanUrl"
      :tmdb-candidate-url="tmdbCandidateUrl"
      @search="runSourceMappingCandidateSearch"
      @candidate-select="handleSourceMappingCandidateSelect"
      @tmdb-input="handleSourceMappingTMDBInput"
      @open-candidate="openTmdbCandidate"
      @retry="handleFetchDetail"
      @submit="submitSourceMapping"
    />

    <PageError v-else-if="error" :error="error" @retry="handleFetchDetail" />

    <div v-else class="flex flex-col gap-block w-full">
      <MediaStaticInfo
        :media-id="mediaId"
        :detail="detail || {}"
        :loading="loading"
        :selected-season-number="selectedSeasonNumber"
        :season-options="seasonOptions"
        :can-edit-external-mapping="canEditExternalMapping"
        :external-mapping-loading="profileRefreshInProgress"
        @season-change="handleSeasonChange"
        @edit-external-mapping="openExternalMappingDialog"
      />

      <MediaDetailOverviewPanel
        :cards="detailOverviewCards"
        :resource-primary-line="resourcePrimaryLine"
        :overview-panel-class="overviewPanelClass"
        :loading-subscription="loadingSubscription"
        :checking-search="checkingSearch"
        :can-mutate-subscription="canMutateSubscription"
        :pilot-disabled-reason="pilotDisabledReason"
        :quick-download-label="quickDownloadLabel"
        :pilot-in-progress="pilotInProgress"
        :pilot-disabled="pilotDisabled"
        :loading="loading"
        :search-in-progress="searchInProgress"
        :media-id="mediaId"
        :subscription="subscription"
        :checking-subscription="checkingSubscription"
        :subscription-run-in-progress="subscriptionRunInProgress"
        @configure-subscription="subscriptionDialog.visible = true"
        @pilot="handlePilotEpisodeDownload"
        @search="triggerSearch"
        @subscription-click="handleSubscriptionClick"
        @follow="handleFollowToggle"
        @run-subscription="handleRunSubscription"
      />

      <ResourceActionTabs 
        :media-id="mediaId"
        :detail="detail" 
        :detail-loading="loading"
        :overview="overview"
        :overview-loading="!dataLoaded.overview"
        :resources="tabData.resources"
        :resources-total-episodes="tabData.resourcesTotalEpisodes"
        :tasks="tabData.tasks"
        :operation-commands="activeCommands"
        :search-command="activeSearchCommand"
        :task-create-pending="taskCreatePending"
        :task-create-placeholder-visible="taskCreatePlaceholderVisible"
        :pending-task-preview="pendingTaskPreview"
        :task-realtime-overrides="taskRealtimeOverrides"
        :search-results="hasPreviewResults ? resourcePreviewResults : null" 
        :has-searched="hasSearched || hasPreviewResults"
        :search-trigger="searchTrigger" 
        :search-results-refresh-trigger="searchResultsRefreshTrigger"
        :season-number="selectedSeasonNumber"
        :catalogs="detailOverviewCatalogs"
        :data-loaded="dataLoaded" 
        :active-tab="activeTab"
        @update:active-tab="activeTab = $event" 
        @view-details="handleViewDetails" 
        @delete="openDeleteModal" 
        @search-download="handleSearchDownload"
        @search-complete="onSearchComplete" 
        @search-loading="handleSearchLoading"
        @command-submitted="handleCommandSubmitted"
        @task-updated="handleTaskUpdated"
        @task-view-updated="handleTaskViewUpdated"
      />

      <ConfigDialog v-model="deleteDialog.visible" :title="$t('taskLive.deleteConfirmTitle')" size="sm" :scroll="false">
        <div class="ui-dialog-body">
          <div class="ui-dialog-section">
            <p class="text-body m-none break-all">
              {{ $t('taskLive.deleteConfirmPrefix') }}
              <strong>{{ deleteTargetDisplayName }}</strong>
              {{ $t('mediaDetail.deleteConfirmSuffix', { type: deleteDialog.target?.is_package ? $t('resourceKind.originalDisc') : $t('mediaDetail.file') }) }}
            </p>
          </div>
        </div>
        <template #footer>
          <Button :label="$t('common.cancel')" severity="secondary" outlined @click="deleteDialog.visible = false" />
          <Button :label="$t('taskLive.confirmDelete')" severity="primary" :loading="deleteDialog.loading" @click="confirmDelete" />
        </template>
      </ConfigDialog>

      <ConfigDialog
        v-model="externalMappingDialog.visible"
        :title="$t('mediaDetail.correctMedia')"
        size="sm"
        :scroll="false"
      >
        <div class="ui-dialog-section">
          <span class="text-caption text-muted">
            {{ $t('mediaDetail.currentTmdbId', { id: metadataSourceIdLabel || $t('mediaDetail.unbound') }) }}
            <span class="text-primary">{{ externalMappingDialogHint }}</span>
          </span>
        </div>
        <div :class="['grid gap-container', isTvMedia ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1']">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block" for="media-detail-tmdb-id-input">{{ $t('mediaDetail.tmdbIdLabel') }}</label>
            <InputText
              id="media-detail-tmdb-id-input"
              v-model.trim="externalMappingDialog.tmdbId"
              class="w-full"
              :placeholder="$t('mediaDetail.tmdbIdPlaceholder')"
              :disabled="externalMappingReadOnly || externalMappingDialog.submitting"
              @keyup.enter="submitExternalMapping"
            />
          </div>
          <div v-if="isTvMedia" class="ui-dialog-section">
            <label class="ui-dialog-item-title block" for="media-detail-season-number-input">{{ $t('mediaDetail.seasonNumber') }}</label>
            <InputNumber
              id="media-detail-season-number-input"
              v-model="externalMappingDialog.seasonNumber"
              class="w-full"
              input-class="w-full"
              :placeholder="$t('mediaDetail.seasonNumberPlaceholder')"
              :min="1"
              :use-grouping="false"
              :disabled="externalMappingReadOnly || externalMappingDialog.submitting"
              @keyup.enter="submitExternalMapping"
            />
          </div>
          <div v-if="isTvMedia" class="ui-dialog-section">
            <label class="ui-dialog-item-title block" for="media-detail-episode-count-override-input">{{ $t('mediaDetail.episodeCountOverride') }}</label>
            <InputNumber
              id="media-detail-episode-count-override-input"
              v-model="externalMappingDialog.episodeCountOverride"
              class="w-full"
              input-class="w-full"
              :placeholder="$t('mediaDetail.episodeCountOverridePlaceholder')"
              :min="1"
              :use-grouping="false"
              :disabled="externalMappingReadOnly || externalMappingDialog.submitting"
              @keyup.enter="submitExternalMapping"
            />
          </div>
        </div>
        <template #footer>
          <Button :label="$t('common.cancel')" text :disabled="externalMappingDialog.submitting" @click="closeExternalMappingDialog" />
          <Button
            v-tooltip.top="$t('mediaDetail.refreshCurrentProfile')"
            :label="$t('mediaDetail.forceRefresh')"
            severity="secondary"
            outlined
            :loading="externalMappingDialog.refreshing || profileRefreshInProgress"
            :disabled="externalMappingDialog.submitting || externalMappingDialog.refreshing || profileRefreshInProgress"
            @click="submitProfileRefresh"
          />
          <Button v-if="!externalMappingReadOnly" :label="$t('common.save')" :loading="externalMappingDialog.submitting" @click="submitExternalMapping" />
        </template>
      </ConfigDialog>

      <SubscriptionDialog
        v-model:visible="subscriptionDialog.visible"
        :media-id="mediaId"
        :season-number="selectedSeasonNumber" :detail="detail"
        :initial-state="subscription"
        :initial-config="downloadConfig"
        :catalogs="detailOverviewCatalogs"
        @saved="handleSubscriptionSaved"
        @command-submitted="handleCommandSubmitted"
      />

      <LibraryFileDetailDialog
        v-model="libraryDetailDialog.visible"
        :loading="libraryDetailDialog.loading"
        :record="libraryDetailDialog.record"
        :package-detail="libraryDetailDialog.package"
        :resource="libraryDetailDialog.resource"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { useMediaDetailPage } from '@/composables/useMediaDetailPage'
import PageError from '@/components/common/PageError.vue'
import MediaStaticInfo from "./MediaStaticInfo.vue"
import ResourceActionTabs from "./ResourceActionTabs.vue"
import SubscriptionDialog from "./SubscriptionDialog.vue"
import LibraryFileDetailDialog from '@/components/common/LibraryFileDetailDialog.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import MediaDetailOverviewPanel from '@/components/media-detail/MediaDetailOverviewPanel.vue'
import MediaSourceMappingPanel from '@/components/media-detail/MediaSourceMappingPanel.vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const {
  mediaId,
  selectedSeasonNumber,
  currentSeasonEpisodeCountOverride,
  seasonOptions,
  entrySourceContext,
  sourceMappingRequired,
  sourceMappingCandidates,
  sourceMappingCandidatesLoading,
  searchSourceTMDBCandidates,
  tmdbCandidateUrl,
  activeTab,
  loading,
  detail,
  error,
  tabData,
  overview,
  dataLoaded,
  subscription,
  downloadConfig,
  loadingSubscription,
  checkingSubscription,
  subscriptionRunInProgress,
  subscriptionDialog,
  canMutateSubscription,
  handleFollowToggle,
  handleRunSubscription,
  handlePilotEpisodeDownload,
  handleAttachTMDBMapping,
  handleAttachSourceTMDBMapping,
  handleSeasonChange,
  handleRefreshMediaProfile,
  hasSearched,
  checkingSearch,
  activeCommands,
  resourcePreviewResults,
  hasPreviewResults,
  searchTrigger,
  searchResultsRefreshTrigger,
  searchInProgress,
  taskCreatePending,
  taskCreatePlaceholderVisible,
  pendingTaskPreview,
  taskRealtimeOverrides,
  activeSearchCommand,
  pilotInProgress,
  profileRefreshInProgress,
  pilotDisabled,
  pilotDisabledReason,
  quickDownloadLabel,
  detailOverviewCards,
  detailOverviewCatalogs,
  triggerSearch,
  onSearchComplete,
  handleSearchLoading,
  handleSearchDownload,
  handleCommandSubmitted,
  handleSubscriptionClick,
  handleFetchDetail,
  deleteDialog,
  openDeleteModal,
  confirmDelete,
  libraryDetailDialog,
  handleViewDetails,
  handleTaskUpdated,
  handleTaskViewUpdated,
  handleSubscriptionSaved,
} = useMediaDetailPage()

const sourceMappingForm = reactive({
  tmdbId: '',
  seasonNumber: null,
  episodeCountOverride: null,
  searchQuery: '',
  selectedCandidateId: null,
  submitting: false,
})

const externalMappingDialog = reactive({
  visible: false,
  tmdbId: '',
  seasonNumber: null,
  episodeCountOverride: null,
  submitting: false,
  refreshing: false,
})

watch(sourceMappingRequired, (value) => {
  sourceMappingForm.tmdbId = ''
  sourceMappingForm.seasonNumber = value?.season_number || null
  sourceMappingForm.episodeCountOverride = null
  sourceMappingForm.searchQuery = value?.search_query || value?.title || ''
  sourceMappingForm.selectedCandidateId = null
  if (value && sourceMappingForm.searchQuery) {
    searchSourceTMDBCandidates(sourceMappingForm.searchQuery)
  }
}, { immediate: true })

async function runSourceMappingCandidateSearch() {
  sourceMappingForm.selectedCandidateId = null
  await searchSourceTMDBCandidates(sourceMappingForm.searchQuery)
}

function handleSourceMappingCandidateSelect(tmdbId) {
  const normalized = String(tmdbId || '').trim()
  sourceMappingForm.tmdbId = normalized
}

function handleSourceMappingTMDBInput() {
  if (sourceMappingForm.selectedCandidateId && sourceMappingForm.tmdbId !== sourceMappingForm.selectedCandidateId) {
    sourceMappingForm.selectedCandidateId = null
  }
}

function openTmdbCandidate(event, option) {
  event?.preventDefault?.()
  event?.stopPropagation?.()
  event?.stopImmediatePropagation?.()
  const url = tmdbCandidateUrl(option)
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

const sourceMappingDoubanUrl = computed(() => {
  const doubanId = sourceMappingRequired.value?.douban_id || sourceMappingRequired.value?.source_id
  return doubanId ? `https://movie.douban.com/subject/${doubanId}/` : ''
})

const metadataSourceIdLabel = computed(() => (detail.value?.tmdb_id ? String(detail.value.tmdb_id) : ''))
const hasDoubanId = computed(() => Boolean(String(detail.value?.douban_id || '').trim()))
const externalMappingReadOnly = computed(() => false)
const canEditExternalMapping = computed(() => canMutateSubscription.value && (hasDoubanId.value || !entrySourceContext.value?.source))
const externalMappingDialogHint = computed(() => (
  t('mediaDetail.externalMappingEditHint')
))
const resourcePrimaryLine = computed(() => {
  const parts = detailOverviewCards.value?.resourceSummary?.primaryParts || []
  const firstPart = parts[0]
  const firstSegment = firstPart?.segments?.[0]
  if (!firstSegment?.text?.endsWith('：')) {
    return { label: null, parts }
  }
  return {
    label: firstSegment,
    parts: [
      {
        ...firstPart,
        segments: firstPart.segments.slice(1),
      },
      ...parts.slice(1),
    ],
  }
})

function openExternalMappingDialog() {
  externalMappingDialog.tmdbId = detail.value?.tmdb_id ? String(detail.value.tmdb_id) : ''
  externalMappingDialog.seasonNumber = selectedSeasonNumber.value || detail.value?.season_number || null
  externalMappingDialog.episodeCountOverride = currentSeasonEpisodeCountOverride.value
  externalMappingDialog.visible = true
}

function closeExternalMappingDialog() {
  if (externalMappingDialog.submitting) return
  externalMappingDialog.visible = false
}

async function submitExternalMapping() {
  if (externalMappingReadOnly.value || externalMappingDialog.submitting) return
  externalMappingDialog.submitting = true
  try {
    const ok = await handleAttachTMDBMapping(
      externalMappingDialog.tmdbId,
      externalMappingDialog.seasonNumber,
      externalMappingDialog.episodeCountOverride,
    )
    if (ok) {
      externalMappingDialog.visible = false
    }
  } finally {
    externalMappingDialog.submitting = false
  }
}

async function submitSourceMapping() {
  if (sourceMappingForm.submitting) return
  sourceMappingForm.submitting = true
  try {
    await handleAttachSourceTMDBMapping(
      sourceMappingForm.tmdbId,
      sourceMappingForm.seasonNumber,
      sourceMappingForm.episodeCountOverride,
    )
  } finally {
    sourceMappingForm.submitting = false
  }
}

async function submitProfileRefresh() {
  if (externalMappingDialog.refreshing || profileRefreshInProgress.value) return
  externalMappingDialog.refreshing = true
  try {
    const ok = await handleRefreshMediaProfile()
    if (ok) {
      externalMappingDialog.visible = false
    }
  } finally {
    externalMappingDialog.refreshing = false
  }
}

const deleteTargetDisplayName = computed(() => (
  deleteDialog.target?.file_name
  || deleteDialog.target?.resource_title
  || deleteDialog.target?.title
  || deleteDialog.target?.name
  || t('mediaDetail.unknownFile')
))
const isTvMedia = computed(() => (
  detail.value?.type === 'tv'
  || detail.value?.media_type === 'tv'
  || mediaId.value?.includes(':tv:')
))
const overviewPanelClass = computed(() => {
  if (isTvMedia.value) return 'ui-panel-media-tv'
  if (detail.value?.type === 'movie' || detail.value?.media_type === 'movie' || mediaId.value?.includes(':movie:')) {
    return 'ui-panel-media-movie'
  }
  return ''
})
</script>
