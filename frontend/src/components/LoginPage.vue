<template>
  <div class="w-full min-h-full flex items-center justify-center px-block py-item">
    <div class="w-full max-w-dialog-sm">
      <Card class="w-full">
        <template #title>
          <div class="flex items-baseline justify-between gap-item">
            <span>{{ $t('auth.login') }}</span>
          </div>
        </template>
        <template #content>
          <div class="flex flex-col gap-container">
            <div v-if="authProviders.length > 0" class="flex flex-col gap-item">
              <label class="font-bold">{{ $t('auth.externalLogin') }}</label>
              <div class="grid grid-cols-1 gap-item">
                <Button
                  v-for="provider in authProviders"
                  :key="provider.id"
                  :label="$t('auth.externalProviderLogin', { provider: provider.name })"
                  icon="pi pi-external-link"
                  severity="secondary"
                  outlined
                  :loading="working && activeProviderId === provider.id"
                  @click="handleProviderLogin(provider.id)"
                />
              </div>
            </div>

            <div v-if="authProviders.length > 0" class="border-t border-separator pt-item">
              <p class="m-none text-caption text-muted">{{ $t('auth.localPasswordLogin') }}</p>
            </div>

            <div class="flex flex-col gap-item">
              <label class="font-bold">{{ $t('auth.adminPassword') }}</label>
              <InputText
                v-model="password"
                class="w-full"
                type="password"
                autocomplete="current-password"
                :placeholder="$t('auth.passwordPlaceholder')"
              />
            </div>

            <div class="flex justify-end gap-item pt-item">
              <Button
                :label="$t('auth.login')"
                icon="pi pi-sign-in"
                :loading="working"
                @click="handleLogin"
              />
            </div>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { getAuthProviders, login, startAuthProviderLogin } from '@/api/auth'
import { useNotificationStore } from '@/stores/notification'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const route = useRoute()
const notification = useNotificationStore()
const authStore = useAuthStore()
const { t } = useI18n()

const working = ref(false)
const password = ref('')
const authProviders = ref([])
const activeProviderId = ref('')

const nextPath = computed(() => {
  const raw = route.query.next
  if (typeof raw === 'string' && raw.startsWith('/')) return raw
  return '/discover'
})

async function handleLogin() {
  if (!password.value) return
  working.value = true
  try {
    const data = await login({ username: 'admin', password: password.value })
    authStore.setAuthenticated(true, data?.username || 'admin')
    authStore.clearAuthRequired()
    const bootstrap = await authStore.refreshBootstrapState({ force: true })
    if (bootstrap?.setup_required) {
      router.replace({ path: '/setup', query: { next: nextPath.value } })
      return
    }
    router.replace(nextPath.value)
  } finally {
    working.value = false
  }
}

async function handleProviderLogin(providerId) {
  working.value = true
  activeProviderId.value = providerId
  try {
    const data = await startAuthProviderLogin(providerId, { next_path: nextPath.value })
    if (data?.redirect_url) {
      window.location.assign(data.redirect_url)
      return
    }
    notification.error(t('auth.externalLoginFailed'))
  } catch {
    notification.error(t('auth.externalLoginFailed'))
  } finally {
    working.value = false
    activeProviderId.value = ''
  }
}

onMounted(async () => {
  try {
    const [providers, bootstrap] = await Promise.all([
      getAuthProviders().catch(() => []),
      authStore.refreshBootstrapState({ force: true }).catch(() => null),
    ])
    authProviders.value = providers
    if (bootstrap?.setup_required) {
      router.replace({ path: '/setup', query: { next: nextPath.value } })
      return
    }
    if (bootstrap?.logged_in) {
      router.replace(nextPath.value)
      return
    }
  } catch {
    authProviders.value = []
  }
  if (typeof route.query.error_key === 'string' && route.query.error_key) {
    notification.error(t(route.query.error_key))
    const next = typeof route.query.next === 'string' ? route.query.next : undefined
    router.replace({ path: '/login', query: next ? { next } : {} })
    return
  }
  if (typeof route.query.error === 'string' && route.query.error) {
    notification.error(route.query.error)
    const next = typeof route.query.next === 'string' ? route.query.next : undefined
    router.replace({ path: '/login', query: next ? { next } : {} })
  }
})
</script>
