<template>
  <div class="flex flex-col gap-container">
    <IndexerCardGrid
      :indexers="config.indexers || []"
      :dragged-indexer-id="draggedIndexerId"
      :drag-over-indexer-id="dragOverIndexerId"
      :test-loading="testLoading"
      :current-testing-indexer="currentTestingIndexer"
      @add="addIndexer"
      @edit="editIndexer"
      @remove="removeIndexer"
      @test="testIndexerConnection"
      @toggle-enabled="toggleIndexerEnabled"
      @open-sites="openSiteStatusDialog"
      @drag-start="handleDragStart"
      @drag-over="handleDragOver"
      @drop="handleDrop"
      @drag-end="handleDragEnd"
    />

    <IndexerEditorDialog
      v-model:visible="indexerDialogVisible"
      :title="indexerDialogTitle"
      :indexer="currentIndexer"
      :type-options="indexerTypeOptions"
      :url-placeholder="indexerUrlPlaceholder"
      :url-help="indexerUrlHelp"
      @type-change="handleIndexerTypeChange"
      @save="saveIndexer"
    />

    <IndexerSiteStatusDialog
      v-model:visible="siteStatusDialogVisible"
      :title="siteStatusDialogTitle"
      :indexer-id="currentDialogIndexerId"
      :sites="currentDialogSites"
      :sites-error="currentDialogSitesError"
      :health-loading="healthLoading"
      :sites-loading="sitesLoading"
      :get-status-label="getStatusLabel"
      :get-status-tone="getStatusTone"
      :format-time="formatTime"
      :is-site-setting-disabled="isSiteSettingDisabled"
      @update-site-setting="updateSiteSetting"
      @update-media-type="updateMediaType"
      @update-search-mode="updateSearchMode"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import IndexerCardGrid from '@/components/config/IndexerCardGrid.vue'
import IndexerEditorDialog from '@/components/config/IndexerEditorDialog.vue'
import IndexerSiteStatusDialog from '@/components/config/IndexerSiteStatusDialog.vue'
import {
  createIndexer,
  deleteIndexer,
  getIndexerHealth,
  getIndexerSites,
  reorderIndexers,
  testServiceConnection,
  updateIndexer,
} from '@/api/config'
import {
  buildNextSiteSettings as buildNextSiteSettingsState,
  computeSiteEffective,
  isMediaTypeToggleDisabled as isMediaTypeToggleDisabledState,
  isSearchToggleDisabled as isSearchToggleDisabledState,
} from '@/composables/useIndexerSiteSettings'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
  applyConfigPatch: {
    type: Function,
    required: true,
  },
})

defineEmits(['save'])
const notification = useNotificationStore()
const { t, locale } = useI18n()
const indexerDialogVisible = ref(false)
const currentIndexer = ref(createEmptyIndexer())
const indexerDialogTitle = ref('')
const indexerDialogMode = ref('add')
const currentTestingIndexer = ref(null)
const testLoading = ref(false)
const healthLoading = ref(false)
const indexerHealth = ref({})
const sitesLoading = ref(false)
const indexerSites = ref({})
const indexerSitesError = ref({})
const siteSettingLoading = ref({})
const siteStatusDialogVisible = ref(false)
const currentDialogIndexerId = ref('')
const currentDialogIndexerName = ref('')
const draggedIndexerId = ref('')
const dragOverIndexerId = ref('')
const indexerTypeOptions = computed(() => [
  { label: t('settings.indexer.jackett'), value: 'jackett' },
  { label: t('settings.indexer.prowlarr'), value: 'prowlarr' },
])

const indexerUrlPlaceholder = computed(() => {
  if (currentIndexer.value.type === 'prowlarr') return 'http://localhost:9696'
  return 'http://localhost:9117'
})

const indexerUrlHelp = computed(() => {
  if (currentIndexer.value.type === 'prowlarr') {
    return t('settings.indexer.prowlarrHelp')
  }
  return t('settings.indexer.jackettHelp')
})

