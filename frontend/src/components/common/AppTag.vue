<template>
  <span
    v-tooltip.top="resolvedTooltip"
    class="ui-tag"
    :class="[
      `ui-tag-${resolvedTone}`,
      `ui-tag-${size}`,
      {
        'ui-tag-interactive': interactive,
        'ui-tag-truncate': truncate
      }
    ]"
  >
    <span v-if="icon" class="ui-tag-icon inline-flex shrink-0 items-center justify-center">
      <i :class="[icon, 'text-tiny']" />
    </span>
    <span class="ui-tag-label inline-flex min-w-0 items-center">{{ resolvedLabel }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: {
    type: [String, Number],
    default: ''
  },
  label: {
    type: [String, Number],
    default: ''
  },
  icon: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'neutral'
  },
  size: {
    type: String,
    default: 'sm'
  },
  interactive: {
    type: Boolean,
    default: false
  },
  truncate: {
    type: Boolean,
    default: false
  },
  tooltip: {
    type: String,
    default: ''
  }
})

const resolvedLabel = computed(() => String(props.label || props.value || ''))
const resolvedTooltip = computed(() => props.tooltip || null)

const resolvedTone = computed(() => {
  const allowed = ['neutral', 'accent', 'success', 'warn', 'danger']
  return allowed.includes(props.tone) ? props.tone : 'neutral'
})
</script>
