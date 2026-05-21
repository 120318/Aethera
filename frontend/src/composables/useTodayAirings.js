import { computed, onMounted, ref } from 'vue'
import { listAirings } from '@/api/calendar'
import {
  buildCalendarAiringKey,
  buildCalendarAiringRoute,
  buildTodayUpdateMedia,
  groupCalendarAiringsForDate,
  toLocalDateKey,
} from '@/utils/calendarAirings'
import { useI18n } from 'vue-i18n'

export function useTodayAirings() {
  const { t } = useI18n()
  const today = new Date()
  const todayKey = toLocalDateKey(today)
  const loading = ref(true)
  const error = ref(null)
  const airings = ref([])

  const groupedAirings = computed(() => groupCalendarAiringsForDate(airings.value, today, t))
  const cards = computed(() => groupedAirings.value.map((airing) => ({
    key: buildCalendarAiringKey(airing),
    media: buildTodayUpdateMedia(airing, t),
    to: buildCalendarAiringRoute(airing),
  })))

  async function fetchTodayAirings() {
    loading.value = true
    error.value = null
    try {
      airings.value = await listAirings({ from: todayKey, to: todayKey, scope: 'all' })
    } catch (err) {
      error.value = err
      airings.value = []
      console.error(t('discover.todayUpdates.loadFailed'), err)
    } finally {
      loading.value = false
    }
  }

  onMounted(fetchTodayAirings)

  return {
    loading,
    error,
    cards,
    fetchTodayAirings,
  }
}
