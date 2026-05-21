<template>
  <div>
    <!-- Filter list -->
    <div
      v-if="filters && filters.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-tall"
    >
      <div v-for="filter in filters" :key="filter.id" class="ui-settings-card h-full">
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h4 class="m-none text-body font-semibold text-color">{{ filter.name || $t('settings.filter.unnamed') }}</h4>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag v-if="filter.is_default" :value="$t('settings.filter.systemPreset')" tone="success" />
            <AppTag v-if="filter.active_default" :value="$t('common.default')" tone="accent" />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p v-if="filter.filters.resolution?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.resolution') }}</strong> {{ filter.filters.resolution.join(', ') }}
            </p>
            <p v-if="filter.filters.hdr_type?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.hdr') }}</strong> {{ filter.filters.hdr_type.join(', ') }}
            </p>
            <p v-if="filter.filters.audio_channels?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.audioChannels') }}</strong> {{ filter.filters.audio_channels.join(', ') }}
            </p>
            <p v-if="filter.filters.source?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.source') }}</strong> {{ filter.filters.source.join(', ') }}
            </p>
            <p v-if="hasCustomResourceSelection(filter.filters)" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.resourceType') }}</strong> {{ formatResourceSelection(filter.filters) }}
            </p>
            <p v-if="filter.filters.codec?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.codec') }}</strong> {{ filter.filters.codec.join(', ') }}
            </p>
            <p v-if="filter.filters.audio_codec?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.audioCodec') }}</strong> {{ filter.filters.audio_codec.join(', ') }}
            </p>
            <p v-if="filter.filters.color_depth?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.colorDepth') }}</strong> {{ filter.filters.color_depth.join(', ') }}
            </p>
            <p v-if="filter.filters.include_keywords?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.includeKeywords') }}</strong> {{ filter.filters.include_keywords.join(', ') }}
            </p>
            <p v-if="filter.filters.exclude_keywords?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.excludeKeywords') }}</strong> {{ filter.filters.exclude_keywords.join(', ') }}
            </p>
            <p v-if="filter.filters.tags?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.tags') }}</strong> {{ formatTagNames(filter.filters.tags) }}
            </p>
            <p v-if="filter.quality_profile_id" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.qualityProfile') }}</strong> {{ getQualityProfileName(filter.quality_profile_id) }}
            </p>
            <p v-if="filter.filters.upgrade_policy?.enabled" class="m-none">
              <strong class="font-semibold">{{ $t('settings.filter.upgradePolicy') }}</strong> {{ formatUpgradePolicy(filter.filters.upgrade_policy) }}
            </p>
            <p
              v-if="!filter.filters.resolution?.length
                && !filter.filters.hdr_type?.length
                && !filter.filters.audio_channels?.length
                && !filter.filters.source?.length
                && !hasCustomResourceSelection(filter.filters)
                && !filter.filters.codec?.length
                && !filter.filters.audio_codec?.length
                && !filter.filters.color_depth?.length
                && !filter.filters.include_keywords?.length
                && !filter.filters.exclude_keywords?.length
                && !filter.filters.tags?.length
                && !filter.filters.upgrade_policy?.enabled"
              class="m-none"
            >
              <strong class="font-semibold">{{ $t('settings.filter.rules') }}</strong> {{ $t('settings.filter.noRules') }}
            </p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button
            v-if="!filter.active_default"
            :label="$t('common.setDefault')"
            severity="secondary"
            outlined
            size="small"
            @click="setDefaultFilter(filter)"
          />
          <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="editFilter(filter)" />
          <Button
            :label="$t('common.delete')" severity="secondary" outlined size="small" :disabled="filter.is_default"
            @click="confirmDelete(filter)"
          />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addFilter">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-tall"
    >
      <button type="button" class="ui-settings-add-card" @click="addFilter">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Filter editor dialog -->
    <ConfigDialog
      v-model:visible="dialogVisible"
      :title="dialogTitle"
      size="md"
      :intro="$t('settings.filter.intro')"
    >
      <!-- Basic information -->
      <div class="ui-dialog-section">
        <label for="filter-name" class="ui-dialog-item-title block">{{ $t('settings.filter.name') }}</label>
        <InputText id="filter-name" v-model="currentFilter.name" :placeholder="$t('settings.filter.namePlaceholder')" class="w-full" />
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.filter.qualityProfileLabel') }}</label>
        <Dropdown
          v-model="currentFilter.quality_profile_id" :options="qualityProfileOptions" option-label="label" option-value="value"
          :placeholder="$t('settings.filter.selectQualityProfile')" class="w-full"
        />
        <p class="m-none mt-inline text-tiny text-muted">{{ $t('settings.filter.qualityProfileHelp') }}</p>
      </div>

      <div class="ui-dialog-grid">
        <!-- Resolution -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.resourceKind') }}</label>
          <ResourceKindFormSelect
            v-model:resource-kind="currentFilter.filters.resource_kind"
            v-model:resource-form="currentFilter.filters.resource_form"
          />
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.resolutionLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.resolution" :options="resolutionOptions" filter :placeholder="$t('settings.filter.selectResolution')"
            display="chip" class="w-full"
          />
        </div>

        <!-- Source -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.sourceLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.source" :options="sourceOptions" filter :placeholder="$t('settings.filter.selectSource')"
            display="chip" class="w-full"
          />
        </div>

        <!-- Video encoding -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.codecLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.codec" :options="codecOptions" filter :placeholder="$t('settings.filter.selectCodec')" display="chip"
            class="w-full"
          />
        </div>

        <!-- HDR type -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.hdrLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.hdr_type" :options="hdrOptions" filter :placeholder="$t('settings.filter.selectHdr')"
            display="chip" class="w-full"
          />
        </div>

        <!-- Audio encoding -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.audioCodecLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.audio_codec" :options="audioCodecOptions" filter :placeholder="$t('settings.filter.selectAudioCodec')"
            display="chip" class="w-full"
          />
        </div>

        <!-- Audio channels -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.audioChannelsLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.audio_channels" :options="audioChannelOptions" filter
            :placeholder="$t('settings.filter.selectAudioChannels')" display="chip" class="w-full"
          />
        </div>

        <!-- Color depth -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.colorDepthLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.color_depth" :options="colorDepthOptions" filter :placeholder="$t('settings.filter.selectColorDepth')"
            display="chip" class="w-full"
          />
        </div>

        <!-- Tags -->
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.filter.tagsLabel') }}</label>
          <MultiSelect
            v-model="currentFilter.filters.tags" :options="tagOptions" option-label="label" filter
            option-value="value" :placeholder="$t('settings.filter.selectTags')" display="chip" class="w-full"
          />
        </div>
      </div>

      <!-- Keywords -->
      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.filter.includeKeywordsLabel') }}</label>
        <Chips
          v-model="currentFilter.filters.include_keywords"
          separator=","
          add-on-blur
          :placeholder="$t('settings.filter.keywordPlaceholder')"
          class="w-full"
        />
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.filter.excludeKeywordsLabel') }}</label>
        <Chips
          v-model="currentFilter.filters.exclude_keywords"
          separator=","
          add-on-blur
          :placeholder="$t('settings.filter.keywordPlaceholder')"
          class="w-full"
        />
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.filter.defaultConfig') }}</label>
        <div class="flex items-center gap-item">
          <ToggleSwitch v-model="currentFilter.active_default" input-id="filter-active-default" />
          <span class="text-muted-size font-muted text-muted">{{ currentFilter.active_default ? $t('settings.filter.defaultFilter') : $t('common.setDefault') }}</span>
        </div>
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="dialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" :loading="saving" @click="saveFilter" />
      </template>
    </ConfigDialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import ResourceKindFormSelect from '@/components/common/ResourceKindFormSelect.vue'
