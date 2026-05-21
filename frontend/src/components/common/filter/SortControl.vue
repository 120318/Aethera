<template>
  <ButtonGroup class="hidden md:inline-flex">
    <Button 
      v-for="opt in options" 
      :key="opt.value"
      :label="opt.label"
      severity="secondary"
      variant="outlined"
      :class="[
        'sort-control-button',
        { 'sort-control-button--active': modelValue.prop === opt.value }
      ]"
      :aria-pressed="modelValue.prop === opt.value"
      @click="handleSort(opt.value)"
    >
      <template v-if="modelValue.prop === opt.value" #icon>
        <i 
          class="pi sort-icon"
          :class="modelValue.order === 'ascending' ? 'pi-sort-amount-up-alt' : 'pi-sort-amount-down'"
        ></i>
      </template>
    </Button>
  </ButtonGroup>
  <div class="flex md:hidden items-center gap-inline min-w-0 max-w-full">
    <Select
      :model-value="modelValue.prop"
      :options="options"
      option-label="label"
      option-value="value"
      class="min-w-0 flex-1"
      @update:model-value="handleSortField"
    />
    <Button
      :icon="modelValue.order === 'ascending' ? 'pi pi-sort-amount-up-alt' : 'pi pi-sort-amount-down'"
      severity="secondary"
      outlined
      size="small"
      :aria-label="activeSortLabel"
      @click="toggleSortOrder"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ButtonGroup from 'primevue/buttongroup'
import Button from 'primevue/button'
import Select from 'primevue/select'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    default: () => ({ prop: '', order: '' })
  },
  options: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const activeSortLabel = computed(() => (
  props.options.find((option) => option.value === props.modelValue.prop)?.label || ''
))

const handleSort = (prop) => {
  const newState = { ...props.modelValue }
  
  if (newState.prop === prop) {
    // Toggle order
    newState.order = newState.order === 'descending' ? 'ascending' : 'descending'
  } else {
    // New prop, default to descending
    newState.prop = prop
    newState.order = 'descending'
  }
  
  emit('update:modelValue', newState)
  emit('change', newState)
}

const handleSortField = (prop) => {
  const newState = {
    ...props.modelValue,
    prop,
    order: props.modelValue.prop === prop ? props.modelValue.order : 'descending',
  }

  emit('update:modelValue', newState)
  emit('change', newState)
}

const toggleSortOrder = () => {
  const newState = {
    ...props.modelValue,
    order: props.modelValue.order === 'descending' ? 'ascending' : 'descending',
  }

  emit('update:modelValue', newState)
  emit('change', newState)
}
</script>

<style scoped>
:deep(.sort-control-button--active.p-button) {
  color: var(--accent-primary);
}
</style>
