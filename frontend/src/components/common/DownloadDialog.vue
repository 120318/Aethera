<template>
  <ConfigDialog
    :model-value="visible"
    :title="$t('downloadDialog.title')"
    :intro="$t('downloadDialog.intro')"
    @update:model-value="$emit('update:visible', $event)"
  >

    <!-- Resource overview -->
    <div class="ui-dialog-section">
      <label class="ui-dialog-item-title">{{ $t('downloadDialog.resourceOverview') }}</label>
      <div class="ui-card p-container">
        <div class="flex items-start gap-inline">
          <div class="flex-1 flex flex-col gap-inline">
            <h4 class="text-body font-semibold wrap-break-word" :title="displayResource?.title">
              {{ displayResource?.title || $t('downloadDialog.unknownResource') }}
            </h4>

            <p
              v-if="displayResource?.description" class="text-muted wrap-break-word"
              :title="displayResource.description"
            >
              {{ displayResource.description }}
            </p>

            <div class="flex flex-wrap items-center gap-x-inline gap-y-inline">
              <AppTag
                v-for="(tag, idx) in resourceTags"
                :key="idx"
                :value="tag.value"
                :icon="tag.icon"
                :tone="tag.tone"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Directory selection -->
    <div class="ui-dialog-section">
      <label class="ui-dialog-item-title">{{ $t('downloadDialog.directory') }}</label>
      <Select
        v-model="selectedDirectoryId" :options="availableDirectories" :option-label="getDirectoryDisplayName"
        option-value="id" :placeholder="$t('downloadDialog.selectDirectory')" class="w-full" @change="handleDirectoryChange"
      >
        <template #value="slotProps">
          <div v-if="slotProps.value" class="flex items-center gap-item">
            <i class="pi pi-folder text-primary"></i>
            <span>{{ getDirectoryDisplayName(availableDirectories.find(d => d.id === slotProps.value)) }}</span>
          </div>
          <span v-else>{{ slotProps.placeholder }}</span>
        </template>
        <template #option="slotProps">
          <div class="flex items-center gap-item">
            <i class="pi pi-folder text-muted"></i>
            <span>{{ getDirectoryDisplayName(slotProps.option) }}</span>
            <AppTag v-if="slotProps.option.is_default" :label="$t('common.default')" tone="success" />
          </div>
        </template>
      </Select>

      <div v-if="selectedDirectory" class="ui-dialog-subsection">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-y-item gap-x-block">
          <div class="flex flex-col gap-inline">
            <span class="text-muted">{{ $t('downloadDialog.physicalPath') }}</span>
            <span class="truncate select-all" :title="selectedDirectory.path">{{ selectedDirectory.path
            }}</span>
          </div>
          <div class="flex flex-col gap-inline">
            <span class="text-muted">{{ $t('downloadDialog.downloadPath') }}</span>
            <span class="truncate select-all" :title="selectedDirectory.download_path">{{
              selectedDirectory.download_path || $t('downloadDialog.sameAsPhysicalPath') }}</span>
          </div>
          <div class="flex flex-col gap-inline">
            <span class="text-muted">{{ $t('downloadDialog.downloader') }}</span>
            <span class="truncate">{{ getDownloaderName(selectedDirectory.downloader_id) || $t('common.notSet') }}</span>
          </div>
          <div class="flex flex-col gap-inline">
            <span class="text-muted">{{ $t('downloadDialog.mediaLibrary') }}</span>
            <span class="truncate">{{ getMediaServerName(selectedDirectory.media_server_id) || $t('common.notSet') }}</span>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="$t('common.cancel')" severity="secondary" text @click="handleClose" />
      <Button
        :label="$t('downloadDialog.downloadNow')" icon="pi pi-download" :disabled="!selectedDirectoryId" :loading="loading"
        @click="handleDownload"
      />
    </template>
  </ConfigDialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { getDirectoriesTabConfig } from '@/api/config'
import { useNotificationStore } from '@/stores/notification'
import { useResourceTags } from '@/composables/useResourceTags'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  resourceData: {
    type: Object,
    default: null
  },
  mediaInfo: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:visible', 'download'])

