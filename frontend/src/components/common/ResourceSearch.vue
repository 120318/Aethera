<template>
  <div class="flex flex-col gap-container">
    <!-- 2. Filter & Stats & Resource List -->
    <div v-if="shouldShowResultsCard || searchState.loading" class="flex flex-col gap-container">
      <div v-if="searchState.loading && searchResults.length === 0" class="ui-tab-empty">
        <i class="pi pi-spinner pi-spin text-display mb-item opacity-50"></i>
        <p class="text-title font-medium">{{ searchState.loadingText || $t('resourceSearch.loading') }}</p>
        <p class="text-caption text-muted">{{ $t('resourceSearch.autoRefreshHint') }}</p>
      </div>

      <!-- Empty State (No Results) -->
      <div
        v-if="searchResults.length === 0 && !searchState.loading"
        class="ui-tab-empty"
      >
        <p class="text-title font-medium mb-item">{{ $t('resourceSearch.noResults') }}</p>
        <p class="text-caption text-muted">{{ $t('resourceSearch.adjustFilters') }}</p>
      </div>

      <div v-if="searchResults.length > 0" class="flex flex-col gap-item">
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-item">
          <Dropdown
            v-if="filterPresets.length > 0" v-model="selectedFilterPreset" :options="filterPresets"
            option-label="name" option-value="id" :placeholder="$t('resourceSearch.quickFilter')" class="w-full" show-clear
            @change="applyFilterPreset"
          />

          <InputText v-model="localFilters.keyword" :placeholder="$t('resourceSearch.keywordFilter')" class="w-full" />

          <Select
            v-model="localFilters.matchState" :options="imdbMatchOptions" option-label="label" option-value="value"
            :placeholder="$t('resourceSearch.matchState')" show-clear class="w-full"
          />

          <MultiSelect
            v-model="localFilters.sites" :options="availableSiteOptions" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.site')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.resolutions" :options="toOptions(availableResolutions)" filter
            option-label="label" option-value="value" :placeholder="$t('resourceSearch.resolution')" display="chip" class="w-full"
            :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.seasons" :options="toOptions(availableSeasons)" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.seasons')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.episodes" :options="availableEpisodeOptions" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.episodes')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.groups" :options="toOptions(availableGroups)" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.groups')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.sources" :options="toOptions(availableSources)" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.source')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.resourceForms" :options="toOptions(availableResourceForms)" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.resourceForm')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.hdrTypes" :options="toOptions(availableHdrTypes)" option-label="label" filter
            option-value="value" :placeholder="$t('subscription.hdrType')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <MultiSelect
            v-model="localFilters.tags" :options="toOptions(availableTags)" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.tags')" display="chip" class="w-full" :max-selected-labels="1"
          />

          <Select
            v-model="localFilters.sizeRange" :options="sizeOptions" option-label="label" option-value="value"
            :placeholder="$t('resourceSearch.size')" show-clear class="w-full"
          />

          <Select
            v-model="localFilters.seeders" :options="seederOptions" option-label="label" option-value="value"
            :placeholder="$t('resourceSearch.seeders')" show-clear class="w-full"
          />

          <MultiSelect
            v-model="localFilters.promotions" :options="promotionOptions" option-label="label" filter
            option-value="value" :placeholder="$t('resourceSearch.promotion')" display="chip" class="w-full" :max-selected-labels="1"
          />
        </div>
      </div>

      <!-- DataView with Results -->
      <DataView
        v-if="searchResults.length > 0" :value="filteredResults" paginator :rows="10" layout="list" paginator-position="both"
        class="overflow-hidden ui-dataview-balanced-paginator"
        :class="{ 'border border-separator rounded-border': !embedded }"
        :pt="dataViewPt"
      >
        <template #paginatorstart>
          <div class="hidden md:flex items-center text-muted">
            {{ $t('resourceSearch.foundPrefix') }} <span class="text-primary mx-inline">{{ searchResults.length }}</span> {{ $t('resourceSearch.foundSuffix') }}
            <span
              v-if="searchDurationSeconds !== null"
              class="text-muted ml-inline"
            >
              {{ $t('resourceSearch.searchDuration', { time: formatSearchDuration(searchDurationSeconds) }) }}
            </span>
            <span
              v-if="filteredResults.length !== searchResults.length"
              class="text-muted ml-inline"
            >
              {{ $t('resourceSearch.filteredCount', { count: filteredResults.length }) }}
            </span>
          </div>
        </template>

        <template #paginatorend>
          <div class="flex items-center gap-item">
            <Button
              v-if="hasActiveFilters" severity="secondary" :label="$t('resourceSearch.clearFilters')" icon="pi pi-filter-slash" link
              size="small" :disabled="searchState.loading" @click="handleClearFilters"
            />
            <SortControl v-model="sortModel" :options="sortOptions" />
          </div>
        </template>

        <template #list="slotProps">
          <ResourceCard
            v-for="(resource, index) in slotProps.items"
            :key="(resource.id || 'no-id') + '_' + (resource.resource?.id || 'no-resid') + '_' + index"
            :resource="resource" :is-downloading="torrenting.has(resource.resource?.id)"
            @download="handleDownloadClick"
          />
        </template>

        <template #empty>
          <div class="ui-tab-empty">
            <p class="text-title font-medium mb-item">{{ $t('resourceSearch.noResults') }}</p>
            <p class="text-caption text-muted">{{ $t('resourceSearch.adjustFilters') }}</p>
          </div>
        </template>
      </DataView>
    </div>
  </div>

  <!-- Filter dialog -->
  <ResourceSearchFilterDialog
    v-model:visible="filterDialogVisible" :loading="searchState.loading"
    :has-searched="hasSearched" :always-show-results="alwaysShowResults" :local-search-state="localSearchState"
    :search-state="searchState" :filter-form="filterForm" :site-options="siteOptions"
    :available-resolutions="availableResolutions" :available-seasons="availableSeasons"
    :available-episodes="availableEpisodes" :available-groups="availableGroups" :available-sources="availableSources"
    :available-resource-forms="availableResourceForms"
    :size-options="sizeOptions" :seeder-options="seederOptions" :show-media-id-input="showMediaIdInput"
    :show-site-input="showSiteInput" :disable-media-id-input="disableMediaIdInput"
    :disable-site-input="disableSiteInput" @confirm="handleDialogConfirm"
  />

  <!-- Download dialog -->
  <DownloadDialog
    v-model:visible="downloadDialogVisible" :resource-data="selectedResourceForDownload || {}"
    :media-info="mediaInfo" @download="handleDownloadConfirm"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import DataView from 'primevue/dataview'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'

