<template>
  <div class="ui-settings-card h-full">
    <div class="ui-settings-card-header">
      <div class="ui-settings-card-copy">
        <h4 class="m-none text-body font-semibold text-color">{{ $t('settings.addons.auth.title') }}</h4>
        <p class="m-none text-caption text-muted">{{ $t('settings.addons.auth.description') }}</p>
      </div>
      <div class="ui-settings-card-meta">
        <ToggleSwitch
          :key="toggleKey"
          :model-value="authConfig.enabled"
          input-id="ext-auth-enabled"
          @update:model-value="handleCardToggle"
        />
      </div>
    </div>

    <div class="ui-settings-card-body">
      <p class="m-none text-caption text-muted">{{ $t('settings.addons.auth.count', { count: enabledProviderCount }) }}</p>
    </div>

    <div class="ui-settings-card-actions">
      <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="openDialog" />
    </div>

    <ConfigDialog
      v-model:visible="dialogVisible"
      :title="$t('settings.addons.auth.editTitle')"
      size="lg"
      :intro="$t('settings.addons.auth.intro')"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 gap-container ui-settings-grid-regular">
        <div v-for="provider in authConfig.providers" :key="provider.id" class="ui-settings-card h-full">
          <div class="ui-settings-card-header">
            <div class="ui-settings-card-copy">
              <h4 class="m-none text-body font-semibold text-color">{{ provider.name || $t('settings.addons.auth.unnamedProvider') }}</h4>
              <p class="m-none text-caption text-muted">{{ provider.issuer_url || $t('settings.addons.auth.issuerUnset') }}</p>
            </div>
            <div class="ui-settings-card-meta">
              <AppTag v-if="isDefaultProvider(provider.id)" :value="$t('common.default')" />
              <ToggleSwitch
                :model-value="provider.enabled"
                :input-id="`auth-provider-enabled-${provider.id}`"
                @update:model-value="updateProviderEnabled(provider, $event)"
              />
            </div>
          </div>

          <div class="ui-settings-card-body">
            <div class="flex flex-col gap-inline text-caption text-muted">
              <p class="m-none"><strong class="font-semibold">{{ $t('common.type') }}:</strong> {{ provider.type }}</p>
              <p class="m-none"><strong class="font-semibold">{{ $t('settings.addons.auth.adminEmails') }}</strong> {{ formatAuthProviderItems(provider.admin_emails, $t('common.unset')) }}</p>
              <p class="m-none"><strong class="font-semibold">{{ $t('settings.addons.auth.scopes') }}:</strong> {{ formatAuthProviderItems(provider.scopes, $t('common.unset')) }}</p>
            </div>
          </div>

          <div class="ui-settings-card-actions">
            <Button :label="$t('common.edit')" severity="primary" size="small" @click="openProviderDialog(provider)" />
            <Button
              v-if="!isDefaultProvider(provider.id)"
              :label="$t('common.setDefault')"
              severity="secondary"
              outlined
              size="small"
              @click="setDefaultProvider(provider.id)"
            />
            <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="removeProvider(provider.id)" />
          </div>
        </div>

        <button type="button" class="ui-settings-add-card" @click="openProviderDialog()">
          <i class="pi pi-plus text-title" aria-hidden="true"></i>
          <span class="text-body font-medium">{{ $t('settings.addons.auth.addProvider') }}</span>
        </button>
      </div>
    </ConfigDialog>

    <ConfigDialog
      v-model:visible="providerDialogVisible"
      :title="editingProviderId ? $t('settings.addons.auth.editProvider') : $t('settings.addons.auth.addProviderTitle')"
      size="lg"
    >
      <div class="flex flex-col gap-container">
        <div class="ui-dialog-grid">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.name') }}</label>
            <InputText v-model="providerForm.name" class="w-full" :placeholder="$t('settings.addons.auth.namePlaceholder')" />
          </div>
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block">{{ $t('common.type') }}</label>
            <Select v-model="providerForm.type" :options="providerTypeOptions" option-label="label" option-value="value" class="w-full" />
          </div>
        </div>

        <template v-if="providerForm.type === 'oidc'">
          <div class="ui-dialog-grid">
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.issuerUrl') }}</label>
              <InputText v-model="providerForm.issuer_url" class="w-full" :placeholder="$t('settings.addons.auth.issuerUrlPlaceholder')" />
            </div>
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.clientId') }}</label>
              <InputText v-model="providerForm.client_id" class="w-full" />
            </div>
          </div>

          <div class="ui-dialog-grid">
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.clientSecret') }}</label>
              <InputText v-model="providerForm.client_secret" class="w-full" />
            </div>
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.scopes') }}</label>
              <InputText v-model="scopesInput" class="w-full" :placeholder="$t('settings.addons.auth.scopesPlaceholder')" />
            </div>
          </div>

          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.adminEmailAllowlist') }}</label>
            <InputText v-model="adminEmailsInput" class="w-full" :placeholder="$t('settings.addons.auth.adminEmailsPlaceholder')" />
          </div>
        </template>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="closeProviderDialog" />
        <Button :label="$t('settings.addons.auth.saveProvider')" severity="primary" @click="saveProvider" />
      </template>
    </ConfigDialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'