import Button from 'primevue/button';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import MultiSelect from 'primevue/multiselect';
import Chips from 'primevue/chips';
import ConfirmDialog from 'primevue/confirmdialog';
import ToggleSwitch from 'primevue/toggleswitch';
import { useConfirm } from 'primevue/useconfirm';
import { useNotificationStore } from '@/stores/notification';
import { getFilters, createFilter, updateFilter, deleteFilter } from '@/api/filter';
import { getTags } from '@/api/tags';
import { getQualityProfiles } from '@/api/quality_profiles';
import {
  QUALITY_AUDIO_CHANNEL_VALUES,
  QUALITY_AUDIO_CODEC_VALUES,
  QUALITY_COLOR_DEPTH_VALUES,
  QUALITY_HDR_TYPE_VALUES,
  qualityResourceKindOptions,
  QUALITY_RESOLUTION_VALUES,
  QUALITY_SOURCE_VALUES,
  QUALITY_VIDEO_CODEC_VALUES,
} from '@/constants/qualityOptions';

const confirm = useConfirm()
const notification = useNotificationStore()
const { t } = useI18n()

const filters = ref([])
const tags = ref([])
const qualityProfiles = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogMode = ref('add')
const currentFilter = ref({ name: '', filters: {} })
const saving = ref(false)

