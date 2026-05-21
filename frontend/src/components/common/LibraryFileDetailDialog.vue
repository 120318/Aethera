<template>
  <ConfigDialog v-model="visible" size="md" :closable="false">
    <template #header>
      <div class="flex items-center justify-between w-full">
        <span class="p-dialog-title">{{ $t('libraryFileDetail.title') }}</span>
        <div class="flex items-center gap-item">
          <Button
            :icon="showRaw ? 'pi pi-list' : 'pi pi-code'"
            :title="showRaw ? $t('libraryFileDetail.viewStructured') : $t('libraryFileDetail.viewRaw')"
            severity="secondary"
            text
            class="p-none"
            @click="toggleRaw"
          />
          <Button
            icon="pi pi-times"
            severity="secondary"
            text
            class="p-none"
            @click="visible = false"
          />
        </div>
      </div>
    </template>
    <div v-if="loading" class="ui-dialog-section">
      <div class="flex flex-col gap-item">
        <Skeleton width="100%" height="1.25rem" />
        <Skeleton width="80%" height="1.25rem" />
        <Skeleton width="100%" height="1.25rem" />
        <Skeleton width="60%" height="1.25rem" />
      </div>
    </div>
    <div v-else-if="record">
      <div v-if="showRaw" class="ui-dialog-section">
        <pre class="text-caption text-muted m-none whitespace-pre-wrap break-all">{{ prettyRecord }}</pre>
      </div>
      <template v-else>
        <div class="flex flex-col gap-item">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.fileName') }}</label>
            <div class="text-body break-all">{{ displayFileName }}</div>
            <div v-if="isPackageDetail" class="text-caption text-muted mt-inline break-all">{{ packageDetail.package_root || '-' }}</div>
            <div v-if="isTvResource && (seasonDisplay || episodeDisplay)" class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block mt-inline">
              <div v-if="seasonDisplay" class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.season') }}</label>
                <div class="text-body">{{ seasonDisplay }}</div>
              </div>
              <div v-if="episodeDisplay" class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.episode') }}</label>
                <div class="text-body">{{ episodeDisplay }}</div>
              </div>
            </div>
          </div>
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.torrentName') }}</label>
            <div class="text-body break-all">{{ displayTorrentName }}</div>
          </div>
          <div class="ui-dialog-section">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
              <div class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.fileSize') }}</label>
                <div class="text-body">{{ formattedSize }}</div>
              </div>
              <div class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ resource?.is_package ? $t('libraryFileDetail.packageFiles') : $t('libraryFileDetail.fileIndex') }}</label>
                <div class="text-body">{{ isPackageDetail ? $t('libraryFileDetail.fileCount', { count: packageDetail.file_count || 0 }) : (record.file_index ?? '-') }}</div>
              </div>
            </div>
          </div>
          <div class="ui-dialog-section">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
              <div class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.directory') }}</label>
                <div class="text-body">{{ displayDirectoryName }}</div>
              </div>
              <div class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.importTime') }}</label>
                <div class="text-body">{{ formattedCreatedAt }}</div>
              </div>
            </div>
          </div>
          <div class="ui-dialog-section">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
              <div class="flex flex-col gap-inline">
                <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.directoryPath') }}</label>
                <div class="text-body break-all">{{ record.path || '-' }}</div>
              </div>
            </div>
          </div>
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.spec') }}</label>
            <div class="text-body">
              <ResourceAttributes
                v-if="hasResourceTags || detailStatusTags.length"
                :attributes="displayAttributes"
                :leading-tags="detailStatusTags"
                :visible-tags="libraryFileVisibleTags"
              />
              <span v-if="!hasResourceTags && !detailStatusTags.length">-</span>
            </div>
          </div>
          <div v-if="libraryFileStructure.length > 0" class="ui-dialog-section">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('libraryFileDetail.fileStructure') }}</label>
            <FileStructureTree :files="libraryFileStructure" :root-name="fileStructureRootName" />
          </div>
        </div>
      </template>
    </div>
    <div v-else class="ui-dialog-section">
      <p class="text-body text-muted m-none">{{ $t('libraryFileDetail.noDetail') }}</p>
    </div>
  </ConfigDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Skeleton from 'primevue/skeleton'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import FileStructureTree from '@/components/common/FileStructureTree.vue'
