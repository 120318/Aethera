<template>
  <div class="ui-settings-card h-full">
    <div class="ui-settings-card-header">
      <div class="ui-settings-card-copy">
        <h4 class="m-none text-body font-semibold text-color">{{ $t('settings.addons.danmu.title') }}</h4>
        <p class="m-none text-caption text-muted">{{ $t('settings.addons.danmu.description') }}</p>
      </div>
      <div class="ui-settings-card-meta">
        <ToggleSwitch
          :key="toggleKey"
          :model-value="danmuConfig.enabled"
          input-id="addon-danmu-enabled"
          @update:model-value="handleCardToggle"
        />
      </div>
    </div>

    <div class="ui-settings-card-body">
      <p class="m-none text-caption text-muted">{{ $t('settings.addons.danmu.count', { directories: selectedDirectoryCount, providers: selectedProviderCount }) }}</p>
      <p v-if="!isDoubanBrowseSource" class="m-none text-caption text-muted">{{ $t('settings.addons.danmu.doubanOnly') }}</p>
    </div>

    <div class="ui-settings-card-actions">
      <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="openDialog" />
    </div>

    <ConfigDialog
      v-model:visible="dialogVisible"
      :title="$t('settings.addons.danmu.editTitle')"
      size="md"
      :intro="$t('settings.addons.danmu.intro')"
    >
      <div class="flex flex-col gap-container">
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.directories') }}</label>
          <MultiSelect
            v-model="danmuConfig.directory_ids"
            :options="directoryOptions"
            option-label="label"
            option-value="value"
            display="chip"
            :placeholder="$t('settings.addons.danmu.selectDirectories')"
            class="w-full"
          />
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.providers') }}</label>
          <MultiSelect
            v-model="danmuConfig.providers"
            :options="providerOptions"
            option-label="label"
            option-value="value"
            display="chip"
            class="w-full"
          />
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.output') }}</label>
          <div class="flex items-center gap-container flex-wrap">
            <label class="flex items-center gap-inline text-caption text-muted">
              <Checkbox v-model="danmuConfig.output_xml" binary input-id="danmu-output-xml" />
              <span>{{ $t('settings.addons.danmu.outputXml') }}</span>
            </label>
            <label class="flex items-center gap-inline text-caption text-muted">
              <Checkbox v-model="danmuConfig.output_ass" binary input-id="danmu-output-ass" />
              <span>{{ $t('settings.addons.danmu.outputAss') }}</span>
            </label>
          </div>
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.backfill') }}</label>
          <div class="flex flex-col gap-item">
            <div class="flex items-center gap-item">
              <ToggleSwitch v-model="danmuConfig.backfill_enabled" input-id="danmu-backfill-enabled" />
              <span class="text-muted-size font-muted text-muted">
                {{ danmuConfig.backfill_enabled ? $t('common.enabled') : $t('common.disabled') }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="danmuConfig.backfill_enabled" class="ui-dialog-grid">
          <div class="ui-dialog-section">
            <label for="danmu-backfill-interval" class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.interval') }}</label>
            <InputNumber
              v-model="backfillIntervalHours"
              input-id="danmu-backfill-interval"
              class="w-full"
              :suffix="$t('settings.addons.danmu.hoursSuffix')"
              :min="1"
              :max="8760"
            />
          </div>
          <div class="ui-dialog-section">
            <label for="danmu-backfill-recent-days" class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.recentDays') }}</label>
            <InputNumber
              v-model="danmuConfig.backfill_recent_days"
              input-id="danmu-backfill-recent-days"
              class="w-full"
              :suffix="$t('settings.addons.danmu.daysSuffix')"
              :min="1"
            />
          </div>
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.addons.danmu.preview') }}</label>
          <div class="danmu-preview" :class="previewAreaClass" :style="previewStyle">
            <div
              v-for="line in previewLines"
              :key="`${previewAnimationKey}-${line.index}`"
              class="danmu-preview-line"
              :style="line.style"
            >
              {{ line.text }}
            </div>
          </div>
        </div>

        <div class="flex flex-col gap-container">
          <div class="ui-dialog-section">
            <div class="danmu-control-header">
              <label for="danmu-font-size" class="ui-dialog-item-title">{{ $t('settings.addons.danmu.fontSize') }}</label>
              <InputNumber
                v-model="danmuConfig.font_size"
                input-id="danmu-font-size"
                class="danmu-control-number"
                :min="18"
                :max="96"
              />
            </div>
            <Slider v-model="danmuConfig.font_size" :min="18" :max="96" :step="2" />
          </div>
          <div class="ui-dialog-section">
            <div class="danmu-control-header">
              <label for="danmu-scroll-duration" class="ui-dialog-item-title">{{ $t('settings.addons.danmu.scrollDuration') }}</label>
              <InputNumber
                v-model="danmuConfig.scroll_duration_seconds"
                input-id="danmu-scroll-duration"
                class="danmu-control-number"
                :min="5"
                :max="35"
              />
            </div>
            <Slider v-model="danmuConfig.scroll_duration_seconds" :min="5" :max="35" :step="1" />
          </div>
          <div class="ui-dialog-section">
            <div class="danmu-control-header">
              <label for="danmu-opacity" class="ui-dialog-item-title">{{ $t('settings.addons.danmu.opacity') }}</label>
              <InputNumber
                v-model="danmuConfig.font_opacity_percent"
                input-id="danmu-opacity"
                class="danmu-control-number"
                suffix="%"
                :min="30"
                :max="100"
              />
            </div>
            <Slider v-model="danmuConfig.font_opacity_percent" :min="30" :max="100" :step="5" />
          </div>
          <div class="ui-dialog-section">
            <div class="danmu-control-header">
              <label for="danmu-density" class="ui-dialog-item-title">{{ $t('settings.addons.danmu.density') }}</label>
              <InputNumber
                v-model="danmuConfig.density_percent"
                input-id="danmu-density"
                class="danmu-control-number"
                suffix="%"
                :min="10"
                :max="100"
              />
            </div>
            <p class="m-none text-caption text-muted">{{ $t('settings.addons.danmu.densityHint') }}</p>
            <Slider v-model="danmuConfig.density_percent" :min="10" :max="100" :step="10" />
          </div>
          <div class="ui-dialog-section">
            <div class="danmu-control-header">
              <label class="ui-dialog-item-title">{{ $t('settings.addons.danmu.displayArea') }}</label>
              <SelectButton
                v-model="danmuConfig.display_area"
                :options="displayAreaOptions"
                option-label="label"
                option-value="value"
                :allow-empty="false"
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="closeDialog" />
        <Button :label="$t('common.save')" severity="primary" @click="saveConfig" />
      </template>
    </ConfigDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import MultiSelect from 'primevue/multiselect'
import SelectButton from 'primevue/selectbutton'
import Slider from 'primevue/slider'
import ToggleSwitch from 'primevue/toggleswitch'

import { getDirectories, saveAddons } from '@/api/config'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
  servicesConfig: {
    type: Object,
    required: true,
  },
})