const defaultIndexerUrls = {
  jackett: 'http://localhost:9117',
  prowlarr: 'http://localhost:9696',
}

const currentDialogSites = computed(() => {
  if (!currentDialogIndexerId.value) return []
  return getCombinedSites(currentDialogIndexerId.value)
})

const currentDialogSitesError = computed(
  () => indexerSitesError.value[currentDialogIndexerId.value] || '',
)

const siteStatusDialogTitle = computed(
  () => t('settings.indexer.settingsTitle', { name: currentDialogIndexerName.value }),
)

function createEmptyIndexer() {
  return {
    id: '',
    name: '',
    type: 'jackett',
    enabled: true,
    priority: 0,
    url: '',
    api_key: '',
    min_seeders: 0,
    site_settings: [],
  }
}

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value))
}

function ensureIndexers() {
  return Array.isArray(props.config.indexers) ? props.config.indexers : []
}

function patchIndexers(indexers) {
  props.applyConfigPatch({ indexers })
}

function showSuccess(message) {
  notification.success(message)
}

function showError(message) {
  notification.error(message)
}

function openSiteStatusDialog(indexer) {
  currentDialogIndexerId.value = indexer.id
  currentDialogIndexerName.value = indexer.name || t('settings.indexer.unnamed')
  siteStatusDialogVisible.value = true
  fetchIndexerSites(indexer.id)
  fetchIndexerHealth(indexer.id)
}

function getCombinedSites(indexerId) {
  const sites = indexerSites.value[indexerId] || []
  const healthList = indexerHealth.value[indexerId] || []
  const healthMap = {}

  for (const health of healthList) {
    healthMap[health.site_id] = health
  }

  const combined = sites.map((site) => {
        const health = healthMap[site.site_id]
        if (!health) {
          return {
            ...site,
            status: 'unknown',
            consecutive_failures: 0,
            checked_at: null,
          }
        }

        return {
          ...site,
          ...health,
          site_name: site.site_name || health.site_name || health.site_id,
        }
  })

  combined.sort((a, b) =>
    (a.site_name || a.site_id).localeCompare(b.site_name || b.site_id, locale.value),
  )

  return combined
}

function getStatusLabel(status) {
  if (status === 'healthy') return t('settings.indexer.healthy')
  if (status === 'unhealthy') return t('settings.indexer.unhealthy')
  return t('settings.indexer.unknown')
}

function getStatusTone(status) {
  if (status === 'healthy') return 'success'
  if (status === 'unhealthy') return 'danger'
  return 'neutral'
}

