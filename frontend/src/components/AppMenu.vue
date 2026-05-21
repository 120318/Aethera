<template>
  <div class="relative flex items-center">
    <Button
      v-tooltip.right="$t('menu.label')"
      size="large"
      severity="secondary"
      variant="text"
      :class="[
        'w-control-icon h-control-icon p-none transition-colors duration-200',
        menuVisible ? 'text-primary' : 'text-muted hover:text-color'
      ]"
      @click="toggleMenu"
    >
      <i class="pi pi-bars text-title" />
    </Button>

    <TieredMenu
      ref="menuRef"
      :model="menuItems"
      popup
      append-to="body"
      @show="menuVisible = true"
      @hide="menuVisible = false"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import TieredMenu from 'primevue/tieredmenu'
import { logout } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useLocaleStore } from '@/stores/locale'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const localeStore = useLocaleStore()
const { t } = useI18n()

const menuRef = ref()
const menuVisible = ref(false)

function setPreference(pref) {
  themeStore.setPreference(pref)
  menuVisible.value = false
  menuRef.value?.hide?.()
}

function setLocale(locale) {
  localeStore.setLocale(locale)
  menuVisible.value = false
  menuRef.value?.hide?.()
}

function toggleMenu(event) {
  menuRef.value?.toggle?.(event)
}

function navigateToRoute(targetRoute, event) {
  if (!event) {
    router.push(targetRoute)
    return
  }

  const isPrimaryClick = event.button === 0
  const hasModifier = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey

  if (!isPrimaryClick || hasModifier) {
    return
  }

  event.preventDefault()
  router.push(targetRoute)
}

function createRouteItem(label, icon, targetRoute) {
  return {
    label,
    icon,
    url: router.resolve(targetRoute).href,
    command: ({ originalEvent }) => navigateToRoute(targetRoute, originalEvent)
  }
}

const menuItems = computed(() => {
  const pref = themeStore.preference
  const themeLabel = pref === 'dark' ? t('theme.dark') : (pref === 'light' ? t('theme.light') : t('theme.auto'))
  const loginRoute = { path: '/login', query: { next: route.fullPath } }

  const base = [
    {
      label: t('theme.current', { label: themeLabel }),
      icon: 'pi pi-palette',
      items: [
        { label: t('theme.lightMode'), icon: 'pi pi-sun', command: () => setPreference('light') },
        { label: t('theme.auto'), icon: 'pi pi-desktop', command: () => setPreference('auto') },
        { label: t('theme.darkMode'), icon: 'pi pi-moon', command: () => setPreference('dark') }
      ]
    },
    {
      label: t('language.current', { label: localeStore.currentLocaleLabel }),
      icon: 'pi pi-language',
      items: localeStore.availableLocales.map((locale) => ({
        label: locale.label,
        icon: locale.value === localeStore.currentLocale ? 'pi pi-check' : 'pi pi-circle',
        command: () => setLocale(locale.value),
      })),
    },
    createRouteItem(t('menu.mediaManagement'), 'pi pi-database', '/media-management'),
    createRouteItem(t('menu.schedulerJobs'), 'pi pi-calendar-clock', '/scheduler-jobs'),
    createRouteItem(t('menu.eventLogs'), 'pi pi-history', '/event-logs'),
    createRouteItem(t('menu.settings'), 'pi pi-cog', '/settings'),
    { separator: true }
  ]

  if (authStore.isAuthenticated) {
    base.push({ label: t('menu.logout'), icon: 'pi pi-sign-out', command: () => doLogout() })
  } else {
    base.push(createRouteItem(t('menu.login'), 'pi pi-sign-in', loginRoute))
  }
  return base
})

async function doLogout() {
  try {
    await logout()
  } finally {
    authStore.setAuthenticated(false)
    router.replace({ path: '/login', query: { next: '/discover' } })
  }
}
</script>
