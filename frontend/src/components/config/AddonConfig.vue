<template>
  <div class="pb-container">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular">
      <div v-if="oidcAuthEnabled" ref="authRef" data-addon-card="auth">
        <AuthAddonCard :config="props.config" />
      </div>
      <div v-if="telegramNotificationsEnabled" ref="notificationsRef" data-addon-card="notifications">
        <NotificationsAddonCard :config="props.config" />
      </div>
      <div ref="danmuRef" data-addon-card="danmu">
        <DanmuAddonCard :config="props.config" :services-config="props.servicesConfig" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import AuthAddonCard from '@/components/config/addons/AuthAddonCard.vue'
import DanmuAddonCard from '@/components/config/addons/DanmuAddonCard.vue'
import NotificationsAddonCard from '@/components/config/addons/NotificationsAddonCard.vue'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  focusAddon: {
    type: String,
    default: '',
  },
  servicesConfig: {
    type: Object,
    required: true,
  },
})

const notificationsRef = ref(null)
const authRef = ref(null)
const danmuRef = ref(null)
const oidcAuthEnabled = import.meta.env.VITE_AETHERA_EXPERIMENTAL_OIDC_AUTH === '1'
const telegramNotificationsEnabled = import.meta.env.VITE_AETHERA_EXPERIMENTAL_TELEGRAM_NOTIFICATIONS === '1'

function focusAddonCard(name) {
  const targets = {
    auth: authRef.value,
    auth_providers: authRef.value,
    notifications: notificationsRef.value,
    telegram: notificationsRef.value,
    danmu: danmuRef.value,
  }
  const target = targets[name]
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(
  () => props.focusAddon,
  async (value) => {
    if (!value) return
    await nextTick()
    focusAddonCard(value)
  },
  { immediate: true },
)
</script>
