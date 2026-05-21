<template>
  <div v-if="isCardVariant" :class="gridClass">
    <div v-for="index in cardCount" :key="index" class="ui-settings-card h-full">
      <div class="ui-settings-card-header">
        <div class="flex flex-col gap-inline flex-1 min-w-0">
          <Skeleton width="50%" height="var(--text-body)" />
          <Skeleton width="28%" height="var(--text-caption)" />
        </div>
        <Skeleton width="var(--size-control-badge-sm)" height="var(--size-control-icon-sm)" />
      </div>

      <div class="ui-settings-card-body">
        <div class="flex flex-col gap-inline">
          <Skeleton width="88%" height="var(--text-caption)" />
          <Skeleton width="72%" height="var(--text-caption)" />
          <Skeleton width="64%" height="var(--text-caption)" />
        </div>
      </div>

      <div class="ui-settings-card-actions">
        <Skeleton width="5rem" height="var(--size-control-field-sm)" border-radius="var(--radius-item)" />
      </div>
    </div>
  </div>

  <div v-else class="flex flex-col gap-block">
    <div v-for="index in panelCount" :key="index" class="ui-panel p-container flex flex-col gap-item">
      <div class="flex items-center justify-between gap-item">
        <div class="flex flex-col gap-inline flex-1 min-w-0">
          <Skeleton width="32%" height="var(--text-subtitle)" />
          <Skeleton width="68%" height="var(--text-caption)" />
        </div>
        <Skeleton width="4.5rem" height="var(--size-control-field-sm)" border-radius="var(--radius-item)" />
      </div>

      <div :class="panelGridClass">
        <div v-for="fieldIndex in fieldCount" :key="fieldIndex" class="flex flex-col gap-inline">
          <Skeleton width="36%" height="var(--text-caption)" />
          <Skeleton width="100%" height="var(--size-control-field-md)" border-radius="var(--radius-item)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Skeleton from 'primevue/skeleton'

const props = defineProps({
  variant: {
    type: String,
    default: 'cards-regular',
  },
})

const isCardVariant = computed(() => props.variant.startsWith('cards-'))

const gridClass = computed(() => {
  const base = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container'
  const map = {
    'cards-compact': `${base} config-tab-skeleton-grid-compact`,
    'cards-regular': `${base} ui-settings-grid-regular`,
    'cards-tall': `${base} ui-settings-grid-tall`,
  }
  return map[props.variant] || map['cards-regular']
})

const cardCount = computed(() => (props.variant === 'cards-compact' ? 3 : 6))
const panelCount = computed(() => (props.variant === 'stacked-dense' ? 2 : 1))
const fieldCount = computed(() => (props.variant === 'stacked-dense' ? 6 : 4))
const panelGridClass = computed(() => (
  props.variant === 'stacked-dense'
    ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-item'
    : 'grid grid-cols-1 gap-item'
))
</script>

<style scoped>
.config-tab-skeleton-grid-compact {
  --settings-card-min-height: var(--size-settings-card-min-height-compact);
}
</style>
