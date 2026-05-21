<template>
  <AppTabs
    :model-value="activeTab"
    :tabs="tabOptions"
    fit-mobile
    content-body-class="media-detail-tab-body"
    @update:model-value="onTabChange"
  >
    <!-- Local resources. -->
    <div v-if="activeTab === 'resources'">
      <LocalResourcesTab
        :media-id="mediaId" :detail="detail" :overview="overview" :overview-loading="overviewLoading"
        :resources="resources" :total-episodes="resourcesTotalEpisodes" :tasks="tasks" :loading="!dataLoaded.resources"
        :detail-loading="detailLoading"
        :season-number="seasonNumber"
        :operation-commands="operationCommands"
        @view-details="$emit('view-details', $event)" @delete="$emit('delete', $event)"
        @command-submitted="$emit('command-submitted', $event)"
      />
    </div>

    <!-- Download tasks. -->
    <div v-else-if="activeTab === 'tasks'" class="animate-fadein">
      <div class="flex flex-col gap-block w-full">
        <div v-if="!dataLoaded.tasks && !taskCreatePending" class="loading-state flex flex-col gap-block">
          <Skeleton height="6rem" class="w-full" />
          <Skeleton height="6rem" class="w-full" />
          <Skeleton height="6rem" class="w-full" />
        </div>
        <div v-else-if="displayTasks.length === 0" class="ui-tab-empty">
          <p class="text-title font-medium mb-item">{{ $t('mediaDetail.noDownloadTasks') }}</p>
          <p class="text-caption text-muted">{{ $t('mediaDetail.noActiveDownloadTasks') }}</p>
        </div>
        <div v-else class="flex flex-col gap-block">
          <TaskLiveStatus
            :tasks="displayTasks" :active-tab="activeTab" :operation-commands="operationCommands"
            :operation-realtime-overrides="taskRealtimeOverrides"
            :media-id="eventMediaId"
            :media-type="detail?.media_type || detail?.type || ''"
            @command-submitted="$emit('command-submitted', $event)"
            @task-updated="$emit('task-updated')"
            @task-view-updated="$emit('task-view-updated', $event)"
          />
        </div>
      </div>
    </div>

    <!-- Search results. -->
    <div v-if="shouldMountSearchPanel" v-show="activeTab === 'search'" class="animate-fadein">
      <div class="animate-fadein">
        <ResourceSearch
          :key="`${eventMediaId || 'media'}:${seasonNumber || ''}`"
          :media-id="eventMediaId" :keyword="detail?.title || ''" :type="detail?.type"
          :season-number="seasonNumber"
          :imdb-id="detail?.imdb_id || ''" :douban-id="detail?.douban_id || ''" :tmdb-id="detail?.tmdb_id || null"
          :seasons-count="detail?.seasons_count || null" :episodes-count="detail?.episodes_count || null"
          :aired-episode-count="detail?.aired_episode_count || null"
          :title="detail?.title || ''" :year="detail?.year" :hide-search-form="true"
          :always-show-results="true" :enable-embedded-search="true" :auto-search="false"
          :initial-results="searchResults" :has-searched="hasSearched" :search-trigger="searchTrigger"
          :search-results-refresh-trigger="searchResultsRefreshTrigger" :embedded="true"
          :is-active="activeTab === 'search'" :active-command="searchCommand" :catalogs="catalogs"
          @download="$emit('search-download', $event)" @search="$emit('search', $event)"
          @search-complete="$emit('search-complete', $event)" @search-loading="$emit('search-loading', $event)"
          @command-submitted="$emit('command-submitted', $event)"
        />
      </div>
    </div>

    <div v-if="activeTab === 'events' || eventTabMounted" v-show="activeTab === 'events'" class="animate-fadein">
      <EventList
        :key="`${eventMediaId || 'no-media'}:${seasonNumber || ''}`"
        :media-id="eventMediaId"
        :season-number="seasonNumber"
        :show-filters="true"
        :refresh-key="eventRefreshKey"
      />
    </div>
  </AppTabs>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Skeleton from 'primevue/skeleton'
