<template>
  <Toast position="top-right">
    <template #message="{ message }">
      <div class="flex min-w-0 flex-1 flex-col gap-tight">
        <span v-if="message.summary" class="font-medium leading-none">{{ message.summary }}</span>
        <div v-if="message.detail" class="text-small text-muted break-words">{{ message.detail }}</div>
      </div>
    </template>
  </Toast>
  <div class="app-shell min-h-screen flex flex-col relative">
    <header class="app-shell-header fixed top-0 inset-x-0 z-40 w-full border-b border-separator bg-surface/80 backdrop-blur">
      <div class="relative w-full max-w-layout mx-auto px-container h-header">
        <div class="absolute inset-y-0 left-container flex items-center gap-container min-w-0">
          <router-link
            to="/discover"
            class="flex items-center min-w-0 text-primary hover:text-primary-emphasis transition-colors shrink-0"
          >
            <span class="ui-brand-wordmark text-heading leading-none">Aethera</span>
          </router-link>

          <div
            v-if="!isAuthPage && !isHomePage"
            class="hidden lg:flex items-center w-form-sm"
          >
            <SearchBox
              v-model="headerSearchQuery"
              class="ui-header-search"
              size="medium"
              field-semantic="form"
              :placeholder="$t('app.search.placeholder')"
              :loading="false"
              :show-prefix-icon="true"
              :show-button="false"
              @search="handleHeaderSearch"
            />
          </div>
        </div>

        <div v-if="!isAuthPage" class="absolute inset-y-0 right-container flex items-center gap-container">
          <Button
            v-tooltip.right="alertCenterTooltip"
            icon="pi pi-bell"
            :label="displayAlertCount > 0 ? (displayAlertCount > 99 ? '99+' : String(displayAlertCount)) : undefined"
            text
            :pt="alertButtonPt"
            @click="alertCenterStore.open()"
          />
          <RouterLink
            v-tooltip.right="$t('menu.calendar')"
            to="/calendar"
            :class="[
              'inline-flex items-center justify-center w-control-icon h-control-icon transition-colors duration-200 no-underline',
              route.path === '/calendar' ? 'text-primary' : 'text-muted hover:text-primary'
            ]"
          >
            <i class="pi pi-calendar text-title" />
          </RouterLink>
          <AppMenu />
        </div>
      </div>
    </header>

    <main
      :class="mainClass"
      :style="mainStyle"
    >
      <router-view />
    </main>

    <footer
      class="min-h-footer px-container flex items-center justify-center text-center bg-surface border-t border-t-separator"
    >
      <p class="text-muted">{{ $t('app.footer') }}</p>
    </footer>
    <AlertCenterDialog
      :visible="alertCenterStore.visible"
      @update:visible="alertCenterStore.setVisible"
    />
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import AppMenu from './components/AppMenu.vue'
import AlertCenterDialog from './components/AlertCenterDialog.vue'
import SearchBox from './components/common/SearchBox.vue'
import { useAppShell } from '@/composables/useAppShell'
import { useNotificationStore } from '@/stores/notification'

const toast = useToast()
const notificationStore = useNotificationStore()
const { locale, t } = useI18n()

const {
  route,
  headerSearchQuery,
  displayAlertCount,
  alertButtonPt,
  alertCenterTooltip,
  isAuthPage,
  isHomePage,
  mainClass,
  mainStyle,
  alertCenterStore,
  handleHeaderSearch,
} = useAppShell()

watch(() => notificationStore.notifications.length, (count) => {
  if (!count) return

  for (const notification of notificationStore.drain()) {
    toast.add({
      severity: notification.severity,
      summary: notification.summary,
      detail: notification.detail,
      life: notification.life,
    })
  }
})

watch(
  [() => route.meta?.titleKey, locale],
  ([titleKey]) => {
    const title = titleKey ? t(titleKey) : t('app.brand')
    document.title = title === t('app.brand') ? title : `${title} - ${t('app.brand')}`
  },
  { immediate: true }
)
</script>

<style scoped>
.app-shell {
  padding-left: calc(100vw - 100%);
}

.app-shell-header {
  padding-left: calc(100vw - 100%);
}

.ui-header-search :deep(.p-iconfield) {
  width: 100%;
}

.ui-header-search :deep(.p-inputicon) {
  color: var(--text-muted);
  transition: color var(--p-transition-duration);
}

.ui-header-search :deep(.p-inputtext) {
  background-color: color-mix(in srgb, var(--surface-subtle) 72%, transparent);
  border-color: color-mix(in srgb, var(--border-default) 72%, transparent);
  color: var(--text-default);
  box-shadow: none;
  transition: background-color var(--p-transition-duration), border-color var(--p-transition-duration), color var(--p-transition-duration);
}

.ui-header-search :deep(.p-inputtext::placeholder) {
  color: var(--text-muted);
}

.ui-header-search:hover :deep(.p-inputtext) {
  background-color: color-mix(in srgb, var(--surface-subtle) 84%, var(--surface-card));
  border-color: var(--border-default);
}

.ui-header-search:focus-within :deep(.p-inputicon) {
  color: var(--accent-primary);
}

.ui-header-search:focus-within :deep(.p-inputtext) {
  background-color: var(--surface-card);
  border-color: color-mix(in srgb, var(--accent-primary) 32%, var(--border-default));
}
</style>