const notification = useNotificationStore()
const { t } = useI18n()
const dialogVisible = ref(false)
const toggleKey = ref(0)
const directories = ref([])

const providerOptions = computed(() => [
  { label: t('settings.addons.danmu.iqiyi'), value: 'iqiyi' },
  { label: t('settings.addons.danmu.bilibili'), value: 'bilibili' },
  { label: t('settings.addons.danmu.youku'), value: 'youku' },
  { label: t('settings.addons.danmu.qq'), value: 'qq' },
])

const displayAreaOptions = computed(() => [
  { label: t('settings.addons.danmu.topArea'), value: 'top' },
  { label: t('settings.addons.danmu.fullArea'), value: 'full' },
])

function ensureDanmuConfig() {
  if (!props.config.addons.danmu) {
    props.config.addons.danmu = {
      enabled: false,
      directory_ids: [],
      providers: ['iqiyi', 'bilibili', 'youku', 'qq'],
      backfill_enabled: true,
      backfill_interval_seconds: 21600,
      backfill_recent_days: 30,
      backfill_missing_window_days: 90,
      output_xml: true,
      output_ass: true,
      font_size: 60,
      font_opacity_percent: 80,
      scroll_duration_seconds: 20,
      density_percent: 20,
      display_area: 'top',
    }
  }
  if (!Array.isArray(props.config.addons.danmu.directory_ids)) {
    props.config.addons.danmu.directory_ids = []
  }
  if (!Array.isArray(props.config.addons.danmu.providers)) {
    props.config.addons.danmu.providers = ['iqiyi', 'bilibili', 'youku', 'qq']
  }
  if (props.config.addons.danmu.backfill_enabled !== false) {
    props.config.addons.danmu.backfill_enabled = true
  }
  if (!props.config.addons.danmu.backfill_interval_seconds) {
    props.config.addons.danmu.backfill_interval_seconds = 21600
  }
  if (!props.config.addons.danmu.backfill_recent_days) {
    props.config.addons.danmu.backfill_recent_days = 30
  }
  if (!props.config.addons.danmu.backfill_missing_window_days) {
    props.config.addons.danmu.backfill_missing_window_days = 90
  }
  if (!props.config.addons.danmu.font_size) {
    props.config.addons.danmu.font_size = 60
  }
  if (!props.config.addons.danmu.font_opacity_percent) {
    props.config.addons.danmu.font_opacity_percent = 80
  }
  if (!props.config.addons.danmu.scroll_duration_seconds) {
    props.config.addons.danmu.scroll_duration_seconds = 20
  }
  if (!props.config.addons.danmu.density_percent) {
    props.config.addons.danmu.density_percent = 20
  }
  if (!['top', 'full'].includes(props.config.addons.danmu.display_area)) {
    props.config.addons.danmu.display_area = 'top'
  }
}