const resolutionOptions = [...QUALITY_RESOLUTION_VALUES]
const sourceOptions = [...QUALITY_SOURCE_VALUES]
const resourceKindOptions = [...qualityResourceKindOptions]
const codecOptions = [...QUALITY_VIDEO_CODEC_VALUES]
const hdrOptions = [...QUALITY_HDR_TYPE_VALUES]
const audioCodecOptions = [...QUALITY_AUDIO_CODEC_VALUES]
const audioChannelOptions = [...QUALITY_AUDIO_CHANNEL_VALUES]
const colorDepthOptions = [...QUALITY_COLOR_DEPTH_VALUES]

const tagOptions = computed(() =>
  tags.value.map((tag) => ({
    label: tag.name,
    value: tag.id
  }))
)

const qualityProfileOptions = computed(() =>
  qualityProfiles.value.map((profile) => ({
    label: profile.name,
    value: profile.id,
  }))
)

onMounted(() => {
  fetchFilters()
  fetchTags()
  fetchQualityProfiles()
})

function createEmptyFilter() {
  return {
    name: '',
    active_default: false,
    quality_profile_id: qualityProfiles.value.find((item) => item.active_default)?.id || qualityProfiles.value[0]?.id || null,
    filters: {
      resource_kind: ['video_file'],
      resolution: [],
      source: [],
      resource_form: [],
      codec: [],
      hdr_type: [],
      audio_codec: [],
      audio_channels: [],
      color_depth: [],
      include_keywords: [],
      exclude_keywords: [],
      tags: [],
      upgrade_policy: { enabled: false, strategy: 'consistent_allow_temp', min_upgrade_score_delta: 0, lock_mode: 'best_existing' }
    }
  }
}

function ensureFilterStructures() {
  if (!currentFilter.value.filters) currentFilter.value.filters = {}
  if (!Array.isArray(currentFilter.value.filters.resource_kind) || currentFilter.value.filters.resource_kind.length === 0) {
    currentFilter.value.filters.resource_kind = ['video_file']
  }
  if (!currentFilter.value.filters.tags) currentFilter.value.filters.tags = []
  if (!currentFilter.value.filters.upgrade_policy) {
    currentFilter.value.filters.upgrade_policy = {
      enabled: false,
      strategy: 'consistent_allow_temp',
      min_upgrade_score_delta: 0,
      lock_mode: 'best_existing'
    }
  } else {
    const policy = currentFilter.value.filters.upgrade_policy
    if (policy.enabled === undefined) policy.enabled = false
    if (!policy.strategy) policy.strategy = 'consistent_allow_temp'
    if (policy.min_upgrade_score_delta === undefined || policy.min_upgrade_score_delta === null) policy.min_upgrade_score_delta = 0
    if (!policy.lock_mode) policy.lock_mode = 'best_existing'
  }
}

function getTagName(tagId) {
  const tag = tags.value.find((item) => item.id === tagId)
  return tag ? tag.name : tagId
}

function getQualityProfileName(profileId) {
  const profile = qualityProfiles.value.find((item) => item.id === profileId)
  return profile ? profile.name : t('settings.quality.notConfigured')
}

function formatTagNames(tagIds) {
  return (tagIds || []).map((tagId) => getTagName(tagId)).join(', ')
}

function isCustomResourceKind(categories) {
  return Array.isArray(categories) && categories.length > 0 && !(categories.length === 1 && categories[0] === 'video_file')
}

function formatResourceKinds(categories) {
  const labels = new Map(resourceKindOptions.map((option) => [option.value, option.label]))
  const values = Array.isArray(categories) && categories.length > 0 ? categories : ['video_file']
  return values.map((value) => labels.get(value) || value).join(', ')
}

function hasCustomResourceSelection(filters) {
  return isCustomResourceKind(filters?.resource_kind) || (Array.isArray(filters?.resource_form) && filters.resource_form.length > 0)
}

function formatResourceSelection(filters) {
  const kinds = formatResourceKinds(filters?.resource_kind)
  const forms = Array.isArray(filters?.resource_form) ? filters.resource_form : []
  if (forms.length === 0) return kinds
  return `${kinds} / ${forms.join(', ')}`
}

