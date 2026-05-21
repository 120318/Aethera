import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { resolveMediaIdFromRoute } from '@/composables/mediaDetailPageSupport'

export function useMediaDetailRouting() {
  const route = useRoute()
  const router = useRouter()
  const mediaId = computed(() => resolveMediaIdFromRoute(route))
  const routeSeasonNumber = computed(() => {
    const raw = route.query.season
    const value = Number(Array.isArray(raw) ? raw[0] : raw)
    return Number.isInteger(value) && value > 0 ? value : null
  })
  const activeTab = ref(route.query.tab || 'resources')

  async function handleSeasonChange(seasonNumber) {
    const normalized = Number(seasonNumber)
    if (!Number.isInteger(normalized) || normalized <= 0 || !mediaId.value) return
    await router.replace({
      name: 'MediaDetail',
      params: { mediaId: mediaId.value },
      query: { ...route.query, season: normalized },
    })
  }

  async function syncRouteSeason(mediaIdValue, seasonNumber) {
    if (!mediaIdValue || !seasonNumber || routeSeasonNumber.value === seasonNumber) return
    await router.replace({
      name: 'MediaDetail',
      params: { mediaId: mediaIdValue },
      query: { ...route.query, season: seasonNumber },
    })
  }

  async function replaceWithCanonicalMedia(canonicalMediaId, seasonNumber = null) {
    if (!canonicalMediaId) return
    await router.replace({
      name: 'MediaDetail',
      params: { mediaId: canonicalMediaId },
      query: seasonNumber ? { season: seasonNumber } : {},
    })
  }

  async function ensureSeasonQuery(seasonNumber) {
    if (!seasonNumber || routeSeasonNumber.value === seasonNumber) return
    await router.replace({
      name: route.name || 'MediaDetail',
      params: route.params,
      query: { ...route.query, season: seasonNumber },
    })
  }

  return {
    route,
    router,
    mediaId,
    routeSeasonNumber,
    activeTab,
    handleSeasonChange,
    syncRouteSeason,
    replaceWithCanonicalMedia,
    ensureSeasonQuery,
  }
}