ensureDanmuConfig()

function clampNumber(value, fallback, min, max) {
  const numberValue = Number(value || fallback)
  if (!Number.isFinite(numberValue)) {
    return fallback
  }
  return Math.min(Math.max(numberValue, min), max)
}

function normalizeDanmuVisualConfig() {
  danmuConfig.value.backfill_interval_seconds = clampNumber(danmuConfig.value.backfill_interval_seconds, 21600, 3600, 31536000)
  danmuConfig.value.backfill_recent_days = clampNumber(danmuConfig.value.backfill_recent_days, 30, 1, 3650)
  danmuConfig.value.backfill_missing_window_days = clampNumber(danmuConfig.value.backfill_missing_window_days, 90, 1, 3650)
  danmuConfig.value.font_size = clampNumber(danmuConfig.value.font_size, 60, 18, 96)
  danmuConfig.value.font_opacity_percent = clampNumber(danmuConfig.value.font_opacity_percent, 80, 30, 100)
  danmuConfig.value.scroll_duration_seconds = clampNumber(danmuConfig.value.scroll_duration_seconds, 20, 5, 35)
  danmuConfig.value.density_percent = clampNumber(danmuConfig.value.density_percent, 20, 10, 100)
  if (!['top', 'full'].includes(danmuConfig.value.display_area)) {
    danmuConfig.value.display_area = 'top'
  }
}