import DownloadDialog from './DownloadDialog.vue'
import ResourceCard from './ResourceCard.vue'
import ResourceSearchFilterDialog from './ResourceSearchFilterDialog.vue'
import SortControl from './filter/SortControl.vue'
import { useResourceSearchLifecycle } from '@/composables/useResourceSearchLifecycle'
import { useResourceSearchPanel } from '@/composables/useResourceSearchPanel'
import { useResourceSearchUi } from '@/composables/useResourceSearchUi'
import { useResourceSearch } from '../../composables/useResourceSearch.js'
import { useSiteDisplay } from '@/composables/useSiteDisplay'
import { useOperationsStore } from '@/stores/operations'

// Helper for string arrays.
const toOptions = (arr) => arr.map(item => ({ label: item, value: item }))

const props = defineProps({
  embedded: {
    type: Boolean,
    default: false
  },
  mediaId: {
    type: String,
    default: ''
  },
  keyword: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: ''
  },
  showMediaIdInput: {
    type: Boolean,
    default: true
  },
  showKeywordInput: {
    type: Boolean,
    default: true
  },
  showSiteInput: {
    type: Boolean,
    default: true
  },
  showMediaTypeInput: {
    type: Boolean,
    default: true
  },
  disableMediaIdInput: {
    type: Boolean,
    default: false
  },
  disableKeywordInput: {
    type: Boolean,
    default: false
  },
  disableMediaTypeInput: {
    type: Boolean,
    default: false
  },
  disableSiteInput: {
    type: Boolean,
    default: false
  },
  hideSearchForm: {
    type: Boolean,
    default: false
  },
  alwaysShowResults: {
    type: Boolean,
    default: false
  },
  enableEmbeddedSearch: {
    type: Boolean,
    default: true
  },
  autoSearch: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  year: {
    type: [String, Number],
    default: ''
  },
  seasonNumber: {
    type: Number,
    default: null,
  },
  imdbId: {
    type: String,
    default: '',
  },
  doubanId: {
    type: String,
    default: '',
  },
  tmdbId: {
    type: [String, Number],
    default: null,
  },
  seasonsCount: {
    type: [String, Number],
    default: null,
  },
  episodesCount: {
    type: [String, Number],
    default: null,
  },
  airedEpisodeCount: {
    type: [String, Number],
    default: null,
  },
  initialResults: {
    type: Array,
    default: null
  },
  hasSearched: {
    type: Boolean,
    default: false
  },
  searchTrigger: {
    type: Number,
    default: 0
  },
  searchResultsRefreshTrigger: {
    type: Number,
    default: 0
  },
  isActive: {
    type: Boolean,
    default: true
  },
  activeCommand: {
    type: Object,
    default: null
  },
  catalogs: {
    type: Object,
    default: null,
  }
})

