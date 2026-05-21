<template>
  <section class="ui-panel p-container flex flex-col gap-item">
    <div class="flex items-center justify-between gap-item">
      <div class="flex flex-col gap-micro min-w-0">
        <h2 class="text-title font-semibold text-color break-words">{{ $t('discover.todayUpdates.title') }}</h2>
      </div>
      <Button
        :label="$t('discover.todayUpdates.fullCalendar')"
        severity="secondary"
        variant="text"
        size="small"
        class="!px-0 !py-0 !bg-transparent !border-0 !shadow-none !text-muted hover:!text-primary shrink-0"
        @click="goToCalendar"
      />
    </div>

    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-container">
      <MediaCardSkeleton
        v-for="index in 3"
        :key="`today-update-loading-${index}`"
        poster-width-class="w-poster-sm sm:w-poster-md"
      />
    </div>

    <EmptyState
      v-else-if="error"
      :border="false"
      :description="$t('discover.todayUpdates.loadFailed')"
    />

    <div v-else-if="cards.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-container">
      <MediaCard
        v-for="card in cards"
        :key="card.key"
        :media="card.media"
        :to="card.to"
        variant="today-update"
        poster-width-class="w-poster-sm sm:w-poster-md"
      />
    </div>

    <EmptyState v-else :border="false" :description="$t('discover.todayUpdates.empty')" />
  </section>
</template>

<script setup>
import EmptyState from './common/EmptyState.vue'
import MediaCard from './common/MediaCard.vue'
import MediaCardSkeleton from './common/MediaCardSkeleton.vue'
import Button from 'primevue/button'
import { useTodayAirings } from '@/composables/useTodayAirings'
import { useRouter } from 'vue-router'

const {
  loading,
  error,
  cards,
} = useTodayAirings()
const router = useRouter()

function goToCalendar() {
  router.push('/calendar')
}
</script>