import ResourceAttributes from '@/components/common/ResourceAttributes.vue'
import { ResourceTagType } from '@/constants/resourceTagTypes'
import { formatSizeBytes, formatTimestamp } from '@/utils/formatters'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  record: {
    type: Object,
    default: null,
  },
  packageDetail: {
    type: Object,
    default: null,
  },
  resource: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const libraryFileVisibleTags = [
  ResourceTagType.RESOLUTION,
  ResourceTagType.VIDEO_CODEC,
  ResourceTagType.AUDIO_CODEC,
  ResourceTagType.HDR_TYPE,
  ResourceTagType.AUDIO_CHANNELS,
  ResourceTagType.COLOR_DEPTH,
  ResourceTagType.RESOURCE_FORM,
  ResourceTagType.PACKAGE_LAYOUT,
  ResourceTagType.DISC,
  ResourceTagType.GROUP,
  ResourceTagType.SOURCE,
  ResourceTagType.VERSION,
  ResourceTagType.LANGUAGE,
  ResourceTagType.SUBTITLE,
]

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const showRaw = ref(false)

const isPackageDetail = computed(() => !!props.packageDetail)
const prettyRecord = computed(() => JSON.stringify(isPackageDetail.value ? { file: props.record, package: props.packageDetail } : props.record, null, 2))
const formattedSize = computed(() => formatSizeBytes(isPackageDetail.value ? props.packageDetail?.total_size || 0 : props.record?.file_size || 0))
const displayFileName = computed(() => (
  props.packageDetail?.file_name
  || props.record?.file_name
  || props.resource?.file_name
  || '-'
))
const displayTorrentName = computed(() => (
  props.resource?.resource_title
  || props.resource?.name
  || props.record?.resource_attributes?.title
  || '-'
))
const displayDirectoryName = computed(() => props.packageDetail?.directory_name || props.record?.directory_name || '-')
const isTvResource = computed(() => {
  const type = props.resource?.media_type || props.resource?.type || displayAttributes.value?.content_type
  if (type === 'tv') return true
  const seasons = displayAttributes.value?.seasons
  const episodes = displayAttributes.value?.episodes
  return (Array.isArray(seasons) && seasons.length > 0) || (Array.isArray(episodes) && episodes.length > 0)
})
const seasonDisplay = computed(() => {
  const attrs = displayAttributes.value
  const seasonRaw = Array.isArray(attrs.seasons) && attrs.seasons.length > 0 ? attrs.seasons[0] : null
  const seasonNum = Number(seasonRaw)
  return Number.isFinite(seasonNum) ? t('calendar.seasonLabel', { number: seasonNum }) : ''
})
const episodeDisplay = computed(() => {
  const attrs = displayAttributes.value
  const episodeRaw = Array.isArray(attrs.episodes) && attrs.episodes.length > 0 ? attrs.episodes[0] : null
  const episodeNum = Number(episodeRaw)
  return Number.isFinite(episodeNum) ? t('calendar.episodeLabel', { number: episodeNum }) : ''
})
const hasResourceTags = computed(() => {
  const attrs = displayAttributes.value
  return Object.values(attrs).some((value) => {
    if (Array.isArray(value)) return value.length > 0
    return value !== null && value !== undefined && value !== ''
  })
})
const formattedCreatedAt = computed(() => {
  const raw = props.packageDetail?.created_at || props.record?.created_at
  return raw ? formatTimestamp(raw) : '-'
})
const displayAttributes = computed(() => props.packageDetail?.resource_attributes || props.record?.resource_attributes || {})
const artifactSummary = computed(() => props.packageDetail?.artifact_summary || props.record?.artifact_summary || {})
const detailStatusTags = computed(() => {
  const tags = []
  if (artifactSummary.value.scraped) {
    tags.push({ key: 'scraped', value: t('libraryFileDetail.statusScraped'), tone: 'success' })
  }
  if (artifactSummary.value.danmu) {
    tags.push({ key: 'danmu', value: t('libraryFileDetail.statusDanmu'), tone: 'accent' })
  }
  return tags
})
const packageFiles = computed(() => {
  const files = Array.isArray(props.packageDetail?.files) ? props.packageDetail.files : []
  return files
})
const libraryFileStructure = computed(() => {
  if (packageFiles.value.length > 0) return packageFiles.value
  if (!props.record) return []
  return [{
    relative_path: props.record.file_name || displayFileName.value,
    file_name: props.record.file_name || displayFileName.value,
    file_size: props.record.file_size || 0,
    file_index: props.record.file_index ?? null,
  }]
})
const fileStructureRootName = computed(() => {
  if (props.packageDetail?.file_name) return props.packageDetail.file_name
  return ''
})

function toggleRaw() {
  showRaw.value = !showRaw.value
}

watch(visible, (val) => {
  if (!val) {
    showRaw.value = false
  }
})
</script>
