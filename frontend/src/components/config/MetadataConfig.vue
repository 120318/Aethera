<template>
  <div class="grid grid-cols-1 gap-container">
    <div class="ui-settings-card">
      <div class="ui-settings-card-header flex items-start justify-between gap-container">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.metadata.browseSourceTitle') }}</h4>
          <p class="m-none text-caption text-muted">{{ $t('settings.metadata.browseSourceDescription') }}</p>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingSource" @click="saveBrowseSourcePreference" />
      </div>
      <div class="ui-settings-card-body">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="ui-dialog-section m-none">
            <label for="browse-source" class="ui-dialog-item-title block">{{ $t('settings.metadata.source') }}</label>
            <Select
              id="browse-source"
              v-model="browseSource"
              :options="browseSourceOptions"
              option-label="label"
              option-value="value"
              class="w-full"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="ui-settings-card">
      <div class="ui-settings-card-header flex items-start justify-between gap-container">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.metadata.tmdbTitle') }}</h4>
          <p class="m-none text-caption text-muted">
            {{ $t('settings.metadata.tmdbDescription') }}
            <a href="https://www.themoviedb.org/settings/api" target="_blank" class="text-primary hover:underline">
              {{ $t('settings.metadata.tmdbApiSettings') }}
            </a>
            {{ $t('settings.metadata.tmdbApplyApiKey') }}
          </p>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingTMDB" @click="saveTMDB" />
      </div>
      <div class="ui-settings-card-body">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item items-center">
          <div class="ui-dialog-section m-none md:self-center">
            <label for="tmdb-api-key" class="ui-dialog-item-title block">{{ $t('common.apiKey') }}</label>
            <InputText
              id="tmdb-api-key"
              v-model="tmdb.api_key"
              :placeholder="$t('settings.metadata.apiKeyPlaceholder')"
              class="w-full"
            />
          </div>
          <div class="ui-dialog-section m-none">
            <label for="tmdb-proxy-images" class="ui-dialog-item-title block">{{ $t('settings.metadata.imageProxy') }}</label>
            <div class="flex items-center gap-item h-control-field-md">
              <ToggleSwitch v-model="tmdb.proxy_images" input-id="tmdb-proxy-images" />
              <label for="tmdb-proxy-images" class="text-body m-none whitespace-nowrap">{{ $t('settings.metadata.backendProxy') }}</label>
            </div>
          </div>
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.metadata.discoverListControl') }}</label>

          <div v-if="loadingTMDBOptions" class="flex justify-center p-block">
            <i class="pi pi-spin pi-spinner text-2xl text-primary"></i>
          </div>

          <PickList v-else v-model="tmdbPickListValues" data-key="key" breakpoint="1400px" scroll-height="24rem" :show-source-controls="false">
            <template #sourceheader>
              <span class="text-muted font-semibold text-subtitle">{{ $t('settings.metadata.availableLists') }}</span>
            </template>
            <template #targetheader>
              <span class="text-muted font-semibold text-subtitle">{{ $t('settings.metadata.visibleLists') }}</span>
            </template>
            <template #item="{ item, selected }">
              <div class="flex items-center w-full gap-item">
                <div class="flex-1 flex flex-col">
                  <span class="font-medium text-caption">{{ discoverListTitle(item) }}</span>
                  <span :class="['text-tiny', { 'text-muted': !selected, 'text-inherit': selected }]">{{ item.key }}</span>
                </div>
              </div>
            </template>
          </PickList>
        </div>
      </div>
    </div>

    <div class="ui-settings-card">
      <div class="ui-settings-card-header flex items-start justify-between gap-container">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.metadata.doubanTitle') }}</h4>
          <p class="m-none text-caption text-muted">{{ $t('settings.metadata.doubanDescription') }}</p>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingDouban" @click="saveDouban" />
      </div>
      <div class="ui-settings-card-body">
        <div class="ui-dialog-section">
          <label for="douban-proxy-images" class="ui-dialog-item-title block">{{ $t('settings.metadata.imageProxy') }}</label>
          <div class="flex items-center gap-item h-control-field-md">
            <ToggleSwitch v-model="douban.proxy_images" input-id="douban-proxy-images" />
            <label for="douban-proxy-images" class="text-body m-none whitespace-nowrap">{{ $t('settings.metadata.backendProxy') }}</label>
          </div>
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.metadata.discoverListControl') }}</label>
          
          <div v-if="loadingDoubanOptions" class="flex justify-center p-block">
            <i class="pi pi-spin pi-spinner text-2xl text-primary"></i>
          </div>
          
          <PickList v-else v-model="doubanPickListValues" data-key="key" breakpoint="1400px" scroll-height="24rem" :show-source-controls="false">
            <template #sourceheader>
              <span class="text-muted font-semibold text-subtitle">{{ $t('settings.metadata.availableLists') }}</span>
            </template>
            <template #targetheader>
              <span class="text-muted font-semibold text-subtitle">{{ $t('settings.metadata.visibleLists') }}</span>
            </template>
            <template #item="{ item, selected }">
              <div class="flex items-center w-full gap-item">
                <div class="flex-1 flex flex-col">
                  <span class="font-medium text-caption">{{ discoverListTitle(item) }}</span>
                  <span :class="['text-tiny', { 'text-muted': !selected, 'text-inherit': selected }]">{{ item.key }}</span>
                </div>
              </div>
            </template>
          </PickList>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import PickList from 'primevue/picklist'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import { useI18n } from 'vue-i18n'