import { saveAddons } from '@/api/config'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import {
  assignAuthProviderForm,
  cloneAuthProvider,
  cloneAuthProviderList,
  createEmptyAuthProvider,
  formatAuthProviderItems,
  normalizeCommaSeparatedItems,
} from '@/components/config/addons/authProvidersSupport'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
})

const notification = useNotificationStore()
const { t } = useI18n()
const dialogVisible = ref(false)
const providerDialogVisible = ref(false)
const editingProviderId = ref('')
const scopesInput = ref('openid, profile, email')
const adminEmailsInput = ref('')
const toggleKey = ref(0)

const providerTypeOptions = computed(() => [
  { label: t('settings.addons.auth.oidc'), value: 'oidc' },
])

const providerForm = reactive(createEmptyAuthProvider())

function ensureAuthConfig() {
  if (!props.config.addons.auth) {
    props.config.addons.auth = {
      enabled: false,
      default_provider_id: null,
      providers: [],
    }
  }
  if (!Array.isArray(props.config.addons.auth.providers)) {
    props.config.addons.auth.providers = []
  }
}

ensureAuthConfig()

const authConfig = computed(() => props.config.addons.auth)

const enabledProviderCount = computed(() => authConfig.value.providers.filter((provider) => provider.enabled).length)

function resetProviderForm() {
  assignAuthProviderForm(providerForm, createEmptyAuthProvider(), scopesInput, adminEmailsInput)
}

function openDialog() {
  dialogVisible.value = true
}

function isDefaultProvider(providerId) {
  return authConfig.value.default_provider_id === providerId
}

function openProviderDialog(provider = null) {
  if (provider) {
    editingProviderId.value = provider.id
    assignAuthProviderForm(providerForm, provider, scopesInput, adminEmailsInput)
  } else {
    editingProviderId.value = ''
    resetProviderForm()
  }
  providerDialogVisible.value = true
}

function closeProviderDialog() {
  providerDialogVisible.value = false
}

async function persistAddons() {
  const savedAddons = await saveAddons(props.config.addons)
  if (savedAddons?.auth) {
    props.config.addons.auth = savedAddons.auth
  }
}

async function handleCardToggle(nextValue) {
  const previous = authConfig.value.enabled
  authConfig.value.enabled = !!nextValue
  try {
    await persistAddons()
    notification.success(nextValue ? t('settings.addons.auth.enabled') : t('settings.addons.auth.disabled'))
    if (nextValue) {
      openDialog()
    }
  } catch {
    authConfig.value.enabled = previous
    toggleKey.value += 1
    notification.error(t('settings.addons.auth.saveFailed'))
  }
}

async function setDefaultProvider(providerId) {
  const previous = authConfig.value.default_provider_id
  authConfig.value.default_provider_id = providerId || null
  try {
    await persistAddons()
    notification.success(t('settings.addons.auth.defaultUpdated'))
  } catch {
    authConfig.value.default_provider_id = previous
    notification.error(t('settings.addons.auth.defaultSaveFailed'))
  }
}

