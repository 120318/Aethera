<template>
  <div class="w-full">
    <InputGroup v-if="showButton">
      <InputGroupAddon v-if="showPrefixIcon">
        <i class="pi pi-search" />
      </InputGroupAddon>
      <InputText
        v-model="localValue" :placeholder="displayPlaceholder" :class="['flex-1', inputClass]" @keyup.enter="handleSearch"
        @input="handleInput"
      />
      <Button
        :icon="showButtonIcon ? (loading ? 'pi pi-spinner pi-spin' : 'pi pi-search') : undefined"
        :label="buttonText" :loading="showButtonIcon ? loading : false" :disabled="!showButtonIcon && loading"
        severity="primary" :class="buttonClass" :pt="buttonPt" @click="handleSearch"
      />
    </InputGroup>

    <IconField v-else>
      <InputIcon v-if="showPrefixIcon" class="pi pi-search" />
      <InputText
        v-model="localValue" :placeholder="displayPlaceholder" :class="['w-full', inputClass]" @keyup.enter="handleSearch"
        @input="handleInput"
      />
    </IconField>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'large'
  },
  fieldSemantic: {
    type: String,
    default: 'control'
  },
  loading: {
    type: Boolean,
    default: false
  },
  showPrefixIcon: {
    type: Boolean,
    default: false
  },
  showButton: {
    type: Boolean,
    default: true
  },
  showButtonIcon: {
    type: Boolean,
    default: true
  },
  buttonText: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'search', 'input'])
const { t } = useI18n()

const localValue = ref(props.modelValue)
const displayPlaceholder = computed(() => props.placeholder || t('search.placeholder'))

const inputClass = computed(() => {
  if (props.fieldSemantic === 'form') {
    if (props.size === 'small') return 'text-small'
    return 'text-body'
  }
  if (props.size === 'small') return 'h-control-field-sm text-small'
  if (props.size === 'medium') return 'h-control-field-md text-body'
  return 'h-control-field-lg text-body'
})

const buttonClass = computed(() => {
  const iconOnly = props.showButtonIcon && !props.buttonText
  if (props.fieldSemantic === 'form') {
    return iconOnly ? 'text-body' : 'text-body'
  }
  if (props.size === 'small') return iconOnly ? 'h-control-field-sm' : 'h-control-field-sm'
  if (props.size === 'medium') return iconOnly ? 'h-control-field-md' : 'h-control-field-md'
  return iconOnly ? 'h-control-field-lg' : 'h-control-field-lg'
})

const buttonPt = computed(() => {
  const iconOnly = props.showButtonIcon && !props.buttonText
  if (!iconOnly) return undefined
  if (props.fieldSemantic === 'form') {
    return {
      root: {
        class: ['px-none', 'min-w-0'],
        style: {
          minWidth: '0',
          paddingInline: '0',
        },
      },
      label: {
        class: 'hidden',
      },
    }
  }

  const sizeClass = props.size === 'small'
    ? 'h-control-field-sm'
    : props.size === 'medium'
      ? 'h-control-field-md'
      : 'h-control-field-lg'

  return {
    root: {
      class: [sizeClass, 'px-none', 'min-w-0'],
      style: {
        width: props.size === 'small'
          ? 'var(--size-control-field-sm)'
          : props.size === 'medium'
            ? 'var(--size-control-field-md)'
            : 'var(--size-control-field-lg)',
        minWidth: '0',
        paddingInline: '0',
      },
    },
    label: {
      class: 'hidden',
    },
  }
})

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
