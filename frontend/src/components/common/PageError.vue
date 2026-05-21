<template>
  <div class="flex flex-col items-center justify-center py-section text-center h-full">
    <i :class="[icon, 'text-status-error text-display mb-block']"></i>
    <h3 class="text-title font-bold mb-item">{{ displayTitle }}</h3>
    <p class="text-muted mb-block">{{ error }}</p>
    <Button :label="displayRetryLabel" severity="primary" @click="$emit('retry')" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'

const props = defineProps({
  error: {
    type: String,
    required: true
  },
  title: {
    type: String,
    default: ''
  },
  retryLabel: {
    type: String,
    default: ''
  },
  icon: {
    type: String,
    default: 'pi pi-times-circle'
  }
})

defineEmits(['retry'])

const { t } = useI18n()
const displayTitle = computed(() => props.title || t('common.loadFailed'))
const displayRetryLabel = computed(() => props.retryLabel || t('common.retry'))
</script>
