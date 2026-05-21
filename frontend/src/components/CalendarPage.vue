<template>
  <div class="max-w-layout mx-auto flex flex-col gap-section h-full overflow-hidden">
    <!-- Page header. -->
    <div class="ui-page-header">
      <div class="flex flex-col gap-micro">
        <h1 class="text-heading font-semibold text-color">{{ $t('calendar.title') }}</h1>
        <p class="text-muted text-caption">{{ $t('calendar.description') }}</p>
      </div>
    </div>

    <!-- Calendar body and month selector. -->
    <div class="flex-1 flex flex-col gap-item overflow-hidden">
      <!-- Compact period selector. -->
      <div class="flex items-center justify-end gap-item">
        <Button v-tooltip.top="previousPeriodLabel" icon="pi pi-chevron-left" severity="secondary" variant="text" size="small" @click="prevPeriod" />
        <h2 class="text-subtitle font-semibold min-w-form-sm text-center text-color">{{ currentPeriodDisplay }}</h2>
        <Button v-tooltip.top="nextPeriodLabel" icon="pi pi-chevron-right" severity="secondary" variant="text" size="small" @click="nextPeriod" />
      </div>

      <div v-if="loading" class="hidden md:flex flex-1 overflow-auto bg-surface border border-separator rounded-container flex-col">
        <!-- Calendar header skeleton. -->
        <div class="grid grid-cols-7 border-b border-separator bg-emphasis sticky top-0 z-10">
          <div v-for="i in 7" :key="i" class="py-container flex justify-center opacity-50">
            <Skeleton width="2rem" height="1rem" />
          </div>
        </div>
        <!-- Calendar cell skeleton. -->
        <div class="grid grid-cols-7 border-collapse">
          <div
            v-for="i in 42" :key="i"
            class="min-h-calendar-cell h-calendar-cell p-inline border-r border-b border-separator last:border-r-0 flex flex-col gap-micro overflow-hidden bg-surface"
          >
            <div class="flex items-center justify-between p-inline mb-micro">
              <Skeleton width="1.2rem" height="1.2rem" />
            </div>
            <div class="flex flex-col gap-micro px-inline overflow-hidden">
              <div v-for="j in 3" :key="j" class="flex items-start gap-item py-micro">
                <Skeleton width="4px" height="0.8rem" class="shrink-0" />
                <div class="flex-1 flex flex-col gap-tight">
                  <Skeleton width="85%" height="0.7rem" />
                  <Skeleton width="50%" height="0.5rem" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="md:hidden flex-1 overflow-auto bg-surface border border-separator rounded-container">
        <div v-for="index in 7" :key="`mobile-calendar-skeleton-${index}`" class="flex items-start gap-container p-container border-b border-separator last:border-b-0">
          <div class="flex flex-col items-center gap-micro w-calendar-date-rail shrink-0">
            <Skeleton width="2rem" height="1.25rem" />
            <Skeleton width="3rem" height="0.875rem" />
          </div>
          <div class="flex flex-col gap-inline min-w-0">
            <Skeleton width="78%" height="1rem" />
            <Skeleton width="52%" height="0.75rem" />
          </div>
        </div>
      </div>

      <div v-if="!loading" class="hidden md:block flex-1 overflow-auto bg-surface border border-separator rounded-container">
        <!-- Weekday header. -->
        <div class="grid grid-cols-7 border-b border-separator bg-emphasis sticky top-0 z-10 h-10 items-center">
          <div v-for="day in weekDays" :key="day" class="text-center text-muted font-medium text-caption">
            {{ day }}
          </div>
        </div>

        <!-- Calendar cells. -->
        <div class="grid grid-cols-7 border-collapse">
          <div
            v-for="(day, index) in calendarDays" :key="index"
            class="min-h-calendar-cell h-calendar-cell p-inline border-r border-b border-separator last:border-r-0 flex flex-col gap-micro transition-colors hover:bg-emphasis overflow-hidden relative"
            :class="{ 'bg-emphasis/30 opacity-60': !day.isCurrentMonth, 'bg-primary/5': day.isToday }"
          >
            
            <!-- Date number. -->
            <div class="flex items-center justify-between p-inline mb-micro text-color text-small">
              <span class="font-bold text-muted" :class="{ 'text-primary': day.isToday }">
                {{ day.date.getDate() }}
              </span>
              <span
                v-if="day.isToday"
                class="inline-flex items-center justify-center w-calendar-today-badge h-calendar-today-badge rounded-calendar-today-badge bg-primary text-primary-contrast text-caption font-semibold shrink-0"
              >
                {{ $t('calendar.today') }}
              </span>
            </div>

            <!-- Event list. -->
            <div class="flex flex-col gap-micro flex-1 overflow-hidden pr-micro">
              <template v-for="event in day.events.slice(0, MAX_VISIBLE_EVENTS)" :key="eventKey(event)">
                <RouterLink
                  :to="getMediaDetailRoute(event)"
                  class="w-full rounded-item px-item py-micro hover:bg-emphasis transition-colors flex items-start gap-item group no-underline text-inherit"
                >
                  <div class="flex-shrink-0 w-1 h-3 rounded-full bg-primary/40 group-hover:bg-primary mt-1"></div>
                  <div class="min-w-0 flex-1 flex flex-col">
                    <div class="text-caption font-medium truncate leading-tight text-color">{{ event.title }}</div>
                    <div class="text-small text-muted truncate">
                      {{ eventMetaText(event) }}
                    </div>
                  </div>
                </RouterLink>
              </template>
            </div>

            <!-- View all button. -->
            <div
              v-if="day.events.length > MAX_VISIBLE_EVENTS" 
              class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-surface to-transparent pt-4 pb-micro px-item text-center"
            >
              <button class="text-tiny font-semibold text-primary hover:underline" @click.stop="showAllEvents(day)">
                {{ $t('calendar.moreEvents', { count: day.events.length - MAX_VISIBLE_EVENTS }) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading" class="md:hidden flex-1 overflow-auto bg-surface border border-separator rounded-container">
        <div
          v-for="day in mobileWeekDays"
          :key="day.date.toISOString()"
          class="flex items-start gap-container p-container border-b border-separator last:border-b-0"
          :class="{ 'bg-primary/5': day.isToday }"
        >
          <div class="flex flex-col items-center gap-micro w-calendar-date-rail shrink-0">
            <div class="text-heading font-bold leading-none text-color" :class="{ 'text-primary': day.isToday }">
              {{ day.date.getDate() }}
            </div>
            <div class="text-caption text-muted leading-none">
              {{ weekDays[day.date.getDay()] }}
            </div>
            <span v-if="day.isToday" class="inline-flex items-center justify-center w-calendar-today-badge h-calendar-today-badge px-inline rounded-calendar-today-badge bg-primary text-primary-contrast text-tiny font-bold">{{ $t('calendar.today') }}</span>
          </div>

          <div class="flex flex-col gap-inline min-w-0">
            <div v-if="day.events.length === 0" class="text-caption text-muted leading-relaxed">
              {{ $t('calendar.noEventsForDay') }}
            </div>
            <template v-else>
              <RouterLink
                v-for="event in day.events"
                :key="eventKey(event)"
                :to="getMediaDetailRoute(event)"
                class="flex items-start gap-item min-w-0 px-item py-tight rounded-item transition-colors hover:bg-emphasis group no-underline text-inherit"
              >
                <div class="shrink-0 w-1 h-3 mt-1 rounded-badge bg-primary/40"></div>
                <div class="min-w-0 flex-1">
                  <div class="text-body font-semibold leading-snug text-color break-words transition-colors group-hover:text-primary">{{ event.title }}</div>
                  <div class="text-caption text-muted leading-snug break-words">{{ eventMetaText(event) }}</div>
                </div>
              </RouterLink>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Daily detail dialog. -->
    <Dialog
      v-model:visible="detailsVisible" :header="detailsHeader" modal class="w-full max-w-dialog-sm" :dismissable-mask="true"
      :pt="{
        content: { class: 'p-none max-h-dialog-body overflow-y-auto overflow-x-hidden' }
      }"
    >
      <div class="ui-dialog-body">
        <div v-if="selectedDayEvents.length === 0" class="ui-tab-empty p-block text-color">
          <p>{{ $t('calendar.noEventsForDay') }}</p>
        </div>
        <div v-else class="flex flex-col divide-y divide-separator border-t border-separator">
          <div
            v-for="event in selectedDayEvents" :key="eventKey(event)"
            class="flex items-center py-container px-container"
          >
            <RouterLink
              :to="getMediaDetailRoute(event)"
              class="flex flex-col gap-micro min-w-0 group no-underline text-inherit"
            >
              <h4 class="text-body font-medium break-words text-color group-hover:text-primary transition-colors inline-block">{{ event.title }}</h4>
              <p class="text-caption text-muted break-words group-hover:text-primary/80 transition-colors">{{ eventMetaText(event) }}</p>
            </RouterLink>
          </div>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import Skeleton from 'primevue/skeleton'
import Dialog from 'primevue/dialog'
import { listAirings } from '@/api/calendar'
import { useI18n } from 'vue-i18n'
import {
  addDays,
  buildCalendarAiringKey,
  buildCalendarAiringMetaText,
  buildCalendarAiringRoute,
  groupCalendarAiringsForDate,
  startOfWeek,
  toLocalDateKey,
} from '@/utils/calendarAirings'

const { t, locale } = useI18n()

const loading = ref(true)
const currentDate = ref(new Date())
const events = ref([])
const isMobileCalendar = ref(false)

const MAX_VISIBLE_EVENTS = 3

const detailsVisible = ref(false)
const selectedDay = ref(null)
const selectedDayEvents = computed(() => selectedDay.value?.events || [])
const detailsHeader = computed(() => {
  if (!selectedDay.value) return ''
  const d = selectedDay.value.date
  return t('calendar.dayDetailTitle', { year: d.getFullYear(), month: d.getMonth() + 1, day: d.getDate() })
})

const weekDays = computed(() => [
  t('calendar.weekdays.sun'),
  t('calendar.weekdays.mon'),
  t('calendar.weekdays.tue'),
  t('calendar.weekdays.wed'),
  t('calendar.weekdays.thu'),
  t('calendar.weekdays.fri'),
  t('calendar.weekdays.sat'),
])

const currentMonthDisplay = computed(() => {
  return currentDate.value.toLocaleString(locale.value, { year: 'numeric', month: 'long' })
})
const currentPeriodDisplay = computed(() => {
  if (!isMobileCalendar.value) return currentMonthDisplay.value
  const weekStart = startOfWeek(currentDate.value)
  const weekEnd = addDays(weekStart, 6)
  if (weekStart.getFullYear() === weekEnd.getFullYear()) {
    return t('calendar.weekRangeSameYear', {
      year: weekStart.getFullYear(),
      startMonth: weekStart.getMonth() + 1,
      startDay: weekStart.getDate(),
      endMonth: weekEnd.getMonth() + 1,
      endDay: weekEnd.getDate(),
    })
  }
  return t('calendar.weekRangeCrossYear', {
    startYear: weekStart.getFullYear(),
    startMonth: weekStart.getMonth() + 1,
    startDay: weekStart.getDate(),
    endYear: weekEnd.getFullYear(),
    endMonth: weekEnd.getMonth() + 1,
    endDay: weekEnd.getDate(),
  })
})

const previousPeriodLabel = computed(() => (
  isMobileCalendar.value ? t('calendar.previousWeek') : t('calendar.previousMonth')
))
const nextPeriodLabel = computed(() => (
  isMobileCalendar.value ? t('calendar.nextWeek') : t('calendar.nextMonth')
))

function groupEventsForDay(dayDate) {
  return groupCalendarAiringsForDate(events.value, dayDate, t)
}

function buildCalendarDay(date, isCurrentMonth = true) {
  const today = new Date()
  return {
    date,
    isCurrentMonth,
    isToday: date.toDateString() === today.toDateString(),
    events: groupEventsForDay(date)
  }
}

const calendarDays = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  
  const firstDayOfMonth = new Date(year, month, 1)
  const lastDayOfMonth = new Date(year, month + 1, 0)
  
  const days = []
  
  const startDay = firstDayOfMonth.getDay()
  for (let i = startDay; i > 0; i--) {
    days.push(buildCalendarDay(new Date(year, month, 1 - i), false))
  }
  
  for (let i = 1; i <= lastDayOfMonth.getDate(); i++) {
    days.push(buildCalendarDay(new Date(year, month, i), true))
  }
  
  const totalSlots = 42
  const remainingSlots = totalSlots - days.length
  for (let i = 1; i <= remainingSlots; i++) {
    days.push(buildCalendarDay(new Date(year, month + 1, i), false))
  }
  
  return days
})