function formatTime(value) {
  if (!value) return t('settings.indexer.noTime')
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return t('settings.indexer.noTime')

  return date.toLocaleString(locale.value, {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function fetchIndexerHealth(indexerId = currentDialogIndexerId.value, options = {}) {
  const { silent = false } = options
  if (!indexerId) {
    indexerHealth.value = {}
    return
  }

  if (!silent) {
    healthLoading.value = true
  }
  try {
    const data = await getIndexerHealth(indexerId)
    const nextHealth = silent ? Object.fromEntries(
      Object.entries(indexerHealth.value).filter(([key]) => key !== indexerId),
    ) : {}
    for (const group of data?.indexers || []) {
      nextHealth[group.indexer_id] = group.sites || []
    }
    indexerHealth.value = nextHealth
  } catch (error) {
    console.error(t('settings.indexer.healthLoadFailed'), error)
    if (!silent) {
      indexerHealth.value = {}
    }
  } finally {
    if (!silent) {
      healthLoading.value = false
    }
  }
}

async function fetchIndexerSites(indexerId = currentDialogIndexerId.value) {
  if (!indexerId) {
    indexerSites.value = {}
    indexerSitesError.value = {}
    return
  }

  sitesLoading.value = true
  try {
    const data = await getIndexerSites(indexerId)
    const nextSites = {}
    const nextErrors = {}
    for (const group of data?.indexers || []) {
      nextSites[group.indexer_id] = group.sites || []
      if (group.error) nextErrors[group.indexer_id] = group.error
    }
    indexerSites.value = nextSites
    indexerSitesError.value = nextErrors
  } catch (error) {
    console.error(t('settings.indexer.sitesLoadFailed'), error)
    indexerSites.value = {}
    indexerSitesError.value = {}
  } finally {
    sitesLoading.value = false
  }
}

function isSiteSettingDisabled(site) {
  return !site.is_live || !!siteSettingLoading.value[site.site_id]
}

function isSearchToggleDisabled(site, mode) {
  return isSearchToggleDisabledState(site, mode, isSiteSettingDisabled(site))
}

function isMediaTypeToggleDisabled(site, mediaType) {
  return isMediaTypeToggleDisabledState(site, mediaType, isSiteSettingDisabled(site))
}

function setSiteSettingLoading(siteId, value) {
  siteSettingLoading.value = {
    ...siteSettingLoading.value,
    [siteId]: value,
  }
}

function patchLocalSiteState(siteId, updater) {
  const indexerId = currentDialogIndexerId.value
  const currentSites = indexerSites.value[indexerId] || []
  const nextSites = currentSites.map((item) => {
    if (item.site_id !== siteId) return item
    return updater(cloneValue(item))
  })
  indexerSites.value = {
    ...indexerSites.value,
    [indexerId]: nextSites,
  }
}

function buildNextSiteSettings(indexer, siteId, updater) {
  return buildNextSiteSettingsState(indexer, siteId, updater, cloneValue)
}

function patchSingleIndexer(nextIndexer) {
  const indexers = cloneValue(ensureIndexers())
  const index = indexers.findIndex((item) => item.id === nextIndexer.id)
  if (index === -1) return
  indexers[index] = nextIndexer
  patchIndexers(indexers)
}

async function persistSiteSetting(site, nextIndexer, nextSettings, successMessage) {
  const previousSite = cloneValue(site)
  patchLocalSiteState(site.site_id, (current) => ({
    ...current,
    settings: nextSettings,
    effective: computeSiteEffective(current, nextSettings),
  }))
  setSiteSettingLoading(site.site_id, true)
  try {
    await updateIndexer(nextIndexer.id, { indexer: nextIndexer })
    patchSingleIndexer(nextIndexer)
    showSuccess(successMessage)
    await fetchIndexerHealth(nextIndexer.id, { silent: true })
  } catch (error) {
    patchLocalSiteState(site.site_id, () => previousSite)
    showError(t('common.settingFailed', { message: error.message }))
  } finally {
    setSiteSettingLoading(site.site_id, false)
  }
}

async function updateSiteSetting(site, key, value) {
  if (isSiteSettingDisabled(site)) return
  const indexer = ensureIndexers().find((item) => item.id === currentDialogIndexerId.value)
  if (!indexer) return
  const nextIndexer = buildNextSiteSettings(indexer, site.site_id, (current) => ({
    ...current,
    [key]: value,
  }))
  const nextSettings = cloneValue(nextIndexer.site_settings.find((item) => item.site_id === site.site_id))
  await persistSiteSetting(site, nextIndexer, nextSettings, value ? t('settings.indexer.siteEnabled') : t('settings.indexer.siteDisabled'))
}

async function updateSearchMode(site, mode, value) {
  if (isSearchToggleDisabled(site, mode)) return
  const indexer = ensureIndexers().find((item) => item.id === currentDialogIndexerId.value)
  if (!indexer) return
  const fieldMap = {
    title: 'disable_title',
    imdb: 'disable_imdb',
    douban: 'disable_douban',
  }
  const field = fieldMap[mode]
  const nextIndexer = buildNextSiteSettings(indexer, site.site_id, (current) => ({
    ...current,
    [field]: !value,
  }))
  const nextSettings = cloneValue(nextIndexer.site_settings.find((item) => item.site_id === site.site_id))
  const labelMap = {
    title: t('settings.indexerSite.title'),
    imdb: t('settings.indexerSite.imdb'),
    douban: t('settings.indexerSite.douban'),
  }
  await persistSiteSetting(site, nextIndexer, nextSettings, value ? t('settings.indexer.searchEnabled', { label: labelMap[mode] }) : t('settings.indexer.searchDisabled', { label: labelMap[mode] }))
}

async function updateMediaType(site, mediaType, value) {
  if (isMediaTypeToggleDisabled(site, mediaType)) return
  const indexer = ensureIndexers().find((item) => item.id === currentDialogIndexerId.value)
  if (!indexer) return
  const currentMediaTypes = new Set([
    ...(site.effective.supports_movie ? ['movie'] : []),
    ...(site.effective.supports_tv ? ['tv'] : []),
  ])
  if (value) {
    currentMediaTypes.add(mediaType)
  } else {
    currentMediaTypes.delete(mediaType)
  }
  const nextMediaTypes = ['movie', 'tv'].filter((item) => currentMediaTypes.has(item))
  const nextIndexer = buildNextSiteSettings(indexer, site.site_id, (current) => ({
    ...current,
    media_types: nextMediaTypes,
  }))
  const nextSettings = cloneValue(nextIndexer.site_settings.find((item) => item.site_id === site.site_id))
  await persistSiteSetting(site, nextIndexer, nextSettings, value ? t('settings.indexer.mediaTypeEnabled') : t('settings.indexer.mediaTypeDisabled'))
}

function normalizeIndexerPriorities(indexers) {
  const total = indexers.length
  return indexers.map((indexer, index) => ({
    ...indexer,
    priority: total - index,
  }))
}

async function persistIndexers(indexers, successMessage) {
  const normalizedIndexers = normalizeIndexerPriorities(indexers)
  await reorderIndexers({ indexers: normalizedIndexers })
  patchIndexers(normalizedIndexers)
  showSuccess(successMessage)
  await fetchIndexerHealth()
  await fetchIndexerSites()
}

function addIndexer() {
  indexerDialogVisible.value = true
  indexerDialogTitle.value = t('settings.indexer.addTitle')
  indexerDialogMode.value = 'add'
  currentIndexer.value = {
    ...createEmptyIndexer(),
    id: `indexer_${Date.now()}`,
    name: t('settings.indexer.newJackett'),
    url: 'http://localhost:9117',
  }
}

function handleIndexerTypeChange(type) {
  if (indexerDialogMode.value !== 'add') return
  const currentUrl = currentIndexer.value.url || ''
  const shouldUseDefaultUrl = !currentUrl || Object.values(defaultIndexerUrls).includes(currentUrl)
  if (type === 'prowlarr') {
    currentIndexer.value.name = t('settings.indexer.newProwlarr')
    if (shouldUseDefaultUrl) {
      currentIndexer.value.url = defaultIndexerUrls.prowlarr
    }
    return
  }
  currentIndexer.value.name = t('settings.indexer.newJackett')
  if (shouldUseDefaultUrl) {
    currentIndexer.value.url = defaultIndexerUrls.jackett
  }
}

function editIndexer(indexer) {
  indexerDialogVisible.value = true
  indexerDialogTitle.value = t('settings.indexer.editTitle')
  indexerDialogMode.value = 'edit'
  currentIndexer.value = cloneValue(indexer)
}

async function saveIndexer() {
  const currentIndexers = cloneValue(ensureIndexers())

  if (indexerDialogMode.value === 'add') {
    currentIndexer.value.priority = currentIndexers.length + 1
  } else {
    currentIndexer.value.priority = currentIndexer.value.priority || 0
  }

  try {
    let nextIndexers = currentIndexers
    if (indexerDialogMode.value === 'add') {
      await createIndexer({ indexer: currentIndexer.value })
      nextIndexers = [...currentIndexers, cloneValue(currentIndexer.value)]
    } else {
      await updateIndexer(currentIndexer.value.id, { indexer: currentIndexer.value })
      const index = currentIndexers.findIndex((item) => item.id === currentIndexer.value.id)
      if (index !== -1) {
        nextIndexers = [...currentIndexers]
        nextIndexers[index] = cloneValue(currentIndexer.value)
      }
    }

    patchIndexers(nextIndexers)
    indexerDialogVisible.value = false
    showSuccess(indexerDialogMode.value === 'add' ? t('settings.indexer.added') : t('settings.indexer.updated'))
    await fetchIndexerHealth()
    await fetchIndexerSites()
  } catch (error) {
    showError(t('common.saveFailed', { message: error.message }))
  }
}

async function removeIndexer(id) {
  const indexers = ensureIndexers()
  const index = indexers.findIndex((item) => item.id === id)
  if (index === -1) return

  try {
    await deleteIndexer(id)
    patchIndexers(indexers.filter((item) => item.id !== id))
    showSuccess(t('settings.indexer.deleted'))
    await fetchIndexerHealth()
    await fetchIndexerSites()
  } catch (error) {
    showError(t('common.deleteFailed', { message: error.message }))
  }
}

async function reorderIndexerEntries(fromIndex, toIndex) {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return

  const reordered = [...ensureIndexers()]
  const [moved] = reordered.splice(fromIndex, 1)
  reordered.splice(toIndex, 0, moved)

  try {
    await persistIndexers(reordered, t('settings.indexer.orderUpdated'))
  } catch (error) {
    showError(t('settings.indexer.sortFailed', { message: error.message }))
  }
}

function handleDragStart(indexerId) {
  draggedIndexerId.value = indexerId
  dragOverIndexerId.value = ''
}

function handleDragOver(indexerId) {
  if (!draggedIndexerId.value || draggedIndexerId.value === indexerId) return
  dragOverIndexerId.value = indexerId
}

async function handleDrop(targetIndex) {
  const fromIndex = ensureIndexers().findIndex((item) => item.id === draggedIndexerId.value)
  dragOverIndexerId.value = ''
  if (fromIndex === -1) {
    draggedIndexerId.value = ''
    return
  }

  const activeDraggedIndexerId = draggedIndexerId.value
  draggedIndexerId.value = ''
  if (ensureIndexers()[targetIndex]?.id === activeDraggedIndexerId) return
  await reorderIndexerEntries(fromIndex, targetIndex)
}

function handleDragEnd() {
  draggedIndexerId.value = ''
  dragOverIndexerId.value = ''
}

async function testIndexerConnection(indexer) {
  testLoading.value = true
  currentTestingIndexer.value = indexer.id

  try {
    await testServiceConnection({
      type: indexer.type,
      config: {
        url: indexer.url,
        api_key: indexer.api_key,
      },
    })
    showSuccess(t('common.connectionSuccess'))
  } catch (error) {
    showError(t('common.networkError', { message: error.message || error }))
  } finally {
    testLoading.value = false
    currentTestingIndexer.value = null
  }
}

async function toggleIndexerEnabled(indexer) {
  const indexers = cloneValue(ensureIndexers())
  const index = indexers.findIndex((item) => item.id === indexer.id)
  if (index === -1) return

  const nextEnabled = !indexers[index].enabled
  indexers[index].enabled = nextEnabled

  try {
    await updateIndexer(indexer.id, {
      indexer: indexers[index],
    })
    patchIndexers(indexers)
    showSuccess(nextEnabled ? t('settings.indexer.enabled') : t('settings.indexer.disabled'))
    await fetchIndexerHealth()
    await fetchIndexerSites()
  } catch (error) {
    showError(t('common.settingFailed', { message: error.message }))
  }
}

defineExpose({
  addIndexer,
  editIndexer,
  removeIndexer,
})
</script>
