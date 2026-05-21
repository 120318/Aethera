<template>
  <Dialog
    :visible="modelValue"
    :header="hasHeaderSlot ? undefined : title"
    modal
    :dismissable-mask="true"
    :class="dialogClass"
    :closable="closable"
    :content-class="contentClass"
    @update:visible="$emit('update:modelValue', $event)"
  >
    <template v-if="hasHeaderSlot" #header>
      <slot name="header" />
    </template>

    <div :class="bodyClass">
      <div v-if="hasIntro" class="config-dialog-intro">
        <slot name="intro">
          {{ intro }}
        </slot>
      </div>
      <slot />
    </div>

    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, useSlots } from 'vue'
import Dialog from 'primevue/dialog'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '',
  },
  size: {
    type: String,
    default: 'md',
  },
  intro: {
    type: String,
    default: '',
  },
  scroll: {
    type: Boolean,
    default: true,
  },
  contentScroll: {
    type: Boolean,
    default: false,
  },
  closable: {
    type: Boolean,
    default: true,
  },
})

defineEmits(['update:modelValue'])

const slots = useSlots()

const hasIntro = computed(() => Boolean(props.intro || slots.intro))
const hasHeaderSlot = computed(() => Boolean(slots.header))

const dialogClass = computed(() => {
  if (props.size === 'sm') return 'config-dialog-shell w-full max-w-dialog-sm'
  if (props.size === 'lg') return 'config-dialog-shell w-full max-w-dialog-lg'
  return 'config-dialog-shell w-full max-w-dialog-md'
})

const bodyClass = computed(() => [
  'ui-dialog-body',
])

const contentClass = computed(() => [
  'config-dialog-content',
  props.scroll || props.contentScroll ? 'config-dialog-content-scroll' : '',
].filter(Boolean).join(' '))
</script>

<style scoped>
.config-dialog-shell {
  color: var(--text-default);
}

.config-dialog-intro {
  font-size: var(--text-caption);
  color: var(--text-muted);
  line-height: 1.6;
}
</style>

<style>
.config-dialog-content {
  overflow: hidden;
}

.config-dialog-content-scroll {
  max-height: var(--max-height-dialog-body);
  overflow-y: auto;
  overflow-x: hidden;
}
</style>
