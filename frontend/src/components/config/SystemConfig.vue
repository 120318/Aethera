<template>
  <div class="grid grid-cols-1 gap-container">
    <div class="ui-settings-card">
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.general') }}</h4>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingGeneral" @click="saveGeneralConfigSection" />
      </div>
      <div class="ui-settings-card-body">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="ui-dialog-section">
            <label for="system-auth-session-ttl" class="ui-dialog-item-title block">{{ $t('settings.system.sessionTtl') }}</label>
            <InputNumber
              v-model="auth.session_ttl_seconds"
              input-id="system-auth-session-ttl"
              class="w-full"
              :min="0"
            />
            <p class="m-none mt-inline text-tiny text-muted">{{ $t('settings.system.sessionTtlHint') }}</p>
          </div>

          <div class="ui-dialog-section">
            <label for="system-public-base-url" class="ui-dialog-item-title block">{{ $t('settings.system.publicBaseUrl') }}</label>
            <InputText
              v-model="general.public_base_url"
              input-id="system-public-base-url"
              :placeholder="$t('settings.system.publicBaseUrlPlaceholder')"
              class="w-full"
            />
          </div>
        </div>

        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
            <div v-for="field in loggingFields" :key="field.key" class="ui-dialog-section">
              <div class="flex items-center gap-micro mb-item">
                <label :for="field.key" class="font-bold text-color">{{ field.label }}</label>
                <Button
                  v-if="field.hint"
                  v-tooltip.top="field.hint"
                  icon="pi pi-info-circle"
                  severity="secondary"
                  variant="text"
                  size="small"
                  :aria-label="$t('settings.system.viewHint')"
                />
              </div>
              <component
                :is="field.component"
                v-model="field.model[field.prop]"
                :input-id="field.key"
                class="w-full"
                v-bind="field.props || {}"
              />
            </div>
          </div>
        </div>

        <div class="ui-dialog-section">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-item">
            <div class="ui-dialog-section">
              <label for="system-account-old-password" class="ui-dialog-item-title block">{{ $t('settings.system.oldPassword') }}</label>
              <InputText v-model="oldPassword" input-id="system-account-old-password" type="password" :placeholder="$t('settings.system.oldPasswordPlaceholder')" class="w-full" />
            </div>
            <div class="ui-dialog-section">
              <label for="system-account-new-password" class="ui-dialog-item-title block">{{ $t('settings.system.newPassword') }}</label>
              <InputText v-model="newPassword" input-id="system-account-new-password" type="password" :placeholder="$t('settings.system.newPasswordPlaceholder')" class="w-full" />
            </div>
            <div class="ui-dialog-section">
              <label for="system-account-new-password-confirm" class="ui-dialog-item-title block">{{ $t('settings.system.confirmNewPassword') }}</label>
              <InputText v-model="newPasswordConfirm" input-id="system-account-new-password-confirm" type="password" :placeholder="$t('settings.system.confirmNewPasswordPlaceholder')" class="w-full" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="ui-settings-card">
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.download') }}</h4>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingDownload" @click="saveDownloadConfigSection" />
      </div>
      <div class="ui-settings-card-body">
        <div class="ui-dialog-section w-full md:w-1/2">
          <label for="system-download-default-tag" class="ui-dialog-item-title block">{{ $t('settings.system.downloadTag') }}</label>
          <p class="m-none text-caption text-muted">{{ $t('settings.system.downloadTagHint') }}</p>
          <InputText
            v-model="download.default_tag"
            input-id="system-download-default-tag"
            :placeholder="$t('settings.system.downloadTagPlaceholder')"
            class="w-full"
          />
        </div>
      </div>
    </div>

    <div class="ui-settings-card">
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.subscriptionDiscovery') }}</h4>
          <p class="m-none text-caption text-muted">{{ $t('settings.system.subscriptionDiscoveryDescription') }}</p>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingScheduler" @click="saveSchedulerConfigSection" />
      </div>
      <div class="ui-settings-card-body">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="ui-dialog-section">
            <label for="system-subscription-discovery-mode" class="ui-dialog-item-title block">{{ $t('settings.system.subscriptionDiscoveryMode') }}</label>
            <Select
              v-model="scheduler.subscription_resource_discovery_mode"
              input-id="system-subscription-discovery-mode"
              :options="subscriptionDiscoveryOptions"
              option-label="label"
              option-value="value"
              class="w-full"
            />
          </div>
          <div class="ui-dialog-section">
            <label for="system-subscription-sweep-interval" class="ui-dialog-item-title block">{{ $t('settings.system.subscriptionSweepInterval') }}</label>
            <InputNumber
              v-model="scheduler.subscription_sweep_interval_seconds"
              input-id="system-subscription-sweep-interval"
              class="w-full"
              :min="60"
            />
            <p class="m-none mt-inline text-tiny text-muted">{{ $t('settings.system.subscriptionSweepIntervalHint') }}</p>
          </div>
          <div class="ui-dialog-section">
            <label for="system-subscription-search-interval" class="ui-dialog-item-title block">{{ $t('settings.system.subscriptionSearchInterval') }}</label>
            <InputNumber
              v-model="scheduler.subscription_search_interval_seconds"
              input-id="system-subscription-search-interval"
              class="w-full"
              :min="60"
            />
            <p class="m-none mt-inline text-tiny text-muted">{{ $t('settings.system.subscriptionSearchIntervalHint') }}</p>
          </div>
          <div class="ui-dialog-section">
            <label for="system-subscription-backfill-interval" class="ui-dialog-item-title block">{{ $t('settings.system.subscriptionBackfillInterval') }}</label>
            <InputNumber
              v-model="scheduler.subscription_search_backfill_interval_seconds"
              input-id="system-subscription-backfill-interval"
              class="w-full"
              :min="60"
              :disabled="scheduler.subscription_resource_discovery_mode !== 'rss_with_search_backfill'"
            />
            <p class="m-none mt-inline text-tiny text-muted">{{ $t('settings.system.subscriptionBackfillIntervalHint') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { changePassword, logout } from '@/api/auth'
import { getSystemConfig, saveAuthConfig, saveLoggingConfig, saveSchedulerConfig, saveSystemConfig } from '@/api/config'
import {
  buildNextAuthConfig,
  buildNextGeneralSystemConfig,
  buildNextSchedulerConfig,
  buildNextSystemLoggingConfig,
  buildLoggingFieldDefinitions,
  syncAuthState,
  syncDownloadState,
  syncGeneralState,
  syncLoggingState,
  syncSchedulerState,
} from '@/components/config/systemConfigSupport'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
  applyConfigPatch: {
    type: Function,
    required: true,
  },
})