const emit = defineEmits(['download', 'search', 'search-complete', 'search-loading', 'command-submitted'])

const operations = useOperationsStore()
const { ensureSiteDisplayLoaded } = useSiteDisplay()
const sitesLoadedForPanel = ref(false)

const {
  searchState,
  searchResults,
  torrenting,
  mediaInfo,
  localFilters,
  sortState,
  hasSearched,
  searchDurationSeconds,
  availableSiteEntries,
  availableGroups,
  availableHdrTypes,
  availableTags,
  availableResolutions,
  availableSources,
  availableResourceForms,
  availableSeasons,
  availableEpisodes,
  availableEpisodeOptions,
  hasActiveFilters,
  filteredResults,
  performSearch,
  loadSearchResults,
  addTorrent,
  siteOptions,
  fetchAvailableSites,
  clearAllFilters,
  setSearchResults,
  clearSearchResults
} = useResourceSearch({
  externalCommand: computed(() => props.activeCommand || null),
  siteCatalog: computed(() => props.catalogs?.sites || []),
  mediaType: computed(() => props.type || ''),
  seasonNumber: computed(() => props.seasonNumber || null),
  title: computed(() => props.title || ''),
  year: computed(() => props.year || null),
  imdbId: computed(() => props.imdbId || ''),
  doubanId: computed(() => props.doubanId || ''),
  tmdbId: computed(() => props.tmdbId || null),
  seasonsCount: computed(() => props.seasonsCount || null),
  episodesCount: computed(() => props.episodesCount || null),
  airedEpisodeCount: computed(() => props.airedEpisodeCount || null),
})

function formatSearchDuration(value) {
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds < 0) return '-'
  if (seconds < 10) return seconds.toFixed(1)
  return String(Math.round(seconds))
}

searchState.media_id = props.mediaId

watch(() => props.mediaId, (value) => {
  searchState.media_id = value
})

const {
  sizeOptions,
  seederOptions,
  promotionOptions,
  imdbMatchOptions,
  sortOptions,
  filterDialogVisible,
  downloadDialogVisible,
  selectedResourceForDownload,
  filterPresets,
  selectedFilterPreset,
  localSearchState,
  sortModel,
  shouldShowResultsCard,
  fetchFilterPresets,
  applyFilterPreset,
  handleDialogConfirm,
  handleClearFilters,
  handleDownloadClick,
  handleDownloadConfirm,
} = useResourceSearchUi({
  props,
  emit,
  searchState,
  localFilters,
  sortState,
  hasSearched,
  searchResults,
  mediaInfo,
  siteOptions,
  clearAllFilters,
  addTorrent,
  filterCatalog: computed(() => props.catalogs?.filters || []),
})

const availableSiteOptions = computed(() => {
  return availableSiteEntries.value
})

const { filtersLoaded } = useResourceSearchLifecycle({
  props,
  emit,
  operations,
  searchState,
  searchResults,
  performSearch,
  loadSearchResults,
  setSearchResults,
  clearSearchResults,
})
const { dataViewPt } = useResourceSearchPanel({
  props,
  emit,
  searchState,
  searchResults,
  localSearchState,
  localFilters,
  siteOptions,
  sizeOptions,
  seederOptions,
  promotionOptions,
  filtersLoaded,
  fetchFilterPresets,
  performSearch,
})

async function ensurePanelSitesLoaded() {
  if (sitesLoadedForPanel.value) return
  sitesLoadedForPanel.value = true
  if (!Array.isArray(props.catalogs?.sites) || props.catalogs.sites.length === 0) {
    await fetchAvailableSites()
  }
  await ensureSiteDisplayLoaded(props.catalogs?.sites || null)
}

watch(
  () => props.isActive,
  (active) => {
    if (active) void ensurePanelSitesLoaded()
  },
  { immediate: true },
)

const filterForm = localFilters
</script>
