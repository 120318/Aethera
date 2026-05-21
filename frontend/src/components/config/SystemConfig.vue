<template>
  <div class="grid grid-cols-1 gap-container">
    <div class="ui-settings-card">
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.general') }}</h4>
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
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.logging') }}</h4>
          <p class="m-none text-caption text-muted">{{ $t('settings.system.loggingDescription') }}</p>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingLogging" @click="saveSystemLoggingSection" />
      </div>
      <div class="ui-settings-card-body">
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
    </div>

    <div class="ui-settings-card">
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.auth') }}</h4>
          <p class="m-none text-caption text-muted">{{ $t('settings.system.authDescription') }}</p>
        </div>
        <Button :label="$t('common.save')" icon="pi pi-save" :loading="savingAuth" @click="saveAuthConfigSection" />
      </div>
      <div class="ui-settings-card-body">
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
      </div>
    </div>

    <div class="ui-settings-card">
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <h4 class="m-none text-subtitle font-semibold text-color">{{ $t('settings.system.password') }}</h4>
          <p class="m-none text-caption text-muted">{{ $t('settings.system.passwordDescription') }}</p>
        </div>
        <Button
          :label="$t('common.save')"
          icon="pi pi-save"
          :loading="savingPassword"
          @click="handleChangePassword"
        />
      </div>
      <div class="ui-settings-card-body">
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
</template>

<script setup>
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { changePassword, logout } from '@/api/auth'
import { saveAuthConfig, saveDownloadConfig, saveLoggingConfig } from '@/api/config'
import {
  buildNextDownloadConfig,
  buildNextAuthConfig,
  buildNextSystemLoggingConfig,
  buildLoggingFieldDefinitions,
  syncAuthState,
  syncDownloadState,
  syncLoggingState,
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
const savingDownload = ref(false)
const savingLogging = ref(false)
const savingAuth = ref(false)
const savingPassword = ref(false)

const download = reactive({
  default_tag: 'Aethera',
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

syncDownloadState(download, props.config.download)
syncAuthState(auth, props.config.auth)
syncLoggingState(logging, props.config.logging)

watch(
  () => props.config.download,
  (value) => syncDownloadState(download, value),
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

const saveDownloadConfigSection = async () => {
  savingDownload.value = true
  try {
    const nextDownload = buildNextDownloadConfig(props.config.download, download)
    await saveDownloadConfig({
      download: nextDownload,
    })
    props.applyConfigPatch({
      download: nextDownload,
    })
    notification.success(t('settings.system.generalSaved'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingDownload.value = false
  }
}

const saveSystemLoggingSection = async () => {
  savingLogging.value = true
  try {
    const nextSystem = buildNextSystemLoggingConfig(props.config, logging)
    const nextLogging = nextSystem.logging
    await saveLoggingConfig({
      logging: nextLogging,
    })
    props.applyConfigPatch({
      logging: nextLogging,
    })
    notification.success(t('settings.system.loggingSaved'))
    notification.info(t('settings.system.loggingRestartHint'))
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingLogging.value = false
  }
}

const saveAuthConfigSection = async () => {
  savingAuth.value = true
  try {
    const nextAuth = buildNextAuthConfig(props.config.auth, auth)
    await saveAuthConfig({
      enabled: true,
      session_ttl_seconds: auth.session_ttl_seconds === 0 ? 0 : Number(auth.session_ttl_seconds ?? 86400),
    })
    notification.success(t('settings.system.authSaved'))
    props.applyConfigPatch({ auth: nextAuth })
  } catch (error) {
    notification.error(t('settings.system.saveFailed', { message: error.message || error }))
  } finally {
    savingAuth.value = false
  }
}

const handleChangePassword = async () => {
  if (!oldPassword.value || !newPassword.value || newPassword.value !== newPasswordConfirm.value) {
    notification.warn(t('settings.system.checkPasswordInput'))
    return
  }
  savingPassword.value = true
  try {
    await changePassword({ old_password: oldPassword.value, new_password: newPassword.value })
    await logout()
    authStore.setAuthenticated(false)
    notification.success(t('settings.system.passwordUpdated'))
    oldPassword.value = ''
    newPassword.value = ''
    newPasswordConfirm.value = ''
  } catch (error) {
    notification.error(t('settings.system.updateFailed', { message: error.message || error }))
  } finally {
    savingPassword.value = false
  }
}
</script>