const notification = useNotificationStore()
const authStore = useAuthStore()
const { t } = useI18n()
const savingGeneral = ref(false)
const savingDownload = ref(false)
const savingScheduler = ref(false)

const general = reactive({
  locale: 'zh-CN',
  public_base_url: '',
})
const download = reactive({
  default_tag: 'Aethera',
})
const scheduler = reactive({
  subscription_sweep_interval_seconds: 300,
  subscription_resource_discovery_mode: 'rss_with_search_backfill',
  subscription_search_interval_seconds: 600,
  subscription_search_backfill_interval_seconds: 3600,
})
const auth = reactive({
  session_ttl_seconds: 86400,
})
const logging = reactive({
  level: 'INFO',
  server_retention_days: 7,
})

const oldPassword = ref('')
const newPassword = ref('')
const newPasswordConfirm = ref('')

const loggingFields = computed(() => buildLoggingFieldDefinitions(t).map((field) => ({ ...field, model: logging })))
const subscriptionDiscoveryOptions = computed(() => [
  { label: t('settings.system.subscriptionDiscoverySearch'), value: 'search' },
  { label: t('settings.system.subscriptionDiscoveryRss'), value: 'rss_with_search_backfill' },
])

syncGeneralState(general, props.config)
syncDownloadState(download, props.config.download)
syncSchedulerState(scheduler, props.config.scheduler)
syncAuthState(auth, props.config.auth)
syncLoggingState(logging, props.config.logging)

watch(
  () => props.config,
  (value) => syncGeneralState(general, value),
  { deep: true },
)

watch(
  () => props.config.download,
  (value) => syncDownloadState(download, value),
  { deep: true },
)

watch(
  () => props.config.scheduler,
  (value) => syncSchedulerState(scheduler, value),
  { deep: true },
)

watch(
  () => props.config.auth,
  (value) => syncAuthState(auth, value),
  { deep: true },
)

watch(
  () => props.config.logging,
  (value) => syncLoggingState(logging, value),
  { deep: true },
)

const saveGeneralConfigSection = async () => {
  const shouldChangePassword = Boolean(oldPassword.value || newPassword.value || newPasswordConfirm.value)
  if (shouldChangePassword && (!oldPassword.value || !newPassword.value || newPassword.value !== newPasswordConfirm.value)) {
    notification.warn(t('settings.system.checkPasswordInput'))
    return
  }

  savingGeneral.value = true
  try {
    const nextSystem = buildNextGeneralSystemConfig(props.config, general, download)
    const nextLogging = buildNextSystemLoggingConfig(props.config, logging).logging
    const nextAuth = buildNextAuthConfig(props.config.auth, {
      session_ttl_seconds: auth.session_ttl_seconds === 0 ? 0 : Number(auth.session_ttl_seconds ?? 86400),
    })
    const loggingLevelChanged = nextLogging.level !== props.config.logging?.level
    const data = await getSystemConfig()
    const currentSystem = data.system || data
    await saveSystemConfig({
      ...currentSystem,
      locale: nextSystem.locale,
      public_base_url: nextSystem.public_base_url,
    })
    await saveLoggingConfig({
      logging: nextLogging,
    })
    await saveAuthConfig(nextAuth)
    props.applyConfigPatch({
      locale: nextSystem.locale,
      public_base_url: nextSystem.public_base_url,
      logging: nextLogging,
      auth: nextAuth,
    })

    if (shouldChangePassword) {
      await changePassword({ old_password: oldPassword.value, new_password: newPassword.value })
      await logout()
      authStore.setAuthenticated(false)
      oldPassword.value = ''
      newPassword.value = ''
      newPasswordConfirm.value = ''
      notification.success(t('settings.system.passwordUpdated'))
      return
    }

    notification.success(t('settings.system.generalSaved'))
    if (loggingLevelChanged) {
      notification.info(t('settings.system.loggingRestartHint'))
    }
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingGeneral.value = false
  }
}

const saveDownloadConfigSection = async () => {
  savingDownload.value = true
  try {
    const nextSystem = buildNextGeneralSystemConfig(props.config, general, download)
    const data = await getSystemConfig()
    const currentSystem = data.system || data
    await saveSystemConfig({
      ...currentSystem,
      download: nextSystem.download,
    })
    props.applyConfigPatch({
      download: nextSystem.download,
    })
    notification.success(t('settings.system.downloadSaved'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingDownload.value = false
  }
}

const saveSchedulerConfigSection = async () => {
  savingScheduler.value = true
  try {
    const nextScheduler = buildNextSchedulerConfig(props.config.scheduler, scheduler)
    await saveSchedulerConfig({ scheduler: nextScheduler })
    props.applyConfigPatch({ scheduler: nextScheduler })
    notification.success(t('settings.system.subscriptionDiscoverySaved'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingScheduler.value = false
  }
}
</script>