const notificationStore = useNotificationStore()
const { t } = useI18n()
const loading = ref(false)
const availableDirectories = ref([])
const availableDownloaders = ref([])
const availableMediaServers = ref([])
const selectedDirectoryId = ref(null)
const selectedDirectory = ref(null)

const { getSortedTags } = useResourceTags()

// Normalize resource data.
const displayResource = computed(() => {
  if (!props.resourceData) return null
  // resourceData may be either an inner resource or a wrapper from callers.
  const r = props.resourceData.resource || props.resourceData
  return {
    title: props.resourceData.title || props.resourceData.name || r.title || r.name,
    description: r.description || props.resourceData.description,
    size: r.size || props.resourceData.size,
    site: r.site || props.resourceData.site,
    id: r.id || props.resourceData.id
  }
})

const mediaType = computed(() => {
  const explicitType = props.mediaInfo?.media_type || props.mediaInfo?.type
  if (explicitType === 'movie' || explicitType === 'tv') {
    return explicitType
  }
  const mediaId = String(props.mediaInfo?.media_id || props.mediaInfo?.id || '')
  const [, type] = mediaId.split(':')
  return type === 'movie' || type === 'tv' ? type : null
})

const getDirectoryDisplayName = (dir) => {
  if (!dir) return ''
  return dir.name || dir.path || dir.id || ''
}

const getDownloaderName = (id) => {
  const downloader = availableDownloaders.value.find(item => item.id === id)
  return downloader?.name || ''
}

const getMediaServerName = (id) => {
  const mediaServer = availableMediaServers.value.find(item => item.id === id)
  return mediaServer?.name || ''
}

const handleDirectoryChange = () => {
  selectedDirectory.value = availableDirectories.value.find(d => d.id === selectedDirectoryId.value) || null
}

const fetchDirectories = async () => {
  try {
    const response = await getDirectoriesTabConfig()
    availableDownloaders.value = response.downloaders || []
    availableMediaServers.value = response.media_servers || []
    if (response.directories) {
      availableDirectories.value = response.directories.filter((d) => {
        if (!d.enabled) return false
        if (!mediaType.value) return true
        return d.media_type === mediaType.value
      })

      const defaultDir = availableDirectories.value.find(d => d.is_default)
      if (defaultDir) {
        selectedDirectoryId.value = defaultDir.id
        handleDirectoryChange()
      } else if (availableDirectories.value.length > 0) {
        selectedDirectoryId.value = availableDirectories.value[0].id
        handleDirectoryChange()
      }
    }
  } catch (error) {
    console.error(t('downloadDialog.loadDirectoriesFailed'), error)
    notificationStore.error(t('downloadDialog.loadDirectoriesFailed'))
  }
}

const handleDownload = async () => {
  if (!selectedDirectoryId.value || !displayResource.value) return

  loading.value = true
  try {
    // Parent component handles the actual download request.
    emit('download', {
      directory_id: selectedDirectoryId.value,
      resource: props.resourceData // Pass back the original prop data
    })

  } catch (error) {
    console.error(t('downloadDialog.addTaskFailed'), error)
    notificationStore.error(t('downloadDialog.addTaskFailed'))
  } finally {
    loading.value = false
  }
}

const handleClose = () => {
  emit('update:visible', false)
}

watch(() => props.visible, (newVal) => {
  if (newVal) {
    fetchDirectories()
  } else {
    loading.value = false
  }
})

onMounted(() => {
  if (props.visible) {
    fetchDirectories()
  }
})

// Tag Helper Logic
const resourceTags = computed(() => {
  let wrapper = props.resourceData;
  if (!wrapper) return []

  if (!wrapper.resource && !wrapper.attributes) {
    wrapper = { resource: props.resourceData, attributes: {} }
  }
  else if (wrapper.resource && !wrapper.attributes) {
    wrapper = { ...wrapper, attributes: {} }
  }

  return getSortedTags(wrapper)
})
</script>

<style scoped>
/* Tailwind utilities are used instead of custom CSS. */
</style>