import AppTabs from '@/components/common/AppTabs.vue'
import ResourceSearch from './common/ResourceSearch.vue'
import TaskLiveStatus from './TaskLiveStatus.vue'
import LocalResourcesTab from './LocalResourcesTab.vue'
import EventList from './EventList.vue'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  mediaId: {
    type: String,
    default: null
  },
  detail: {
    type: Object,
    default: () => ({})
  },
  detailLoading: {
    type: Boolean,
    default: false
  },
  overview: {
    type: Object,
    default: null
  },
  overviewLoading: {
    type: Boolean,
    default: false
  },
  resources: {
    type: Array,
    default: () => []
  },
  resourcesTotalEpisodes: {
    type: Number,
    default: 0
  },
  tasks: {
    type: Array,
    default: () => []
  },
  taskCreatePending: {
    type: Boolean,
    default: false
  },
  taskCreatePlaceholderVisible: {
    type: Boolean,
    default: false
  },
  pendingTaskPreview: {
    type: Object,
    default: null
  },
  taskRealtimeOverrides: {
    type: Object,
    default: () => ({})
  },
  operationCommands: {
    type: Array,
    default: null
  },
  searchCommand: {
    type: Object,
    default: null
  },
  dataLoaded: {
    type: Object,
    default: () => ({
      resources: false,
      tasks: false,
      search: false
    })
  },
  activeTab: {
    type: String,
    default: 'resources'
  },
  searchResults: {
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
  seasonNumber: {
    type: Number,
    default: null
  },
  catalogs: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits([
  'update:activeTab',
  'view-details',
  'move-files',
  'delete',
  'search-download',
  'search',
  'search-complete',
  'search-loading',
  'command-submitted',
  'task-updated',
  'task-view-updated',
])

function normalizeMediaId(v) {
  if (!v) return null
  if (typeof v === 'string') return v
  if (typeof v === 'object') {
    if (typeof v.media_id === 'string') return v.media_id
    const provider = v.provider?.value || v.provider
    const mediaType = v.media_type?.value || v.media_type || v.mediaType
    const id = v.id
    if (provider && mediaType && id) {
      return `${provider}:${mediaType}:${id}`
    }
  }
  // Fallback: avoid silently querying "all events" without media context.
  const s = String(v)
  return s && s !== '[object Object]' ? s : null
}

const normalizedMediaId = computed(() => normalizeMediaId(props.detail?.media_id || props.detail?.id))
const eventMediaId = computed(() => props.mediaId || normalizedMediaId.value)
const eventTabMounted = ref(false)
const eventRefreshKey = ref(0)
const hasSearchResults = computed(() => Array.isArray(props.searchResults) && props.searchResults.length > 0)
const hasActiveSearchCommand = computed(() => (
  props.searchCommand?.status === 'queued' || props.searchCommand?.status === 'running'
))
const searchTabVisibilitySignal = computed(() => (
  props.hasSearched || hasSearchResults.value || hasActiveSearchCommand.value || props.searchTrigger > 0 || props.activeTab === 'search'
))
const searchTabEverVisible = ref(false)
const shouldMountSearchPanel = computed(() => searchTabVisibilitySignal.value || searchTabEverVisible.value)
const displayTasks = computed(() => {
  if (!props.taskCreatePlaceholderVisible) return props.tasks
  const preview = props.pendingTaskPreview || {}
  const placeholder = {
    id: '__task_create_pending__',
    title: preview.title || t('taskLive.creatingDownloadTask'),
    description: preview.description || '',
    size: Number(preview.size || 0),
    status: 'pending',
    state: 'pending',
    progress: 0,
    added_on: Date.now(),
    attributes: preview.attributes || {},
    task_data: {
      id: '__task_create_pending__',
      context: {
        search_result: {
          site: preview.site || '',
        },
      },
      download_client: '',
      download_client_url: '',
    },
    _taskCreatePlaceholder: true,
  }
  return [placeholder, ...props.tasks]
})

const tabOptions = computed(() => {
  const tabs = [
    {
      label: t('mediaDetail.tabs.localResources'),
      value: 'resources'
    },
    {
      label: t('mediaDetail.tabs.downloadTasks'),
      value: 'tasks'
    },
    {
      label: t('mediaDetail.tabs.searchResults'),
      value: 'search'
    },
    {
      label: t('mediaDetail.tabs.eventLogs'),
      value: 'events'
    }
  ]

  return tabs
})

function onTabChange(newVal) {
  emit('update:activeTab', newVal)
}

// Hash-based tab routing
const hashToTab = (hash) => {
  if (!hash) return null
  const h = hash.replace(/^#/, '')
  if (h === 'resources' || h === 'tasks' || h === 'search' || h === 'events') return h
  return null
}

const syncTabFromHash = () => {
  const tab = hashToTab(window.location.hash || route.hash)
  if (tab && tab !== props.activeTab) {
    emit('update:activeTab', tab)
  }
}

watch(
  () => props.activeTab,
  (newVal) => {
    if (newVal === 'events') {
      eventTabMounted.value = true
      eventRefreshKey.value += 1
    }
    const currentHash = route.hash || window.location.hash
    const desired = `#${newVal}`
    if (currentHash !== desired) {
      router.replace({
        hash: desired,
        query: route.query,
      })
    }
  }
)

watch(
  searchTabVisibilitySignal,
  (visible) => {
    if (visible) {
      searchTabEverVisible.value = true
    }
  },
  { immediate: true }
)

watch(
  eventMediaId,
  () => {
    searchTabEverVisible.value = searchTabVisibilitySignal.value
  }
)

onMounted(() => {
  syncTabFromHash()
  if (props.activeTab === 'events') {
    eventTabMounted.value = true
  }
  window.addEventListener('hashchange', syncTabFromHash)
})
</script>

<style scoped>
:deep(.media-detail-tab-body) {
  padding-block: var(--spacing-item);
}
</style>
