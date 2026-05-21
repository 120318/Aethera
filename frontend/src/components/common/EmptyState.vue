<template>
  <div
    :class="[
      'empty-state flex flex-col items-center justify-center p-section text-center min-h-placeholder-md text-muted-size font-muted text-muted',
      border ? 'ui-card' : ''
    ]"
  >
    <div class="empty-icon mb-container opacity-50">
      <i v-if="image && image.startsWith('pi')" :class="[image, 'text-display']" :style="iconStyle" />
      <img v-else-if="image" :src="image" :style="imageStyle" />
      <i v-else class="pi pi-inbox text-display" :style="iconStyle" />
    </div>
    <div class="empty-text text-body font-medium">
      <slot name="description">{{ displayDescription }}</slot>
    </div>
    <div v-if="$slots.default" class="mt-container">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  description: {
    type: String,
    default: ''
  },
  image: {
    type: String,
    default: undefined
  },
  imageSize: {
    type: Number,
    default: 48
  },
  border: {
    type: Boolean,
    default: true
  }
})

const { t } = useI18n()
const displayDescription = computed(() => props.description || t('empty.noData'))

const iconStyle = computed(() => (
  props.imageSize ? { fontSize: `${props.imageSize}px` } : undefined
))

const imageStyle = computed(() => (
  props.imageSize ? { width: `${props.imageSize}px` } : undefined
))
</script>

<style scoped>
/* Scoped styles replaced by Tailwind classes */
</style>
