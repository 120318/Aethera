<template>
  <div class="media-detail-overview-shell">
    <template v-if="cards.showSkeleton">
      <div class="media-overview-layout">
        <div :class="['ui-surface-item', 'media-overview-summary-card', overviewPanelClass]">
          <div class="flex flex-wrap items-center gap-x-item gap-y-inline mt-item">
            <Skeleton v-for="index in 4" :key="`resource-skeleton-row1-${index}`" width="8rem" height="1rem" />
          </div>
          <div class="flex flex-wrap items-center gap-x-item gap-y-inline mt-item">
            <Skeleton v-for="index in 3" :key="`resource-skeleton-row2-${index}`" width="7rem" height="1rem" />
          </div>
        </div>
        <div class="ui-surface-item media-overview-detail-card">
          <div class="flex items-start justify-between gap-item">
            <Skeleton width="5rem" height="0.875rem" />
            <Skeleton width="2rem" height="2rem" border-radius="999px" />
          </div>
          <div class="flex flex-col gap-item">
            <Skeleton width="100%" height="1rem" />
            <Skeleton width="88%" height="1rem" />
            <Skeleton width="76%" height="1rem" />
          </div>
          <div class="media-detail-panel-actions mt-container">
            <Skeleton width="6rem" height="2.5rem" class="rounded" />
            <Skeleton width="6rem" height="2.5rem" class="rounded" />
            <Skeleton width="6rem" height="2.5rem" class="rounded" />
          </div>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="media-overview-layout">
        <div :class="['ui-surface-item', 'media-overview-summary-card', overviewPanelClass]">
          <div class="text-title text-color">{{ $t('mediaDetail.overview') }}</div>
          <div class="media-overview-line media-overview-line-bulleted">
            <span v-if="resourcePrimaryLine.label" class="media-overview-label-group">
              <span :class="resourcePrimaryLine.label.accent ? 'text-primary' : (resourcePrimaryLine.label.muted ? 'text-muted' : 'text-color')">{{ labelTextWithoutColon }}</span>
              <Button
                v-if="detailRows.length > 0"
                v-tooltip.top="detailDialogTitle"
                icon="pi pi-info-circle"
                text
                rounded
                size="small"
                class="media-overview-inline-icon"
                :aria-label="detailDialogTitle"
                @click="releaseDialogVisible = true"
              />
              <span :class="resourcePrimaryLine.label.accent ? 'text-primary' : (resourcePrimaryLine.label.muted ? 'text-muted' : 'text-color')">{{ labelColon }}</span>
            </span>
            <span class="media-overview-line-body">
              <template v-for="(part, partIndex) in resourcePrimaryLine.parts" :key="part.key">
                <span v-if="partIndex > 0" class="media-overview-separator">·</span>
                <span>
                  <template v-for="(segment, segmentIndex) in part.segments" :key="`${part.key}-${segmentIndex}-${segment.key || segment.text}`">
                    <a
                      v-if="segment.url"
                      :href="segment.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="transition-colors"
                      :class="segment.accent ? 'text-primary hover:text-primary-emphasis' : (segment.muted ? 'text-muted hover:text-color' : 'text-color hover:text-color')"
                    >
                      {{ segment.text }}
                    </a>
                    <span v-else :class="segment.accent ? 'text-primary' : (segment.muted ? 'text-muted' : 'text-color')">{{ segment.text }}</span>
                  </template>
                </span>
              </template>
              <span class="text-color">。</span>
            </span>
          </div>
          <div v-if="cards.resourceSummary.statsParts.length > 0" class="media-overview-line media-overview-line-bulleted mt-item">
            <span class="media-overview-line-body">
              <template v-for="(part, partIndex) in cards.resourceSummary.statsParts" :key="part.key">
                <span v-if="partIndex > 0" class="media-overview-separator">·</span>
                <span>
                  <template v-for="(segment, segmentIndex) in part.segments" :key="`${part.key}-${segmentIndex}-${segment.key || segment.text}`">
                    <span :class="segment.accent ? 'text-primary' : (segment.muted ? 'text-muted' : 'text-color')">{{ segment.text }}</span>
                  </template>
                </span>
              </template>
              <span class="text-color">。</span>
            </span>
          </div>
          <div v-if="cards.resourceSummary.secondaryParts.length > 0" class="media-overview-line media-overview-line-bulleted mt-item">
            <span class="media-overview-line-body">
              <template v-for="(part, partIndex) in cards.resourceSummary.secondaryParts" :key="part.key">
                <span v-if="partIndex > 0" class="media-overview-separator">·</span>
                <span>
                  <template v-for="(segment, segmentIndex) in part.segments" :key="`${part.key}-${segmentIndex}`">
                    <span
                      v-tooltip.top="segment.tooltip || null"
                      :class="segment.accent ? 'text-primary' : (segment.muted ? 'text-muted' : 'text-color')"
                    >{{ segment.text }}</span>
                  </template>
                  <span v-if="part.suffix">{{ part.suffix }}</span>
                </span>
              </template>
              <span class="text-color">。</span>
            </span>
          </div>
        </div>
        <div class="ui-surface-item media-overview-detail-card">
          <div class="flex items-start justify-between gap-item">
            <div class="text-title text-color">{{ $t('mediaDetail.subscription') }}</div>
            <Button
              v-tooltip.top="$t('mediaDetail.configureSubscription')" icon="pi pi-cog" text rounded
              :aria-label="$t('mediaDetail.configureSubscription')"
              :disabled="!canMutateSubscription"
              @click="$emit('configure-subscription')"
            />
          </div>
          <div class="flex flex-col gap-item">
            <div class="media-overview-line">
              <span class="text-color">{{ cards.subscription.subscribed ? $t('subscription.subscribed') : $t('subscription.notSubscribed') }}</span>
              <span class="text-muted">·</span>
              <span class="text-color">{{ cards.subscription.followed ? $t('subscription.followed') : $t('subscription.notFollowed') }}</span>
              <span class="text-muted">·</span>
              <span class="text-muted">{{ $t('mediaDetail.subscriptionMode') }}<span class="text-color">{{ cards.subscription.mode }}</span></span>
              <span class="text-muted">·</span>
              <span class="text-muted">{{ $t('mediaDetail.customRules') }}<span class="text-color">{{ cards.currentConfig.customRules }}</span></span>
            </div>
            <div v-if="cards.subscription.lastCheckedLabel" class="media-overview-line">
              <span class="text-muted">{{ $t('mediaDetail.lastChecked') }}<span class="text-color">{{ cards.subscription.lastCheckedLabel }}</span></span>
              <span v-if="cards.subscription.endedReason" class="text-muted">·</span>
              <span v-if="cards.subscription.endedReason" class="text-muted">{{ $t('mediaDetail.endedReason') }}<span class="text-color">{{ cards.subscription.endedReason }}</span></span>
            </div>
            <div v-else-if="cards.subscription.endedReason" class="media-overview-line">
              <span class="text-muted">{{ $t('mediaDetail.endedReason') }}<span class="text-color">{{ cards.subscription.endedReason }}</span></span>
            </div>
            <div class="media-overview-line">
              <span class="text-muted">{{ $t('mediaDetail.directory') }}<span class="text-color">{{ cards.currentConfig.directory }}</span></span>
              <span class="text-muted">·</span>
              <span class="text-muted">{{ $t('mediaDetail.filter') }}<span class="text-color">{{ cards.currentConfig.filter }}</span></span>
              <span class="text-muted">·</span>
              <span class="text-muted">{{ $t('mediaDetail.qualityProfile') }}<span class="text-color">{{ cards.currentConfig.qualityProfile }}</span></span>
            </div>
          </div>
          <div class="media-detail-panel-actions mt-container min-h-control-field-md">
            <template v-if="loadingSubscription || checkingSearch">
              <Skeleton width="6rem" height="2.5rem" class="rounded" />
              <Skeleton width="6rem" height="2.5rem" class="rounded" />
              <Skeleton width="6rem" height="2.5rem" class="rounded" />
            </template>
            <template v-else>
              <span v-tooltip.top="pilotDisabledReason || null" class="inline-flex">
                <Button
                  :label="quickDownloadLabel" icon="pi pi-bolt"
                  severity="primary" :loading="pilotInProgress" :disabled="loading || !canMutateSubscription || pilotDisabled || pilotInProgress"
                  @click="$emit('pilot')"
                />
              </span>
              <Button
                :label="$t('mediaDetail.search')" icon="pi pi-search" severity="secondary" outlined
                :loading="checkingSearch || searchInProgress" :disabled="loading || checkingSearch || searchInProgress || !mediaId" @click="$emit('search')"
              />
              <Button
                :label="subscription?.active ? $t('mediaDetail.cancelSubscription') : $t('mediaDetail.subscribe')" :icon="subscription?.active ? 'pi pi-times' : 'pi pi-star'"
                :severity="subscription?.active ? 'danger' : 'secondary'" outlined :loading="checkingSubscription"
                :disabled="!canMutateSubscription || checkingSubscription" @click="$emit('subscription-click')"
              />
              <Button
                :label="subscription?.followed ? $t('mediaDetail.cancelFollow') : $t('mediaDetail.follow')"
                :icon="subscription?.followed ? 'pi pi-heart-fill' : 'pi pi-heart'"
                :severity="subscription?.followed ? 'danger' : 'secondary'" outlined
                :loading="checkingSubscription" :disabled="!canMutateSubscription || checkingSubscription" @click="$emit('follow')"
              />
              <Button
                v-if="subscription?.active"
                :label="$t('mediaDetail.refresh')"
                icon="pi pi-refresh"
                severity="secondary"
                outlined
                :loading="subscriptionRunInProgress"
                :disabled="subscriptionRunInProgress"
                @click="$emit('run-subscription')"
              />
            </template>
          </div>
        </div>
      </div>
    </template>
    <Dialog
      v-model:visible="releaseDialogVisible"
      modal
      :dismissable-mask="true"
      :header="detailDialogTitle"
      :style="{ width: 'min(56rem, 92vw)' }"
    >
      <div v-if="detailRows.length === 0" class="text-muted">{{ detailDialogEmptyText }}</div>
      <div v-else class="release-detail-table-wrap">
        <table class="release-detail-table">
          <thead>
            <tr>
              <th>{{ isTvScheduleDetail ? $t('mediaDetail.overviewText.airingPlatform') : $t('mediaDetail.overviewText.releaseRegion') }}</th>
              <th>{{ isTvScheduleDetail ? $t('mediaDetail.overviewText.airingType') : $t('mediaDetail.overviewText.releaseType') }}</th>
              <th>{{ isTvScheduleDetail ? $t('mediaDetail.overviewText.airingDate') : $t('mediaDetail.overviewText.releaseDate') }}</th>
              <th>{{ isTvScheduleDetail ? $t('mediaDetail.overviewText.airingNote') : $t('mediaDetail.overviewText.releaseNote') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in detailRows" :key="`${item.region || 'region'}-${item.type || 'type'}-${item.release_date || index}-${index}`">
              <td>{{ item.region || '-' }}</td>
              <td>{{ item.type_label || releaseTypeLabel(item.type) }}</td>
              <td>{{ item.release_date || '-' }}</td>
              <td>
                <span>{{ item.note || '-' }}</span>
                <span v-if="Array.isArray(item.descriptors) && item.descriptors.length" class="block text-muted">
                  {{ $t('mediaDetail.overviewText.releaseDescriptors') }}：{{ item.descriptors.join(', ') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Skeleton from 'primevue/skeleton'
import { useI18n } from 'vue-i18n'
import { dedupePlatforms } from '@/utils/mediaPlatforms'

const props = defineProps({
  cards: { type: Object, required: true },
  resourcePrimaryLine: { type: Object, required: true },
  overviewPanelClass: { type: String, default: '' },
  loadingSubscription: { type: Boolean, default: false },
  checkingSearch: { type: Boolean, default: false },
  canMutateSubscription: { type: Boolean, default: false },
  pilotDisabledReason: { type: String, default: '' },
  quickDownloadLabel: { type: String, default: '' },
  pilotInProgress: { type: Boolean, default: false },
  pilotDisabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  searchInProgress: { type: Boolean, default: false },
  mediaId: { type: String, default: '' },
  subscription: { type: Object, default: null },
  checkingSubscription: { type: Boolean, default: false },
  subscriptionRunInProgress: { type: Boolean, default: false },
})

const { t } = useI18n()
const releaseDialogVisible = ref(false)
const releaseTypeOrder = [1, 2, 3, 4, 5, 6]
const releaseDetailChinaRegion = 'CN'
const isTvScheduleDetail = computed(() => props.cards?.localResources?.schedule?.media_type === 'tv')
const detailDialogTitle = computed(() => (isTvScheduleDetail.value ? t('mediaDetail.overviewText.airingDetails') : t('mediaDetail.overviewText.releaseDetails')))
const detailDialogEmptyText = computed(() => (isTvScheduleDetail.value ? t('mediaDetail.overviewText.airingDetailsEmpty') : t('mediaDetail.overviewText.releaseDetailsEmpty')))
const detailRows = computed(() => (isTvScheduleDetail.value ? airingDetails.value : releaseDetails.value))

const releaseDetails = computed(() => {
  const items = props.cards?.localResources?.releaseDates
  if (!Array.isArray(items)) return []
  const validItems = items
    .filter((item) => item?.release_date && Number(item?.type || 0) > 0)
    .map((item) => ({ ...item, region: String(item.region || '').toUpperCase() }))
  const details = []
  for (const type of releaseTypeOrder) {
    const typedItems = validItems.filter((item) => Number(item.type || 0) === type)
    const globalEarliest = earliestRelease(typedItems)
    const chinaEarliest = earliestRelease(typedItems.filter((item) => item.region === releaseDetailChinaRegion))
    if (globalEarliest) details.push(globalEarliest)
    if (chinaEarliest && !isSameReleaseDetail(globalEarliest, chinaEarliest)) details.push(chinaEarliest)
  }
  return details
})
const airingDetails = computed(() => {
  const schedule = props.cards?.localResources?.schedule || {}
  const rows = []
  const platformText = formatSchedulePlatforms([
    ...(Array.isArray(schedule.online_platforms) ? schedule.online_platforms : []),
    ...(Array.isArray(schedule.networks) ? schedule.networks : []),
  ])
  if (schedule.first_air_date) {
    rows.push({
      region: platformText,
      type_label: t('mediaDetail.overviewText.firstAir'),
      release_date: schedule.first_air_date,
      note: '',
    })
  }
  if (schedule.latest_aired_episode?.air_date) {
    rows.push({
      region: platformText,
      type_label: t('mediaDetail.overviewText.latestAiring'),
      release_date: schedule.latest_aired_episode.air_date,
      note: episodeNote(schedule.latest_aired_episode),
    })
  }
  if (schedule.next_episode_to_air?.air_date) {
    rows.push({
      region: platformText,
      type_label: t('mediaDetail.overviewText.nextAiring'),
      release_date: schedule.next_episode_to_air.air_date,
      note: episodeNote(schedule.next_episode_to_air),
    })
  }
  const seen = new Set(rows.map((row) => `${row.type_label}-${row.release_date}-${row.note}`))
  const airings = Array.isArray(props.cards?.localResources?.airings) ? props.cards.localResources.airings : []
  for (const airing of airings) {
    if (airing?.kind !== 'tv_episode_air' || !airing.date) continue
    const note = episodeNote({
      season_number: airing.season_number,
      episode_number: airing.episode_number,
      title: airing.episode_title,
    })
    const row = {
      region: formatSchedulePlatforms(airing.platforms) || platformText,
      type_label: t('mediaDetail.overviewText.episodeAir'),
      release_date: airing.date,
      note,
    }
    const key = `${row.type_label}-${row.release_date}-${row.note}`
    if (seen.has(key)) continue
    seen.add(key)
    rows.push(row)
  }
  return rows.sort((a, b) => String(a.release_date || '').localeCompare(String(b.release_date || '')))
})

function formatSchedulePlatforms(platforms) {
  return formatDetailPlatforms(platforms).join(' / ')
}

function formatDetailPlatforms(platforms) {
  if (!Array.isArray(platforms)) return []
  return dedupePlatforms(platforms, 4).map((platform) => platform?.name).filter(Boolean)
}

function episodeNote(episode) {
  const segments = []
  if (episode?.season_number) segments.push(t('calendar.seasonLabel', { number: episode.season_number }))
  if (episode?.episode_number) segments.push(t('calendar.episodeLabel', { number: episode.episode_number }))
  if (episode?.title) segments.push(episode.title)
  return segments.join(' · ')
}

function earliestRelease(items) {
  if (!Array.isArray(items) || items.length === 0) return null
  return [...items].sort((a, b) => {
    const date = String(a?.release_date || '').localeCompare(String(b?.release_date || ''))
    if (date !== 0) return date
    const regionA = String(a?.region || '').toUpperCase() === releaseDetailChinaRegion ? 0 : 1
    const regionB = String(b?.region || '').toUpperCase() === releaseDetailChinaRegion ? 0 : 1
    if (regionA !== regionB) return regionA - regionB
    return String(a?.region || '').localeCompare(String(b?.region || ''))
  })[0]
}

function isSameReleaseDetail(left, right) {
  if (!left || !right) return false
  return (
    Number(left.type || 0) === Number(right.type || 0)
    && String(left.region || '').toUpperCase() === String(right.region || '').toUpperCase()
    && String(left.release_date || '') === String(right.release_date || '')
    && String(left.certification || '') === String(right.certification || '')
    && String(left.note || '') === String(right.note || '')
  )
}

const labelTextWithoutColon = computed(() => {
  const text = props.resourcePrimaryLine?.label?.text || ''
  return text.endsWith('：') ? text.slice(0, -1) : text
})
const labelColon = computed(() => {
  const text = props.resourcePrimaryLine?.label?.text || ''
  return text.endsWith('：') ? '：' : ''
})

function releaseTypeLabel(type) {
  const key = `mediaDetail.overviewText.releaseType${Number(type || 0)}`
  const label = t(key)
  return label === key ? String(type || '-') : label
}

defineEmits([
  'configure-subscription',
  'pilot',
  'search',
  'subscription-click',
  'follow',
  'run-subscription',
])
</script>

<style scoped>
.media-detail-overview-shell { width: 100%; }

.media-overview-layout {
  gap: var(--spacing-block);
  width: 100%;
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
}

@media (min-width: 960px) { .media-overview-layout { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

.media-overview-line {
  gap: var(--spacing-inline);
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  color: var(--text-muted);
  font-size: var(--text-body);
  font-weight: 400;
  line-height: 1.6;
}

.media-overview-line-body {
  display: inline;
  flex: 1 1 0;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: normal;
}

.media-overview-label-group {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-inline);
  line-height: 1.6;
}

.media-overview-inline-icon {
  width: 1.5rem;
  height: 1.5rem;
  min-width: 1.5rem;
  padding: 0;
}

.media-overview-separator {
  color: var(--text-muted);
  margin: 0 var(--spacing-inline);
}

.media-overview-line-bulleted::before {
  content: "•";
  color: var(--text-muted);
  margin-right: var(--spacing-inline);
  flex-shrink: 0;
}

.media-overview-summary-card { background-color: var(--panel-surface-bg, var(--surface-content)); }

.media-overview-detail-card {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.media-detail-panel-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-item);
}

.release-detail-table-wrap {
  overflow-x: auto;
}

.release-detail-table {
  width: 100%;
  border: 1px solid var(--border-default);
  border-collapse: collapse;
  font-size: var(--text-body);
}

.release-detail-table th,
.release-detail-table td {
  padding: var(--spacing-inline) var(--spacing-item);
  border: 1px solid var(--border-default);
  text-align: left;
  vertical-align: top;
}

.release-detail-table th {
  background-color: var(--surface-subtle);
  color: var(--text-muted);
  font-weight: 600;
  white-space: nowrap;
}

@media (max-width: 767px) {
  .media-overview-line {
    display: block;
  }

  .media-overview-line > span,
  .media-overview-line-body {
    display: inline;
  }

  .media-overview-line-bulleted::before {
    display: inline;
  }
}

</style>