import { useNotificationStore } from '@/stores/notification'
import { useMediaImageSettingsStore } from '@/stores/media-image-settings'
import { saveDoubanConfig, saveServicesConfig, saveTMDBConfig } from '@/api/config'
import { getDiscoverListMetas } from '@/api/discover'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  applyConfigPatch: {
    type: Function,
    required: true,
  },
})

const notification = useNotificationStore()
const mediaImageSettings = useMediaImageSettingsStore()
const { t } = useI18n()
const savingTMDB = ref(false)
const savingDouban = ref(false)
const savingSource = ref(false)
const loadingDoubanOptions = ref(false)
const loadingTMDBOptions = ref(false)
const browseSource = ref('douban')
const browseSourceOptions = computed(() => [
  { label: t('settings.metadata.doubanSource'), value: 'douban' },
  { label: t('settings.metadata.tmdbSource'), value: 'tmdb' },
])
const tmdb = reactive({
  api_key: '',
  proxy_images: false,
})
const douban = reactive({
  proxy_images: true,
})

const doubanPickListValues = ref([[], []])
const tmdbPickListValues = ref([[], []])
const doubanOptions = ref([])
const tmdbOptions = ref([])

const loadOptions = async (source) => {
  const loadingRef = source === 'tmdb' ? loadingTMDBOptions : loadingDoubanOptions
  const optionsRef = source === 'tmdb' ? tmdbOptions : doubanOptions
  loadingRef.value = true
  try {
    const res = await getDiscoverListMetas(source)
    optionsRef.value = res.data || []
    initPickList(source)
  } catch (error) {
    console.error(t('settings.metadata.loadListOptionsFailed'), error)
  } finally {
    loadingRef.value = false
  }
}

const discoverListTitle = (item) => (
  item?.title_key ? t(item.title_key) : item?.title || item?.key || ''
)

const initPickList = (source) => {
  const options = source === 'tmdb' ? tmdbOptions.value : doubanOptions.value
  if (!options.length) return
  const selectedKeys = source === 'tmdb'
    ? (props.config.themoviedb?.discover_lists || [])
    : (props.config.douban?.discover_lists || [])
  const selected = []
  const unselected = []
  
  // Preserve selection order.
  for (const key of selectedKeys) {
    const opt = options.find(o => o.key === key)
    if (opt) selected.push(opt)
  }
  
  // Filter out unselected items.
  for (const opt of options) {
    if (!selectedKeys.includes(opt.key)) unselected.push(opt)
  }
  
  if (source === 'tmdb') {
    tmdbPickListValues.value = [unselected, selected]
  } else {
    doubanPickListValues.value = [unselected, selected]
  }
}

watch(() => props.config.douban?.discover_lists, () => {
  if (doubanOptions.value.length > 0) initPickList('douban')
}, { deep: true })

watch(() => props.config.themoviedb?.discover_lists, () => {
  if (tmdbOptions.value.length > 0) initPickList('tmdb')
}, { deep: true })

watch(
  () => props.config.browse_source,
  (value) => {
    browseSource.value = value === 'tmdb' ? 'tmdb' : 'douban'
  },
  { immediate: true },
)

watch(
  () => props.config.douban,
  (value) => {
    douban.proxy_images = value?.proxy_images !== false
  },
  { deep: true, immediate: true },
)

watch(
  () => props.config.themoviedb,
  (value) => {
    tmdb.api_key = value?.api_key || ''
    tmdb.proxy_images = !!value?.proxy_images
  },
  { deep: true, immediate: true },
)

onMounted(() => {
  loadOptions('douban')
  loadOptions('tmdb')
})

const saveBrowseSourcePreference = async () => {
  savingSource.value = true
  try {
    const nextServices = {
      browse_source: browseSource.value,
      themoviedb: props.config.themoviedb || { api_key: '', proxy_images: false, discover_lists: [] },
      douban: props.config.douban || { discover_lists: [], proxy_images: true },
    }
    await saveServicesConfig(nextServices)
    props.applyConfigPatch({ browse_source: browseSource.value })
    notification.success(t('settings.metadata.browseSourceSaved'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingSource.value = false
  }
}

const saveTMDB = async () => {
  savingTMDB.value = true
  try {
    const nextTMDB = {
      ...(props.config.themoviedb || {}),
      api_key: tmdb.api_key,
      proxy_images: !!tmdb.proxy_images,
      discover_lists: tmdbPickListValues.value[1].map(item => item.key),
    }
    await saveTMDBConfig(nextTMDB)
    props.applyConfigPatch({ themoviedb: nextTMDB })
    mediaImageSettings.patchFromServicesConfig({
      themoviedb: nextTMDB,
      douban: props.config.douban || { discover_lists: [], proxy_images: true },
    })
    notification.success(t('settings.metadata.tmdbSaved'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingTMDB.value = false
  }
}

const saveDouban = async () => {
  savingDouban.value = true
  try {
    const selectedKeys = doubanPickListValues.value[1].map(item => item.key)
    const nextDouban = {
      ...(props.config.douban || {}),
      discover_lists: selectedKeys,
      proxy_images: douban.proxy_images !== false,
    }
    await saveDoubanConfig(nextDouban)
    props.applyConfigPatch({ douban: nextDouban })
    mediaImageSettings.patchFromServicesConfig({
      themoviedb: props.config.themoviedb || { api_key: '', proxy_images: false },
      douban: nextDouban,
    })
    notification.success(t('settings.metadata.doubanSaved'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingDouban.value = false
  }
}
</script>
