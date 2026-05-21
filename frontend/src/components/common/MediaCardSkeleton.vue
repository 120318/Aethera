<template>
  <Card
    class="ui-card relative h-full overflow-visible box-border"
    :style="cardStyle"
    :pt="cardPt"
  >
    <template #content>
      <div class="flex flex-row gap-container h-full relative">
        <div :class="['relative shrink-0 self-stretch', posterWidthClass]">
          <div class="w-full h-full rounded-container overflow-hidden bg-emphasis border border-separator-subtle">
            <Skeleton class="w-full h-full" />
          </div>
        </div>

        <div class="flex-1 flex flex-col min-w-0 py-inline pl-inline pr-block">
          <div class="mb-item pr-block">
            <div class="flex flex-wrap items-baseline gap-inline">
              <Skeleton width="48%" height="var(--text-title)" />
              <Skeleton width="16%" height="var(--text-subtitle)" />
            </div>
          </div>

          <div class="flex flex-col gap-inline">
            <Skeleton width="74%" height="var(--text-body)" />
            <Skeleton width="60%" height="var(--text-body)" />
          </div>
        </div>

        <div class="absolute top-none right-0 z-10">
          <Skeleton class="w-control-badge-sm h-control-badge-sm rounded-border" />
        </div>
      </div>

      <div class="absolute right-0 bottom-0">
        <Skeleton width="3rem" height="1.4rem" border-radius="var(--radius-item)" />
      </div>
    </template>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import Card from 'primevue/card'
import Skeleton from 'primevue/skeleton'

const cardPt = {
  body: 'p-container h-full',
  content: 'p-none h-full',
}

const props = defineProps({
  posterWidthClass: {
    type: String,
    default: 'w-poster-sm sm:w-poster-md'
  },
  cardHeight: {
    type: Number,
    default: 0
  }
})

const cardStyle = computed(() => {
  if (!props.cardHeight) return undefined
  return { height: `${props.cardHeight}px` }
})
</script>