const mobileWeekDays = computed(() => {
  const firstDate = startOfWeek(currentDate.value)
  return Array.from({ length: 7 }, (_, index) => buildCalendarDay(addDays(firstDate, index), true))
})

const fetchCalendarData = async () => {
  loading.value = true
  try {
    const year = currentDate.value.getFullYear()
    const month = currentDate.value.getMonth()
    const firstVisibleDate = isMobileCalendar.value
      ? startOfWeek(currentDate.value)
      : new Date(year, month, 1)
    const lastVisibleDate = isMobileCalendar.value
      ? addDays(firstVisibleDate, 6)
      : new Date(year, month + 1, 0)

    const from = toLocalDateKey(firstVisibleDate)
    const to = toLocalDateKey(lastVisibleDate)

    const data = await listAirings({ from, to, scope: 'all' })
    events.value = data || []
  } catch (e) {
    console.error(t('calendar.loadFailed'), e)
  } finally {
    loading.value = false
  }
}

const showAllEvents = (day) => {
  selectedDay.value = day
  detailsVisible.value = true
}

const eventKey = buildCalendarAiringKey

const eventMetaText = (event) => buildCalendarAiringMetaText(event, t)

const prevPeriod = () => {
  currentDate.value = isMobileCalendar.value
    ? addDays(currentDate.value, -7)
    : new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() - 1, 1)
  fetchCalendarData()
}

const nextPeriod = () => {
  currentDate.value = isMobileCalendar.value
    ? addDays(currentDate.value, 7)
    : new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + 1, 1)
  fetchCalendarData()
}

const getMediaDetailRoute = buildCalendarAiringRoute

let mobileCalendarMediaQuery = null

function updateMobileCalendarFlag() {
  isMobileCalendar.value = Boolean(mobileCalendarMediaQuery?.matches)
}

function handleMobileCalendarChange() {
  updateMobileCalendarFlag()
  fetchCalendarData()
}

onMounted(() => {
  mobileCalendarMediaQuery = window.matchMedia('(max-width: 767px)')
  updateMobileCalendarFlag()
  mobileCalendarMediaQuery.addEventListener('change', handleMobileCalendarChange)
  fetchCalendarData()
})

onUnmounted(() => {
  mobileCalendarMediaQuery?.removeEventListener('change', handleMobileCalendarChange)
})
</script>
