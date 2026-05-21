<template>
  <section class="w-full max-w-layout mx-auto flex flex-col gap-block">
    <div class="ui-page-header">
      <div class="flex flex-col gap-item">
        <h1 class="text-heading font-semibold">{{ $t('mediaManagement.title') }}</h1>
        <p class="text-muted text-caption">{{ $t('mediaManagement.description') }}</p>
      </div>
    </div>

    <AppTabs v-model="activeTab" :tabs="managementTabs" content-body-class="media-management-tab-body">
      <section v-if="activeTab === 'media'" class="flex flex-col gap-item">
        <div v-if="summaryLoading" class="summary-grid">
          <div v-for="index in summarySkeletonCount" :key="index" class="ui-panel summary-card p-container flex flex-col gap-item">
            <div class="h-7 flex items-center">
              <Skeleton width="56%" height="var(--text-title)" />
            </div>
            <Skeleton width="40%" height="var(--text-hero)" />
          </div>
        </div>

        <div v-else class="summary-grid">
          <div
            v-for="card in summaryCards"
            :key="card.key"
            class="ui-panel summary-card p-container flex flex-col gap-item"
          >
            <div class="text-title font-bold h-7 flex items-center">{{ card.label }}</div>
            <div :class="['text-hero font-semibold', card.valueClass]">{{ card.value }}</div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-item">
          <InputText v-model="filters.query" :placeholder="$t('mediaManagement.filters.searchPlaceholder')" class="w-full" />
          <Select
            v-model="filters.mediaType"
            :options="mediaTypeOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('mediaManagement.filters.mediaType')"
            class="w-full"
          />
          <MultiSelect
            v-model="filters.statuses"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            :placeholder="$t('mediaManagement.filters.status')"
            display="chip"
            :max-selected-labels="2"
            class="w-full"
          />
        </div>

        <div v-if="loading" class="flex flex-col">
          <div v-for="index in 6" :key="index" class="list-skeleton-row flex flex-col gap-item py-item border-b border-separator last:border-0">
            <div class="flex flex-col sm:flex-row items-start sm:items-stretch gap-item min-w-0">
              <div class="min-w-0 flex flex-col gap-inline flex-1">
                <div class="h-6 flex items-center">
                  <Skeleton width="64%" height="var(--text-body)" />
                </div>
                <div class="flex flex-wrap items-center gap-inline min-w-0">
                  <Skeleton width="14%" height="var(--size-placeholder-tiny)" />
                  <Skeleton width="18%" height="var(--size-placeholder-tiny)" />
                  <Skeleton width="22%" height="var(--size-placeholder-tiny)" />
                </div>
              </div>

              <div class="media-management-skeleton-side flex w-full sm:w-auto sm:self-stretch flex-col items-end justify-end gap-inline shrink-0">
                <Skeleton width="48%" height="var(--text-caption)" />
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="items.length === 0" class="ui-tab-empty">
          <p class="text-title font-medium mb-item">{{ $t('mediaManagement.empty.title') }}</p>
          <p class="text-caption text-muted">{{ $t('mediaManagement.empty.description') }}</p>
        </div>

        <DataView
          v-else
          lazy
          :value="items"
          paginator
          :first="first"
          :rows="rows"
          :total-records="total"
          layout="list"
          paginator-position="both"
          class="overflow-hidden ui-dataview-balanced-paginator"
          @page="onPage"
        >
          <template #paginatorstart>
            <div class="hidden md:flex items-center text-muted">
              {{ $t('mediaManagement.pagination.totalPrefix') }}
              <span class="text-primary mx-inline">{{ total }}</span>
              {{ $t('mediaManagement.pagination.totalSuffix') }}
            </div>
          </template>

          <template #paginatorend>
            <div class="flex items-center gap-item">
              <span class="text-caption text-muted">{{ $t('mediaManagement.sort.label') }}</span>
              <Select
                v-model="filters.sort"
                :options="sortOptions"
                option-label="label"
                option-value="value"
                :placeholder="$t('mediaManagement.sort.label')"
                class="w-form-md"
              />
            </div>
          </template>

          <template #list="slotProps">
            <MediaManagementCard
              v-for="item in slotProps.items"
              :key="getItemKey(item)"
              :item="item"
              :action-loading="getItemActionLoading(item)"
              :delete-pending="isDeletePending(item)"
              @toggle-follow="handleQuickToggleFollow"
              @toggle-subscription="handleQuickToggleSubscription"
              @delete-files="handleQuickDeleteFiles"
            />
          </template>

          <template #empty>
            <div class="ui-tab-empty">
              <p class="text-title font-medium mb-item">{{ $t('mediaManagement.empty.title') }}</p>
              <p class="text-caption text-muted">{{ $t('mediaManagement.empty.description') }}</p>
            </div>
          </template>
        </DataView>
      </section>

      <section v-else-if="activeTab === 'directories'" class="flex flex-col gap-item">
        <DirectoryIntegrityTab
          v-model:result="directoryIntegrityResult"
          :loading="directoryIntegrityLoading"
        />
      </section>
    </AppTabs>

    <ConfirmDialog />
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import ConfirmDialog from 'primevue/confirmdialog'
import DataView from 'primevue/dataview'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Skeleton from 'primevue/skeleton'
import AppTabs from '@/components/common/AppTabs.vue'
import MediaManagementCard from '@/components/media-management/MediaManagementCard.vue'
import { useMediaManagementPage } from '@/composables/useMediaManagementPage'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const DirectoryIntegrityTab = defineAsyncComponent(() => import('@/components/media-management/DirectoryIntegrityTab.vue'))
const TAB_TO_HASH = {
  media: '#media',
  directories: '#directories',
}
const HASH_TO_TAB = Object.fromEntries(Object.entries(TAB_TO_HASH).map(([tab, hash]) => [hash, tab]))