const danmuConfig = computed(() => props.config.addons.danmu)
const selectedDirectoryCount = computed(() => danmuConfig.value.directory_ids.length)
const selectedProviderCount = computed(() => danmuConfig.value.providers.length)
const isDoubanBrowseSource = computed(() => props.servicesConfig?.browse_source === 'douban')
const backfillIntervalHours = computed({
  get: () => Math.max(Math.round(Number(danmuConfig.value.backfill_interval_seconds || 21600) / 3600), 1),
  set: (value) => {
    const hours = clampNumber(value, 6, 1, 8760)
    danmuConfig.value.backfill_interval_seconds = hours * 3600
  },
})
const previewFontSize = computed(() => Math.min(Math.max(Number(danmuConfig.value.font_size || 60), 18), 96))
const previewOpacity = computed(() => Math.min(Math.max(Number(danmuConfig.value.font_opacity_percent || 80), 30), 100))
const previewDuration = computed(() => Math.min(Math.max(Number(danmuConfig.value.scroll_duration_seconds || 20), 5), 35))
const previewDensity = computed(() => Math.min(Math.max(Number(danmuConfig.value.density_percent || 20), 10), 100))
const previewDisplayArea = computed(() => (danmuConfig.value.display_area === 'full' ? 'full' : 'top'))
const previewAnimationKey = computed(() => `${previewFontSize.value}-${previewOpacity.value}-${previewDuration.value}-${previewDensity.value}-${previewDisplayArea.value}`)
const previewAreaClass = computed(() => (previewDisplayArea.value === 'full' ? 'is-full-area' : 'is-top-area'))
const previewStyle = computed(() => ({
  '--danmu-preview-font-size': `${previewFontSize.value}px`,
  '--danmu-preview-opacity': previewOpacity.value / 100,
  '--danmu-preview-duration': `${previewDuration.value}s`,
}))
const previewLines = computed(() => {
  const count = Math.max(Math.ceil(previewDensity.value / 25), 1)
  const maxTop = previewDisplayArea.value === 'full' ? 76 : 38
  return Array.from({ length: count }, (_, index) => ({
    index,
    text: index === 0 ? t('settings.addons.danmu.previewLine') : t('settings.addons.danmu.densityPreview'),
    style: {
      top: `${18 + ((maxTop - 18) / Math.max(count - 1, 1)) * index}%`,
      animationDelay: `${index * -1.2}s`,
    },
  }))
})
const directoryOptions = computed(() => (
  directories.value
    .filter((directory) => directory.enabled)
    .map((directory) => ({
      label: `${directory.name || directory.id} · ${directory.media_type || 'media'}`,
      value: directory.id,
    }))
))

async function loadDirectories() {
  try {
    const payload = await getDirectories()
    directories.value = payload?.directories || []
  } catch {
    directories.value = []
  }
}

function openDialog() {
  dialogVisible.value = true
  loadDirectories()
}

function closeDialog() {
  dialogVisible.value = false
}

async function persistAddons() {
  normalizeDanmuVisualConfig()
  const savedAddons = await saveAddons(props.config.addons)
  if (savedAddons?.danmu) {
    props.config.addons.danmu = savedAddons.danmu
  }
}

async function handleCardToggle(enabled) {
  const previous = danmuConfig.value.enabled
  danmuConfig.value.enabled = !!enabled
  try {
    await persistAddons()
    notification.success(enabled ? t('settings.addons.danmu.enabled') : t('settings.addons.danmu.disabled'))
  } catch {
    danmuConfig.value.enabled = previous
    toggleKey.value += 1
    notification.error(t('settings.addons.danmu.saveFailed'))
  }
}

async function saveConfig() {
  if (!danmuConfig.value.output_xml && !danmuConfig.value.output_ass) {
    notification.warn(t('settings.addons.danmu.outputRequired'))
    return
  }
  try {
    await persistAddons()
    notification.success(t('settings.addons.danmu.saved'))
    closeDialog()
  } catch {
    notification.error(t('settings.addons.danmu.saveFailed'))
  }
}

onMounted(loadDirectories)
</script>

<style scoped>
.danmu-preview {
  position: relative;
  height: 8rem;
  overflow: hidden;
  border: 1px solid var(--surface-border);
  border-radius: var(--border-radius);
  background:
    linear-gradient(180deg, rgb(18 24 38 / 76%), rgb(15 18 28 / 92%)),
    var(--surface-900);
}

.danmu-preview.is-top-area::after {
  position: absolute;
  inset: 50% 0 auto;
  height: 1px;
  content: "";
  background: rgb(255 255 255 / 20%);
}

.danmu-preview-line {
  position: absolute;
  top: 2rem;
  left: 100%;
  white-space: nowrap;
  font-size: var(--danmu-preview-font-size);
  line-height: 1;
  font-weight: 700;
  color: white;
  opacity: var(--danmu-preview-opacity);
  text-shadow:
    0 1px 2px rgb(0 0 0 / 90%),
    0 0 4px rgb(0 0 0 / 80%);
  animation: danmu-preview-scroll var(--danmu-preview-duration) linear infinite;
}

.danmu-control-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-item);
  margin-bottom: var(--spacing-item);
}

.danmu-control-number {
  width: 7rem;
}

@keyframes danmu-preview-scroll {
  from {
    transform: translateX(0);
  }

  to {
    transform: translateX(calc(-100% - 100vw));
  }
}
</style>