function formatUpgradePolicy(policy) {
  if (!policy?.enabled) return t('settings.filter.closed')
  const strategyLabel = policy.strategy === 'consistent_skip_low' ? t('settings.filter.strictConsistent') : t('settings.filter.availabilityFirst')
  const lockModeMap = {
    off: t('settings.filter.noLock'),
    first_download: t('settings.filter.firstDownload'),
    best_existing: t('settings.filter.bestExisting'),
  }
  const lockLabel = lockModeMap[policy.lock_mode] || policy.lock_mode || t('settings.filter.noLock')
  return `${strategyLabel} / ${lockLabel} / ${t('settings.filter.scoreDelta', { delta: policy.min_upgrade_score_delta || 0 })}`
}

async function fetchTags() {
  try {
    tags.value = (await getTags()) || []
  } catch (error) {
    console.error(t('settings.quality.loadTagsFailed'), error)
  }
}

async function fetchQualityProfiles() {
  try {
    qualityProfiles.value = (await getQualityProfiles()) || []
  } catch (error) {
    console.error(t('settings.quality.loadFailed'), error)
  }
}

async function fetchFilters() {
  try {
    filters.value = (await getFilters()) || []
  } catch {
    notification.error(t('settings.filter.loadFailed'))
  }
}

function addFilter() {
  dialogVisible.value = true
  dialogTitle.value = t('settings.filter.addTitle')
  dialogMode.value = 'add'
  currentFilter.value = createEmptyFilter()
}

function editFilter(filter) {
  dialogVisible.value = true
  dialogTitle.value = t('settings.filter.editTitle')
  dialogMode.value = 'edit'
  currentFilter.value = JSON.parse(JSON.stringify(filter))
  currentFilter.value.active_default = currentFilter.value.active_default || false
  if (!currentFilter.value.filters) currentFilter.value.filters = {}
  const next = currentFilter.value.filters
  next.resource_kind = Array.isArray(next.resource_kind) && next.resource_kind.length > 0 ? next.resource_kind : ['video_file']
  next.resolution = next.resolution || []
  next.source = next.source || []
  next.resource_form = next.resource_form || []
  next.codec = next.codec || []
  next.hdr_type = next.hdr_type || []
  next.audio_codec = next.audio_codec || []
  next.audio_channels = next.audio_channels || []
  next.color_depth = next.color_depth || []
  next.include_keywords = next.include_keywords || []
  next.exclude_keywords = next.exclude_keywords || []
  next.tags = next.tags || []
  currentFilter.value.quality_profile_id = currentFilter.value.quality_profile_id || qualityProfiles.value.find((item) => item.active_default)?.id || qualityProfiles.value[0]?.id || null
  ensureFilterStructures()
}

async function setDefaultFilter(filter) {
  const previous = filters.value.map((item) => ({
    id: item.id,
    active_default: item.active_default,
  }))

  const changedFilters = filters.value.filter((item) => (
    (item.id === filter.id && !item.active_default)
    || (item.id !== filter.id && item.active_default)
  ))

  filters.value.forEach((item) => {
    item.active_default = item.id === filter.id
  })

  try {
    await Promise.all(changedFilters.map((item) => (
      updateFilter(item.id, {
        active_default: item.id === filter.id,
      })
    )))
    notification.success(t('settings.filter.defaultUpdated'))
    await fetchFilters()
  } catch (error) {
    filters.value.forEach((item) => {
      const snapshot = previous.find((entry) => entry.id === item.id)
      item.active_default = snapshot ? snapshot.active_default : false
    })
    notification.error(t('common.saveFailed', { message: error.message || t('common.unknownError') }))
  }
}

async function saveFilter() {
  if (!currentFilter.value.name) {
    notification.warn(t('settings.filter.nameRequired'))
    return
  }
  saving.value = true
  try {
    if (dialogMode.value === 'add') {
      await createFilter(currentFilter.value)
      notification.success(t('settings.filter.added'))
    } else {
      await updateFilter(currentFilter.value.id, currentFilter.value)
      notification.success(t('settings.filter.updated'))
    }
    dialogVisible.value = false
    await fetchFilters()
  } catch (error) {
    notification.error(t('common.saveFailed', { message: error.message || t('common.unknownError') }))
  } finally {
    saving.value = false
  }
}

function confirmDelete(filter) {
  confirm.require({
    message: t('settings.filter.deleteMessage', { name: filter.name || t('settings.filter.unnamed') }),
    header: t('settings.quality.deleteHeader'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    rejectProps: {
      severity: 'secondary',
      outlined: true,
    },
    acceptProps: {
      severity: 'primary',
    },
    accept: async () => {
      try {
        await deleteFilter(filter.id)
        notification.success(t('settings.filter.deleted'))
        await fetchFilters()
      } catch {
        notification.error(t('settings.tag.deleteFailed'))
      }
    }
  })
}
</script>
