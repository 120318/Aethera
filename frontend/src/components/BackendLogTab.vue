<template>
  <div class="flex flex-col gap-item w-full min-h-tab-content">
    <div class="flex flex-col gap-item">
      <div class="flex flex-col lg:flex-row gap-item">
        <div class="w-full lg:flex-1">
          <InputText
            v-model="keyword"
            :placeholder="$t('backendLogs.filterPlaceholder')"
            class="w-full"
          />
        </div>
        <div class="w-full lg:w-48">
          <Select
            v-model="selectedLevel"
            :options="levelOptions"
            option-label="label"
            option-value="value"
            class="w-full"
          />
        </div>
      </div>

      <div class="flex flex-col lg:flex-row lg:items-center gap-item lg:gap-container">
        <div class="flex flex-wrap items-center gap-item text-caption text-muted min-w-0">
          <span>{{ autoRefreshEnabled ? $t('backendLogs.autoRefreshEnabled') : $t('backendLogs.autoRefreshPaused') }}</span>
          <span>{{ $t('backendLogs.visibleLines', { count: filteredLineCount }) }}</span>
          <span v-if="lastRefreshedAt">{{ $t('backendLogs.lastRefreshed', { time: formatAbsoluteDateTime(lastRefreshedAt) }) }}</span>
          <span v-if="sourceFile" class="font-mono break-all">{{ sourceFile }}</span>
        </div>

        <div class="flex flex-wrap items-center gap-item lg:ml-auto">
          <Button
            :label="autoRefreshEnabled ? $t('backendLogs.pauseRefresh') : $t('backendLogs.resumeRefresh')"
            severity="secondary"
            variant="text"
            size="small"
            @click="toggleAutoRefresh"
          />
          <Button
            :label="$t('backendLogs.refreshNow')"
            severity="secondary"
            variant="text"
            size="small"
            :loading="manualRefreshing"
            @click="refreshNow"
          />
        </div>
      </div>

      <div v-if="loadError" class="flex items-center gap-item px-item py-item border border-separator rounded-container text-status-error bg-surface">
        <i class="pi pi-exclamation-circle" />
        <span>{{ loadError }}</span>
      </div>
    </div>

    <div
      ref="viewerRef"
      class="flex-1 min-h-tab-content overflow-auto bg-surface border border-separator rounded-container p-container"
      @scroll="handleScroll"
    >
      <div v-if="initialLoading && !initialized" class="ui-tab-empty min-h-tab-content">
        <i class="pi pi-spinner pi-spin text-display mb-item opacity-50"></i>
        <p class="text-title font-medium">{{ $t('backendLogs.loadingTitle') }}</p>
        <p class="text-caption text-muted">{{ $t('backendLogs.loadingDescription') }}</p>
      </div>

      <div v-else-if="displayLines.length === 0" class="ui-tab-empty min-h-tab-content">
        <p class="text-title font-medium mb-item">{{ lineCount > 0 ? $t('backendLogs.noMatchedLines') : $t('backendLogs.emptyTitle') }}</p>
        <p class="text-caption text-muted">
          {{ lineCount > 0 ? $t('backendLogs.noMatchedHint') : $t('backendLogs.emptyDescription') }}
        </p>
      </div>

      <div v-else class="flex flex-col">
        <div
          v-for="entry in displayLines"
          :key="entry.key"
          :class="entry.className"
        >
          {{ entry.text }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'

import { useBackendLogViewer } from '@/composables/useBackendLogViewer'
import { formatAbsoluteDateTime } from '@/utils/formatters'

const props = defineProps({
  isActive: {
    type: Boolean,
    default: false,
  },
})

const viewerRef = ref(null)
const stickToTop = ref(true)
const activeState = computed(() => props.isActive)
const { t } = useI18n()

const {
  autoRefreshEnabled,
  filteredLineCount,
  filteredEntries,
  initialized,
  initialLoading,
  keyword,
  lastRefreshedAt,
  lineCount,
  loadError,
  manualRefreshing,
  pauseAutoRefresh,
  refreshNow,
  resumeAutoRefresh,
  selectedLevel,
  sourceFile,
} = useBackendLogViewer(activeState)

const levelOptions = computed(() => [
  { label: t('backendLogs.levels.all'), value: '' },
  { label: t('backendLogs.levels.warning'), value: 'warning' },
  { label: t('backendLogs.levels.error'), value: 'error' },
  { label: t('backendLogs.levels.critical'), value: 'critical' },
  { label: t('backendLogs.levels.info'), value: 'info' },
  { label: t('backendLogs.levels.debug'), value: 'debug' },
  { label: t('backendLogs.levels.trace'), value: 'trace' },
])

const displayLines = computed(() => (
  [...filteredEntries.value]
    .reverse()
    .flatMap((entry, entryIndex) => entry.lines.map((text, lineIndex) => ({
      key: `${entryIndex}:${lineIndex}:${entry.key}`,
      text,
      className: getLineClassName(text, entry.level),
    })))
))

function getLineClassName(line, level) {
  if (level === 'error' || level === 'critical' || line.includes(' | ERROR | ') || line.includes(' | CRITICAL | ')) {
    return 'ui-log-line font-mono ui-log-line-error'
  }
  if (level === 'warning' || line.includes(' | WARNING | ')) {
    return 'ui-log-line font-mono ui-log-line-warn'
  }
  return 'ui-log-line font-mono'
}

function isNearTop(element) {
  if (!element) return true
  return element.scrollTop <= 24
}

function handleScroll(event) {
  stickToTop.value = isNearTop(event.target)
}

function scrollToTop() {
  nextTick(() => {
    const element = viewerRef.value
    if (!element) return
    element.scrollTop = 0
    stickToTop.value = true
  })
}

function toggleAutoRefresh() {
  if (autoRefreshEnabled.value) {
    pauseAutoRefresh()
  } else {
    resumeAutoRefresh()
  }
}

watch(
  () => props.isActive,
  (active) => {
    if (!active) return
    if (stickToTop.value) {
      scrollToTop()
    }
  }
)

watch(
  () => displayLines.value.length,
  async () => {
    if (!props.isActive || !stickToTop.value) return
    await nextTick()
    scrollToTop()
  }
)
</script>

<style scoped>
.ui-log-line {
  font-size: var(--text-caption);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-default);
}

.ui-log-line-warn {
  color: var(--state-warn);
}

.ui-log-line-error {
  color: var(--state-error);
}
</style>