async function updateProviderEnabled(provider, nextValue) {
  const providerIndex = authConfig.value.providers.findIndex((item) => item.id === provider.id)
  if (providerIndex < 0) {
    return
  }

  const previousProvider = cloneAuthProvider(authConfig.value.providers[providerIndex])

  authConfig.value.providers.splice(providerIndex, 1, {
    ...authConfig.value.providers[providerIndex],
    enabled: !!nextValue,
  })

  try {
    await persistAddons()
    notification.success(nextValue ? t('settings.addons.auth.providerEnabled') : t('settings.addons.auth.providerDisabled'))
  } catch {
    authConfig.value.providers.splice(providerIndex, 1, previousProvider)
    notification.error(t('settings.addons.auth.providerStatusSaveFailed'))
  }
}

async function removeProvider(providerId) {
  const originalProviders = [...authConfig.value.providers]
  const originalDefaultProviderId = authConfig.value.default_provider_id
  authConfig.value.providers = authConfig.value.providers.filter((provider) => provider.id !== providerId)
  if (authConfig.value.default_provider_id === providerId) {
    authConfig.value.default_provider_id = authConfig.value.providers[0]?.id || null
  }
  try {
    await persistAddons()
    notification.success(t('settings.addons.auth.providerDeleted'))
  } catch {
    authConfig.value.providers = originalProviders
    authConfig.value.default_provider_id = originalDefaultProviderId
    notification.error(t('settings.addons.auth.providerDeleteFailed'))
  }
}

async function saveProvider() {
  const nextScopes = normalizeCommaSeparatedItems(scopesInput.value)
  const nextAdminEmails = normalizeCommaSeparatedItems(adminEmailsInput.value).map((item) => item.toLowerCase())
  if (!providerForm.name.trim() || !providerForm.issuer_url.trim() || !providerForm.client_id.trim() || !providerForm.client_secret.trim()) {
    notification.warn(t('settings.addons.auth.providerInfoRequired'))
    return
  }
  if (nextAdminEmails.length === 0) {
    notification.warn(t('settings.addons.auth.adminEmailRequired'))
    return
  }

  const nextProvider = {
    id: providerForm.id,
    type: providerForm.type,
    name: providerForm.name.trim(),
    enabled: providerForm.enabled,
    issuer_url: providerForm.issuer_url.trim(),
    client_id: providerForm.client_id.trim(),
    client_secret: providerForm.client_secret.trim(),
    scopes: nextScopes.length > 0 ? nextScopes : ['openid', 'profile', 'email'],
    discovery_enabled: providerForm.discovery_enabled,
    authorization_endpoint: providerForm.authorization_endpoint,
    token_endpoint: providerForm.token_endpoint,
    userinfo_endpoint: providerForm.userinfo_endpoint,
    jwks_uri: providerForm.jwks_uri,
    claim_mappings: providerForm.claim_mappings,
    admin_emails: nextAdminEmails,
    allow_local_fallback: providerForm.allow_local_fallback,
  }

  const previousProviders = cloneAuthProviderList(authConfig.value.providers)
  const previousDefaultProviderId = authConfig.value.default_provider_id

  const existingIndex = authConfig.value.providers.findIndex((provider) => provider.id === nextProvider.id)
  if (existingIndex >= 0) {
    authConfig.value.providers.splice(existingIndex, 1, nextProvider)
  } else {
    authConfig.value.providers.push(nextProvider)
  }

  if (!authConfig.value.default_provider_id) {
    authConfig.value.default_provider_id = nextProvider.id
  }

  try {
    await persistAddons()
    notification.success(editingProviderId.value ? t('settings.addons.auth.providerUpdated') : t('settings.addons.auth.providerAdded'))
    closeProviderDialog()
  } catch {
    authConfig.value.providers.splice(0, authConfig.value.providers.length, ...previousProviders)
    authConfig.value.default_provider_id = previousDefaultProviderId
    notification.error(t('settings.addons.auth.providerSaveFailed'))
  }
}
</script>
