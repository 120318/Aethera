<template>
  <section class="flex flex-col gap-container">
    <DirectoryIntegritySummaryPanel
      :loading="integrityLoading"
      :global-cards="globalSummaryCards"
    />

    <div class="directory-integrity-toolbar">
      <Select
        v-model="directoryFilter"
        :options="directoryOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('mediaManagement.directoryIntegrity.filters.directory')"
        class="w-full"
      />
      <Select
        v-model="scopeFilter"
        :options="scopeOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('mediaManagement.directoryIntegrity.filters.scope')"
        class="w-full"
      />
      <MultiSelect
        v-model="issueTypeFilters"
        :options="issueTypeOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('mediaManagement.directoryIntegrity.filters.issueType')"
        display="chip"
        :max-selected-labels="2"
        class="w-full"
      />
    </div>

    <DirectoryIntegritySummaryPanel
      v-if="!integrityLoading"
      :current-cards="currentDirectorySummaryCards"
      :issue-counts="currentDirectoryIssueCounts"
      :current-panel-class="currentDirectoryPanelClass"
    />

    <DirectoryIntegrityActions
      :scanning="integrityScanning"
      :repairing="integrityRepairing"
      :policy-loading="policyLoading"
      :selected-disabled="selectedRepairableIds.length === 0"
      :all-disabled="visibleRepairableIds.length === 0"
      :config-disabled="!directoryFilter"
      @scan="scanIntegrity"
      @repair-selected="confirmRepairIntegrity(selectedRepairableIds)"
      @repair-all="confirmRepairIntegrity(visibleRepairableIds)"
      @config="openPolicyDialog"
    />

    <div v-if="integrityLoading" class="flex flex-col gap-item">
      <Skeleton v-for="index in 4" :key="index" height="var(--size-control-field-md)" border-radius="var(--radius-item)" />
    </div>

    <div v-else-if="!integrityResult" class="ui-tab-empty">
      <p class="text-title font-medium mb-item">{{ $t('mediaManagement.directoryIntegrity.noResult') }}</p>
      <p class="text-caption text-muted">{{ $t('mediaManagement.directoryIntegrity.noResultDescription') }}</p>
    </div>

    <div v-else-if="directoryIntegrityItems.length === 0" class="ui-tab-empty">
      <p class="text-title font-medium mb-item">{{ $t('mediaManagement.directoryIntegrity.noIssues') }}</p>
      <p class="text-caption text-muted">{{ $t('mediaManagement.directoryIntegrity.noIssuesDescription') }}</p>
    </div>

    <template v-else>
      <div v-if="filteredDirectoryIntegrityItems.length === 0" class="ui-tab-empty">
        <p class="text-title font-medium mb-item">{{ $t('mediaManagement.directoryIntegrity.noFilteredIssues') }}</p>
        <p class="text-caption text-muted">{{ $t('mediaManagement.directoryIntegrity.noFilteredIssuesDescription') }}</p>
      </div>

      <DataView
        v-else
        :value="filteredDirectoryIntegrityItems"
        paginator
        :first="first"
        :rows="rows"
        :total-records="filteredDirectoryIntegrityItems.length"
        layout="list"
        paginator-position="both"
        class="directory-integrity-dataview overflow-hidden ui-dataview-balanced-paginator"
        @page="onPage"
      >
        <template #paginatorstart>
          <div class="directory-integrity-paginator-start">
            <Checkbox
              :model-value="allVisibleRepairableSelected"
              binary
              :disabled="visibleRepairableIds.length === 0"
              @update:model-value="toggleAllVisibleRepairable"
            />
            <span>{{ $t('mediaManagement.directoryIntegrity.totalCount', { count: filteredDirectoryIntegrityItems.length }) }}</span>
            <span>{{ $t('mediaManagement.directoryIntegrity.selectedCount', { count: selectedRepairableIds.length }) }}</span>
          </div>
        </template>

        <template #paginatorend>
          <span class="directory-integrity-paginator-spacer" aria-hidden="true" />
        </template>

        <template #list="slotProps">
          <div class="directory-integrity-list">
            <div
              v-for="item in slotProps.items"
              :key="item.id"
              class="directory-integrity-item"
            >
              <Checkbox
                v-model="selectedItemIds"
                :value="item.id"
                :disabled="!item.repairable || integrityRepairing"
                class="directory-integrity-item__check"
              />
              <div class="directory-integrity-item__main">
                <p class="m-0 text-body font-medium text-color break-all">
                  <RouterLink
                    v-if="item.media_id && mediaDisplayTitle(item) && mediaDetailRoute(item)"
                    :to="mediaDetailRoute(item)"
                    class="text-color no-underline transition-colors hover:text-primary"
                  >
                    {{ mediaDisplayTitle(item) }}
                  </RouterLink>
                  <template v-else>{{ mediaDisplayTitle(item) || item.display_name || item.relative_path || item.path }}</template>
                  <span v-if="item.media_id && mediaDisplayTitle(item) && item.display_name">
                    · {{ item.display_name }}
                  </span>
                </p>
                <div class="flex flex-wrap items-center gap-inline min-w-0">
                  <AppTag :value="formatIntegrityIssueType(item.issue_type)" tone="warn" />
                  <AppTag :value="formatIntegrityScope(item.scope)" tone="accent" />
                  <AppTag :value="formatDirectoryLabel(item)" />
                  <AppTag v-if="item.library_file_name" :value="item.library_file_name" />
                  <AppTag v-if="item.size" :value="formatSizeBytes(item.size)" />
                  <AppTag
                    v-if="item.file_created_at"
                    :value="formatFileCreatedAt(item.file_created_at)"
                    :tooltip="formatFileCreatedAtTooltip(item.file_created_at)"
                  />
                  <AppTag
                    v-if="item.record_created_at"
                    :value="formatRecordCreatedAt(item.record_created_at)"
                    :tooltip="formatRecordCreatedAtTooltip(item.record_created_at)"
                  />
                  <AppTag
                    v-if="item.task_completed_at"
                    :value="formatTaskCompletedAt(item.task_completed_at)"
                    :tooltip="formatTaskCompletedAtTooltip(item.task_completed_at)"
                  />
                  <AppTag
                    v-if="item.downloader_state"
                    :value="formatDownloaderState(item)"
                    tone="danger"
                  />
                  <AppTag
                    v-for="message in filteredTrackerMessages(item)"
                    :key="message"
                    :value="message"
                    tone="muted"
                  />
                </div>
              </div>
              <div class="directory-integrity-item__actions">
                <Button
                  v-tooltip.top="$t('mediaManagement.directoryIntegrity.detail')"
                  icon="pi pi-info-circle"
                  severity="secondary"
                  text
                  :aria-label="$t('mediaManagement.directoryIntegrity.detail')"
                  @click="openDetailDialog(item)"
                />
                <Button
                  v-tooltip.top="formatIntegrityRepairAction(item.repair_action)"
                  icon="pi pi-wrench"
                  severity="secondary"
                  text
                  :loading="isItemRepairing(item.id)"
                  :aria-label="formatIntegrityRepairAction(item.repair_action)"
                  :disabled="!item.repairable || integrityRepairing"
                  @click="confirmRepairIntegrity([item.id])"
                />
              </div>
            </div>
          </div>
        </template>
      </DataView>
    </template>

    <ConfigDialog
      v-model="detailDialogVisible"
      size="lg"
      :closable="false"
      :scroll="!detailShowRaw"
      :content-scroll="detailShowRaw"
    >
      <template #header>
        <div class="flex items-center justify-between w-full">
          <span class="p-dialog-title">{{ $t('mediaManagement.directoryIntegrity.detailTitle') }}</span>
          <div class="flex items-center gap-item">
            <Button
              :icon="detailShowRaw ? 'pi pi-list' : 'pi pi-code'"
              :title="detailShowRaw ? $t('mediaManagement.directoryIntegrity.viewStructured') : $t('mediaManagement.directoryIntegrity.viewRawFields')"
              severity="secondary"
              text
              @click="detailShowRaw = !detailShowRaw"
            />
            <Button
              icon="pi pi-times"
              severity="secondary"
              text
              :title="$t('common.close')"
              @click="closeDetailDialog"
            />
          </div>
        </div>
      </template>

      <div v-if="selectedDetailItem && detailShowRaw" class="directory-integrity-detail-raw">
        <pre class="directory-integrity-detail-raw__content text-caption text-muted m-none whitespace-pre-wrap break-all">{{ prettySelectedDetailItem }}</pre>
      </div>
      <div v-else-if="selectedDetailItem" class="directory-integrity-detail">
        <div
          v-for="section in detailSections(selectedDetailItem)"
          :key="section.key"
          class="ui-dialog-section"
        >
          <label class="ui-dialog-item-title text-caption text-muted">{{ section.title }}</label>
          <div class="directory-integrity-detail-grid">
            <div
              v-for="row in section.rows"
              :key="row.key"
              class="directory-integrity-detail-field"
            >
              <span class="text-caption text-muted">{{ row.label }}</span>
              <RouterLink
                v-if="row.route"
                :to="row.route"
                class="text-body text-color no-underline break-all hover:text-primary"
              >
                {{ row.value }}
              </RouterLink>
              <div v-else-if="Array.isArray(row.value)" class="flex flex-col gap-inline">
                <span
                  v-for="(entry, index) in row.value"
                  :key="`${row.key}-${index}`"
                  :class="['text-body break-all', row.mono ? 'font-mono' : '']"
                >
                  {{ entry }}
                </span>
              </div>
              <span v-else :class="['text-body break-all', row.mono ? 'font-mono' : '']">{{ row.value }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="ui-dialog-section">
        <p class="text-body text-muted m-none">{{ $t('mediaManagement.directoryIntegrity.noDetailData') }}</p>
      </div>
    </ConfigDialog>

    <DirectoryIntegrityPolicyDialog
      v-model="policyDialogVisible"
      :loading="policyLoading"
      :saving="policySaving"
      :policies="visiblePolicyRows"
      :issue-options="allIssueTypeOptions"
      @save="savePolicyDialog"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import DataView from 'primevue/dataview'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Skeleton from 'primevue/skeleton'
import { useConfirm } from 'primevue/useconfirm'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import {
  getDirectoryIntegrityPolicies,
  getDirectoryIntegrityLatest,
  repairDirectoryIntegrity,
  saveDirectoryIntegrityPolicies,
  scanDirectoryIntegrity,
} from '@/api/config'
import { useCommandRuntime } from '@/composables/useCommandRuntime'
import { useNotificationStore } from '@/stores/notification'
import { useOperationsStore } from '@/stores/operations'
import {
  ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES,
  DIRECTORY_REPAIR_COMMAND_TYPES,
  DIRECTORY_SCAN_COMMAND_TYPES,
  DIRECTORY_SCAN_TARGET_ID,
  buildDirectoryIntegrityCountSummary,
  buildDirectoryIntegrityIssueCountTags,
  buildDirectoryIntegritySummaryCards,
  buildDirectoryOptions,
  buildDirectoryOptionSummaries,
  buildPolicyRows,
  createDirectoryIntegritySupport,
  resolveDefaultDirectoryFilter,
} from './directoryIntegritySupport'
import DirectoryIntegrityActions from './DirectoryIntegrityActions.vue'
import DirectoryIntegrityPolicyDialog from './DirectoryIntegrityPolicyDialog.vue'
import DirectoryIntegritySummaryPanel from './DirectoryIntegritySummaryPanel.vue'

const props = defineProps({
  result: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:result'])

const confirm = useConfirm()
const notification = useNotificationStore()
const operations = useOperationsStore()
const { t } = useI18n()

const scanSubmitting = ref(false)
const scanSubmittingTargetId = ref('')
const repairSubmitting = ref(false)
const directoryFilter = ref('')
const scanPollingTargetIds = ref([])
const scopeFilter = ref('')
const issueTypeFilters = ref([])
const selectedItemIds = ref([])
const repairingTargetIds = ref([])
const repairPollingTimer = ref(null)
const policyDialogVisible = ref(false)
const policyLoading = ref(false)
const policySaving = ref(false)
const policyRows = ref([])
const first = ref(0)
const rows = ref(10)
const detailDialogVisible = ref(false)
const detailShowRaw = ref(false)
const selectedDetailItem = ref(null)

const integrityResult = computed({
  get: () => props.result,
  set: value => emit('update:result', value),
})
const {
  buildDetailRawPayload,
  detailSections,
  filteredTrackerMessages,
  formatDirectoryLabel,
  formatDownloaderState,
  formatFileCreatedAt,
  formatFileCreatedAtTooltip,
  formatIntegrityIssueType,
  formatIntegrityRepairAction,
  formatIntegrityScope,
  formatMediaType,
  formatRecordCreatedAt,
  formatRecordCreatedAtTooltip,
  formatSizeBytes,
  formatTaskCompletedAt,
  formatTaskCompletedAtTooltip,
  mediaDetailRoute,
  mediaDisplayTitle,
} = createDirectoryIntegritySupport(t, () => integrityResult.value)
const integrityLoading = computed(() => props.loading)
const integritySummary = computed(() => integrityResult.value?.summary || {})
const directorySummaries = computed(() => (
  Array.isArray(integritySummary.value.directories) ? integritySummary.value.directories : []
))
const directoryIntegrityItems = computed(() => {
  return Array.isArray(integrityResult.value?.items) ? integrityResult.value.items : []
})
const directoryOptionSummaries = computed(() => buildDirectoryOptionSummaries(directorySummaries.value, directoryIntegrityItems.value, policyRows.value))
const directoryOptions = computed(() => buildDirectoryOptions(directoryOptionSummaries.value, { formatMediaType }))

const currentDirectoryBaseSummary = computed(() => {
  if (!directoryFilter.value) return integritySummary.value
  return directoryOptionSummaries.value.find(directory => directory.directory_id === directoryFilter.value) || {}
})

const globalSummaryCards = computed(() => buildDirectoryIntegritySummaryCards(integritySummary.value, t, formatSizeBytes))

const scopeOptions = computed(() => {
  const options = [{ label: t('mediaManagement.directoryIntegrity.filters.allScopes'), value: '' }]
  const seen = new Set()
  for (const item of directoryScopedItems.value) {
    const value = item.scope || ''
    if (!value || seen.has(value)) continue
    seen.add(value)
    options.push({ label: formatIntegrityScope(value), value })
  }
  return options
})

const issueTypeOptions = computed(() => {
  const seen = new Set()
  return issueOptionSourceItems.value
    .filter((item) => {
      if (!item.issue_type || seen.has(item.issue_type)) return false
      seen.add(item.issue_type)
      return true
    })
    .map(item => ({
      label: formatIntegrityIssueType(item.issue_type),
      value: item.issue_type,
    }))
})

const allIssueTypeOptions = computed(() => ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES.map(issueType => ({
  label: formatIntegrityIssueType(issueType),
  value: issueType,
})))

const visiblePolicyRows = computed(() => {
  if (!directoryFilter.value) return []
  return policyRows.value.filter(policy => policy.directory_id === directoryFilter.value)
})

const directoryScopedItems = computed(() => {
  if (!directoryFilter.value) return directoryIntegrityItems.value
  return directoryIntegrityItems.value.filter(item => item.directory_id === directoryFilter.value)
})

const issueOptionSourceItems = computed(() => directoryScopedItems.value.filter((item) => {
  if (scopeFilter.value && item.scope !== scopeFilter.value) return false
  return true
}))

const filteredDirectoryIntegrityItems = computed(() => {
  const issueTypes = new Set(issueTypeFilters.value || [])
  return directoryScopedItems.value.filter((item) => {
    if (scopeFilter.value && item.scope !== scopeFilter.value) return false
    if (issueTypes.size > 0 && !issueTypes.has(item.issue_type)) return false
    return true
  })
})

const currentDirectorySummary = computed(() => ({
  ...currentDirectoryBaseSummary.value,
  ...buildDirectoryIntegrityCountSummary(filteredDirectoryIntegrityItems.value),
}))

const currentDirectorySummaryCards = computed(() => buildDirectoryIntegritySummaryCards(currentDirectorySummary.value, t, formatSizeBytes))

const currentDirectoryIssueCounts = computed(() => buildDirectoryIntegrityIssueCountTags(currentDirectorySummary.value, formatIntegrityIssueType))

const currentDirectoryPanelClass = computed(() => {
  const mediaType = String(currentDirectoryBaseSummary.value?.media_type || '').toLowerCase()
  if (mediaType === 'movie') return 'ui-panel-media-movie'
  if (mediaType === 'tv' || mediaType === 'anime') return 'ui-panel-media-tv'
  return ''
})

const visibleRepairableIds = computed(() => filteredDirectoryIntegrityItems.value
  .filter(item => item.repairable)
  .map(item => item.id))

const selectedRepairableIds = computed(() => {
  const repairable = new Set(visibleRepairableIds.value)
  return selectedItemIds.value.filter(id => repairable.has(id))
})

const allVisibleRepairableSelected = computed(() => (
  visibleRepairableIds.value.length > 0
  && visibleRepairableIds.value.every(id => selectedItemIds.value.includes(id))
))
const scanRuntimeTargetIds = computed(() => {
  const targetIds = new Set(scanPollingTargetIds.value)
  const currentTargetId = directoryFilter.value || DIRECTORY_SCAN_TARGET_ID
  if (currentTargetId) targetIds.add(currentTargetId)
  return [...targetIds]
})
const scanCommandRuntime = useCommandRuntime({
  scope: () => ({
    targetType: 'directory',
    targetIds: scanRuntimeTargetIds.value,
  }),
  commandTypes: DIRECTORY_SCAN_COMMAND_TYPES,
  onTerminal: handleScanCommandTerminal,
})
const currentDirectoryScanActive = computed(() => {
  const targetId = directoryFilter.value
  if (!targetId) return false
  if (scanSubmitting.value && scanSubmittingTargetId.value === targetId) return true
  return scanCommandRuntime.activeCommands.value.some(command => (
    command?.target_id === targetId
    && (command.status === 'queued' || command.status === 'running')
  ))
})
const currentRepairScanId = computed(() => integrityResult.value?.scan_id || '')
const repairRuntimeTargetIds = computed(() => {
  const targetIds = new Set(repairingTargetIds.value)
  if (currentRepairScanId.value) targetIds.add(currentRepairScanId.value)
  return [...targetIds]
})
const repairCommandRuntime = useCommandRuntime({
  scope: () => ({
    targetType: 'directory',
    targetIds: repairRuntimeTargetIds.value,
  }),
  commandTypes: DIRECTORY_REPAIR_COMMAND_TYPES,
  onTerminal: handleRepairCommandTerminal,
})
const integrityScanning = computed(() => currentDirectoryScanActive.value)
const activeRepairCommands = computed(() => repairCommandRuntime.activeCommands.value.filter(command => (
  command?.status === 'queued' || command?.status === 'running'
)))
const activeRepairItemTargetIds = computed(() => activeRepairCommands.value
  .map(command => command.target_id)
  .filter(targetId => targetId && targetId !== currentRepairScanId.value))
const itemRepairingIds = computed(() => new Set([
  ...repairingTargetIds.value,
  ...activeRepairItemTargetIds.value,
]))
const integrityRepairing = computed(() => repairSubmitting.value || activeRepairCommands.value.length > 0 || itemRepairingIds.value.size > 0)
const prettySelectedDetailItem = computed(() => JSON.stringify(buildDetailRawPayload(selectedDetailItem.value), null, 2))

watch(filteredDirectoryIntegrityItems, () => {
  const visible = new Set(filteredDirectoryIntegrityItems.value.map(item => item.id))
  selectedItemIds.value = selectedItemIds.value.filter(id => visible.has(id))
  first.value = 0
})

watch(directoryOptionSummaries, () => {
  if (!directoryFilter.value) {
    directoryFilter.value = resolveDefaultDirectoryFilter(directoryOptionSummaries.value)
    return
  }
  const exists = directoryOptionSummaries.value.some(directory => directory.directory_id === directoryFilter.value)
  if (!exists) {
    directoryFilter.value = resolveDefaultDirectoryFilter(directoryOptionSummaries.value)
  }
}, { immediate: true })

watch(issueTypeOptions, () => {
  const allowed = new Set(issueTypeOptions.value.map(option => option.value))
  issueTypeFilters.value = issueTypeFilters.value.filter(issueType => allowed.has(issueType))
})

watch(scopeOptions, () => {
  if (!scopeFilter.value) return
  const allowed = new Set(scopeOptions.value.map(option => option.value))
  if (!allowed.has(scopeFilter.value)) scopeFilter.value = ''
})

watch(currentRepairScanId, async (scanId) => {
  if (!scanId) return
  await repairCommandRuntime.refreshActiveCommands()
}, { immediate: true })

async function scanIntegrity() {
  if (!directoryFilter.value) return
  const targetId = directoryFilter.value
  trackScanPollingTarget(targetId)
  scanSubmitting.value = true
  scanSubmittingTargetId.value = targetId
  try {
    await scanDirectoryIntegrity({ directory_id: targetId })
    await scanCommandRuntime.refreshActiveCommands()
    await operations.refreshActiveActions()
    scanCommandRuntime.startPolling()
    selectedItemIds.value = []
    notification.success(t('mediaManagement.directoryIntegrity.scanSubmitted'))
  } catch (error) {
    releaseScanPollingTarget(targetId)
    notification.error(t('mediaManagement.directoryIntegrity.scanFailed', { message: error.message }))
  } finally {
    scanSubmitting.value = false
    if (scanSubmittingTargetId.value === targetId) {
      scanSubmittingTargetId.value = ''
    }
  }
}

function trackScanPollingTarget(targetId) {
  if (!targetId || scanPollingTargetIds.value.includes(targetId)) return
  scanPollingTargetIds.value = [...scanPollingTargetIds.value, targetId]
}

function releaseScanPollingTarget(targetId) {
  if (!targetId) return
  scanPollingTargetIds.value = scanPollingTargetIds.value.filter(item => item !== targetId)
}

function toggleAllVisibleRepairable(checked) {
  selectedItemIds.value = checked ? [...visibleRepairableIds.value] : []
}

function onPage(event) {
  first.value = event.first
  rows.value = event.rows
}

function openDetailDialog(item) {
  selectedDetailItem.value = item
  detailShowRaw.value = false
  detailDialogVisible.value = true
}

function closeDetailDialog() {
  detailDialogVisible.value = false
  detailShowRaw.value = false
  selectedDetailItem.value = null
}

function confirmRepairIntegrity(itemIds = []) {
  if (!integrityResult.value?.scan_id || itemIds.length === 0) return
  confirm.require({
    message: t('mediaManagement.directoryIntegrity.repairConfirmMessage', { count: itemIds.length }),
    header: t('mediaManagement.directoryIntegrity.repairConfirmTitle'),
    rejectLabel: t('common.cancel'),
    acceptLabel: t('mediaManagement.directoryIntegrity.repairConfirm'),
    rejectProps: {
      severity: 'secondary',
      outlined: true,
    },
    acceptProps: {
      severity: 'danger',
    },
    accept: async () => {
      await submitIntegrityRepair(itemIds)
    },
  })
}

async function submitIntegrityRepair(itemIds = []) {
  const targetIds = itemIds.filter(Boolean)
  repairingTargetIds.value = [...new Set([...repairingTargetIds.value, ...targetIds])]
  repairSubmitting.value = true
  try {
    await repairDirectoryIntegrity({
      scan_id: integrityResult.value.scan_id,
      item_ids: itemIds,
    })
    await repairCommandRuntime.refreshActiveCommands()
    await operations.refreshActiveActions()
    repairCommandRuntime.startPolling()
    startRepairFallbackPolling()
    selectedItemIds.value = []
    notification.success(t('mediaManagement.directoryIntegrity.repairSubmitted'))
  } catch (error) {
    releaseRepairTargets(targetIds)
    notification.error(t('mediaManagement.directoryIntegrity.repairFailed', { message: error.message }))
  } finally {
    repairSubmitting.value = false
  }
}

async function openPolicyDialog() {
  if (!directoryFilter.value) return
  policyDialogVisible.value = true
  policyLoading.value = true
  try {
    await loadPolicyRows()
  } catch (error) {
    notification.error(t('mediaManagement.directoryIntegrity.policyLoadFailed', { message: error.message }))
  } finally {
    policyLoading.value = false
  }
}

async function loadPolicyRows() {
  const response = await getDirectoryIntegrityPolicies()
  policyRows.value = buildPolicyRows(response)
}

async function savePolicyDialog() {
  policySaving.value = true
  try {
    const payload = {
      policies: policyRows.value.map(policy => ({
        directory_id: policy.directory_id,
        enabled: Boolean(policy.enabled),
        scan_library: Boolean(policy.scan_library),
        scan_download: Boolean(policy.scan_download),
        issue_types: Array.isArray(policy.issue_types) ? policy.issue_types : [],
      })),
    }
    const response = await saveDirectoryIntegrityPolicies(payload)
    policyRows.value = buildPolicyRows(response)
    policyDialogVisible.value = false
    notification.success(t('mediaManagement.directoryIntegrity.policySaved'))
  } catch (error) {
    notification.error(t('mediaManagement.directoryIntegrity.policySaveFailed', { message: error.message }))
  } finally {
    policySaving.value = false
  }
}

async function handleRepairCommandTerminal() {
  const response = await getDirectoryIntegrityLatest()
  integrityResult.value = response.result || null
  await operations.refreshActiveActions()
  await repairCommandRuntime.refreshActiveCommands()
  syncRepairingTargetsFromActiveCommands()
}

async function handleScanCommandTerminal(command) {
  releaseScanPollingTarget(command?.target_id)
  const response = await getDirectoryIntegrityLatest()
  integrityResult.value = response.result || null
  await operations.refreshActiveActions()
}

onMounted(() => void loadPolicyRows())
onUnmounted(stopRepairFallbackPolling)

function isItemRepairing(itemId) {
  return itemRepairingIds.value.has(itemId)
}

function releaseRepairTargets(targetIds = []) {
  const released = new Set(targetIds.filter(Boolean))
  if (released.size === 0) return
  repairingTargetIds.value = repairingTargetIds.value.filter(targetId => !released.has(targetId))
}

function syncRepairingTargetsFromActiveCommands() {
  repairingTargetIds.value = activeRepairItemTargetIds.value
  if (repairingTargetIds.value.length === 0) {
    stopRepairFallbackPolling()
  }
}

function startRepairFallbackPolling() {
  if (repairPollingTimer.value) return
  repairPollingTimer.value = window.setInterval(checkRepairProgress, 1500)
  void checkRepairProgress()
}

function stopRepairFallbackPolling() {
  if (!repairPollingTimer.value) return
  window.clearInterval(repairPollingTimer.value)
  repairPollingTimer.value = null
}

async function checkRepairProgress() {
  if (repairingTargetIds.value.length === 0) {
    stopRepairFallbackPolling()
    return
  }
  await repairCommandRuntime.refreshActiveCommands()
  if (activeRepairCommands.value.length > 0) return
  const response = await getDirectoryIntegrityLatest()
  integrityResult.value = response.result || null
  await operations.refreshActiveActions()
  repairingTargetIds.value = []
  stopRepairFallbackPolling()
}
</script>

<style scoped>
.directory-integrity-toolbar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--spacing-item);
}
.directory-integrity-paginator-start {
  display: flex;
  align-items: center;
  gap: var(--spacing-item);
  color: var(--text-muted);
}
.directory-integrity-dataview :deep(.p-paginator) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
}
.directory-integrity-dataview :deep(.p-paginator-content-start),
.directory-integrity-dataview :deep(.p-paginator-content),
.directory-integrity-dataview :deep(.p-paginator-content-end) {
  min-width: 0;
}
.directory-integrity-dataview :deep(.p-paginator-content) {
  justify-self: center;
}
.directory-integrity-dataview :deep(.p-paginator-content-end) { justify-self: stretch; }
.directory-integrity-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-item);
}
.directory-integrity-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-container);
  padding-block: var(--spacing-item);
  border-bottom: 1px solid var(--border-subtle);
}
.directory-integrity-item__check {
  margin-block-start: var(--spacing-inline);
}
.directory-integrity-item__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--spacing-inline);
}
.directory-integrity-item__actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: var(--spacing-item);
  flex-shrink: 0;
}
.directory-integrity-detail { display: flex; flex-direction: column; gap: var(--spacing-item); }
.directory-integrity-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-item) var(--spacing-block);
}
.directory-integrity-detail-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--spacing-inline);
}
.directory-integrity-detail-raw { min-height: 0; }
.directory-integrity-detail-raw__content { overflow: visible; }
@media (max-width: 767px) {
  .directory-integrity-toolbar {
    grid-template-columns: 1fr;
  }
  .directory-integrity-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
