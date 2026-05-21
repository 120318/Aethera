<template>
  <section class="w-full max-w-layout mx-auto flex flex-col gap-section">
    <div class="ui-page-header">
      <div class="ui-page-copy">
        <h1 class="text-heading font-semibold text-color">{{ $t('eventLogs.title') }}</h1>
        <p class="text-muted text-caption">{{ $t('eventLogs.description') }}</p>
      </div>
    </div>

    <AppTabs v-model="activeView" :tabs="viewTabs" content-body-class="p-none">
      <div v-if="activeView === 'events'">
        <EventList />
      </div>

      <div v-else-if="activeView === 'actions'">
        <ActionList />
      </div>

      <div v-else-if="activeView === 'backendLogs'">
        <BackendLogTab :is-active="activeView === 'backendLogs'" />
      </div>
    </AppTabs>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import ActionList from '@/components/ActionList.vue'
import BackendLogTab from '@/components/BackendLogTab.vue'
import AppTabs from '@/components/common/AppTabs.vue'
import EventList from '@/components/EventList.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const HASH_TO_TAB = {
  '#events': 'events',
  '#actions': 'actions',
  '#logs': 'backendLogs',
}

const TAB_TO_HASH = {
  events: '#events',
  actions: '#actions',
  backendLogs: '#logs',
}

function hashToTab(hash) {
  return HASH_TO_TAB[hash] || 'events'
}

const activeView = ref(hashToTab(route.hash))

const viewTabs = computed(() => [
  { label: t('eventLogs.tabs.events'), value: 'events' },
  { label: t('eventLogs.tabs.actions'), value: 'actions' },
  { label: t('eventLogs.tabs.logs'), value: 'backendLogs' },
])

watch(
  () => route.hash,
  (nextHash) => {
    const nextTab = hashToTab(nextHash)
    if (nextTab !== activeView.value) {
      activeView.value = nextTab
    }
  }
)

watch(
  activeView,
  (nextTab) => {
    const desiredHash = TAB_TO_HASH[nextTab] || '#events'
    if (route.hash === desiredHash) return
    router.replace({
      hash: desiredHash,
      query: route.query,
    })
  },
  { immediate: true }
)

onMounted(() => {
  if (route.hash) return
  router.replace({
    hash: TAB_TO_HASH[activeView.value] || '#events',
    query: route.query,
  })
})
</script>
