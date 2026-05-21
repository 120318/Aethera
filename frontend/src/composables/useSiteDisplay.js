import { computed, ref } from 'vue'

import { getResourceSites } from '@/api/resource'
import { t } from '@/i18n'

const siteRecords = ref([])
const loaded = ref(false)
const loading = ref(false)
let pendingPromise = null

async function ensureLoaded(initialSites = null) {
  if (Array.isArray(initialSites) && initialSites.length > 0) {
    siteRecords.value = initialSites
    loaded.value = true
    return
  }
  if (loaded.value) return
  if (pendingPromise) {
    await pendingPromise
    return
  }
  loading.value = true
  pendingPromise = getResourceSites()
    .then((data) => {
      siteRecords.value = Array.isArray(data?.sites) ? data.sites : []
      loaded.value = true
    })
    .catch((error) => {
      console.error(t('siteDisplay.loadFailed'), error)
    })
    .finally(() => {
      loading.value = false
      pendingPromise = null
    })
  await pendingPromise
}

export function useSiteDisplay() {
  const siteNameMap = computed(() => {
    const map = new Map()
    for (const site of siteRecords.value) {
      if (!site?.id) continue
      map.set(site.id, site.name || site.description || site.id)
    }
    return map
  })

  const resolveSiteName = (siteId) => {
    if (!siteId) return ''
    return siteNameMap.value.get(siteId) || siteId
  }

  return {
    ensureSiteDisplayLoaded: ensureLoaded,
    siteRecords,
    siteNameMap,
    resolveSiteName,
    siteDisplayLoaded: loaded,
    siteDisplayLoading: loading,
  }
}
