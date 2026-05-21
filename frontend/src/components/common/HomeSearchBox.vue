<template>
  <div class="home-search-box w-full mx-auto">
    <InputGroup>
      <InputText
        v-model="localValue"
        :placeholder="displayPlaceholder"
        class="h-control-field-hero text-title"
        @keyup.enter="handleSearch"
        @input="handleInput"
      />
      <Button
        :icon="loading ? 'pi pi-spinner pi-spin' : 'pi pi-search'"
        :aria-label="t('common.search')"
        :loading="loading"
        :pt="buttonPt"
        @click="handleSearch"
      />
    </InputGroup>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import InputGroup from 'primevue/inputgroup'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'search', 'input'])
const { t } = useI18n()

const localValue = ref(props.modelValue)
const displayPlaceholder = computed(() => props.placeholder || t('discover.searchPlaceholder'))

const buttonPt = {
  root: {
    class: 'min-w-0 h-control-field-hero',
    style: {
      width: 'var(--size-control-field-hero)',
      minWidth: '0',
      paddingInline: '0',
    },
  },
  label: {
    class: 'hidden',
  },
}

watch(() => props.modelValue, (newVal) => {
  localValue.value = newVal
})

watch(localValue, (newVal) => {
  emit('update:modelValue', newVal)
})

const handleSearch = () => {
  emit('search', localValue.value)
}

const handleInput = (event) => {
  emit('input', event.target.value)
}
</script>

<style scoped>
.home-search-box {
  max-width: min(var(--size-search-hero-width), 100%);
}
</style>