function hashToTab(hash) {
  return HASH_TO_TAB[hash] || 'media'
}

const activeTab = ref(hashToTab(route.hash))
const managementTabs = computed(() => [
  { label: t('mediaManagement.tabs.mediaList'), value: 'media' },
  { label: t('mediaManagement.tabs.directoryList'), value: 'directories' },
])

const {
  loading,
  summaryLoading,
  directoryIntegrityResult,
  directoryIntegrityLoading,
  items,
  filters,
  total,
  first,
  rows,
  onPage,
  summaryCards,
  mediaTypeOptions,
  statusOptions,
  sortOptions,
  getItemActionLoading,
  getItemKey,
  isDeletePending,
  handleQuickToggleFollow,
  handleQuickToggleSubscription,
  handleQuickDeleteFiles,
  loadMediaTab,
  loadDirectoryIntegrityTab,
} = useMediaManagementPage()

const summarySkeletonCount = computed(() => summaryCards.value.length || 6)

watch(
  () => route.hash,
  (nextHash) => {
    const nextTab = hashToTab(nextHash)
    if (activeTab.value !== nextTab) {
      activeTab.value = nextTab
    }
  },
)

watch(
  activeTab,
  (nextTab) => {
    const desiredHash = TAB_TO_HASH[nextTab] || TAB_TO_HASH.media
    if (route.hash !== desiredHash) {
      router.replace({
        path: route.path,
        query: route.query,
        hash: desiredHash,
      })
    }
    void loadActiveTab(nextTab)
  },
  { immediate: true },
)

function loadActiveTab(tab) {
  if (tab === 'directories') {
    return loadDirectoryIntegrityTab()
  }
  return loadMediaTab()
}

onMounted(() => {
  if (route.hash) return
  router.replace({
    path: route.path,
    query: route.query,
    hash: TAB_TO_HASH[activeTab.value] || TAB_TO_HASH.media,
  })
})
</script>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-item);
}

@media (min-width: 1024px) {
  .summary-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}

.summary-card {
  min-height: var(--size-placeholder-summary);
}

.list-skeleton-row {
  border-radius: 0;
}

:deep(.media-management-tab-body) {
  padding: var(--spacing-container);
}
</style>
