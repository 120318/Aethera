<template>
  <div class="ui-settings-card h-full">
    <div class="ui-settings-card-header">
      <div class="ui-settings-card-copy">
        <h4 class="m-none text-body font-semibold text-color">{{ $t('settings.addons.subtitles.title') }}</h4>
        <p class="m-none text-caption text-muted">{{ $t('settings.addons.subtitles.description') }}</p>
      </div>
      <ToggleSwitch :model-value="subtitleConfig.enabled" input-id="addon-subtitles-enabled" @update:model-value="toggleEnabled" />
    </div>
    <div class="ui-settings-card-body">
      <p class="m-none text-caption text-muted">{{ $t('settings.addons.subtitles.providerHint') }}</p>
    </div>
    <div class="ui-settings-card-actions">
      <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="dialogVisible = true" />
    </div>

    <ConfigDialog v-model:visible="dialogVisible" :title="$t('settings.addons.subtitles.editTitle')" size="md">
      <div class="flex flex-col gap-container">
        <div class="ui-dialog-section">
          <label for="subtitles-api-key" class="ui-dialog-item-title block">{{ $t('settings.addons.subtitles.apiKey') }}</label>
          <Password v-model="subtitleConfig.api_key" input-id="subtitles-api-key" :feedback="false" toggle-mask class="w-full" input-class="w-full" />
        </div>
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.addons.subtitles.languages') }}</label>
          <MultiSelect v-model="subtitleConfig.languages" :options="languageOptions" option-label="label" option-value="value" display="chip" class="w-full" />
        </div>
        <div class="ui-dialog-section">
          <div class="flex items-center gap-item">
            <ToggleSwitch v-model="subtitleConfig.auto_fill_enabled" input-id="subtitles-auto-fill" />
            <span class="text-caption text-muted">{{ $t('settings.addons.subtitles.autoFill') }}</span>
          </div>
          <p class="m-none text-caption text-muted">{{ $t('settings.addons.subtitles.autoFillHint') }}</p>
        </div>
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="dialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" @click="save" />
      </template>
    </ConfigDialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'

import { saveAddons } from '@/api/config'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({ config: { type: Object, required: true } })
const { t } = useI18n()
const notification = useNotificationStore()
const dialogVisible = ref(false)

function ensureConfig() {
  if (!props.config.addons.subtitles) {
    props.config.addons.subtitles = {
      enabled: false,
      provider: 'opensubtitles',
      api_key: '',
      languages: ['zh-cn', 'zh-tw', 'en'],
      auto_fill_enabled: false,
    }
  }
  return props.config.addons.subtitles
}

const subtitleConfig = computed(() => ensureConfig())
const languageOptions = computed(() => [
  { label: t('settings.addons.subtitles.simplifiedChinese'), value: 'zh-cn' },
  { label: t('settings.addons.subtitles.traditionalChinese'), value: 'zh-tw' },
  { label: t('settings.addons.subtitles.english'), value: 'en' },
])

async function persist() {
  const updated = await saveAddons(props.config.addons)
  Object.assign(props.config.addons, updated)
  notification.success(t('settings.addons.subtitles.saved'))
}

async function toggleEnabled(enabled) {
  subtitleConfig.value.enabled = enabled
  await persist()
}

async function save() {
  await persist()
  dialogVisible.value = false
}
</script>
