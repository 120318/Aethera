<template>
  <MultiSelect
    v-model="selectedValues"
    :options="optionGroups"
    option-label="label"
    option-value="value"
    option-group-label="label"
    option-group-children="items"
    :placeholder="resolvedPlaceholder"
    display="chip"
    :max-selected-labels="2"
    :selected-items-label="$t('resourceKind.selectedTypesLabel')"
    class="w-full"
  />
</template>

<script setup>
import { computed } from 'vue'
import MultiSelect from 'primevue/multiselect'
import { RESOURCE_FORMS_BY_KIND } from '@/constants/qualityOptions'
import { useI18n } from 'vue-i18n'

const DEFAULT_KIND = 'video_file'
const DEFAULT_VALUE = 'video_file:Video File'

const props = defineProps({
  resourceKind: {
    type: Array,
    default: () => ['video_file'],
  },
  resourceForm: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:resourceKind', 'update:resourceForm'])
const { t } = useI18n()

const resolvedPlaceholder = computed(() => props.placeholder || t('resourceKind.selectResourceType'))

const optionGroups = computed(() => [
  {
    label: t('resourceKind.video'),
    items: [
      { label: t('resourceKind.videoFile'), value: toValue('video_file', 'Video File') },
    ],
  },
  {
    label: t('resourceKind.originalDisc'),
    items: [
      { label: t('resourceKind.blurayDisc'), value: toValue('original_disc', 'BluRay Disc') },
      { label: t('resourceKind.dvdDisc'), value: toValue('original_disc', 'DVD Disc') },
    ],
  },
])

const selectedValues = computed({
  get: () => selectedValuesFromProps(props.resourceKind, props.resourceForm),
  set: (values) => {
    const payload = payloadFromSelection(values)
    emit('update:resourceKind', payload.resourceKind)
    emit('update:resourceForm', payload.resourceForm)
  },
})

function toValue(kind, form) {
  return `${kind}:${form}`
}

function normalizeKinds(kinds) {
  return Array.isArray(kinds) && kinds.length > 0 ? [...new Set(kinds)] : [DEFAULT_KIND]
}

function allowedFormsForKinds(kinds) {
  return normalizeKinds(kinds).flatMap((kind) => (
    (RESOURCE_FORMS_BY_KIND[kind] || []).map((form) => ({ kind, form }))
  ))
}

function selectedValuesFromProps(kinds, forms) {
  const scopedForms = Array.isArray(forms) ? forms : []
  const allowed = allowedFormsForKinds(kinds)
  if (scopedForms.length === 0) {
    return allowed.map((item) => toValue(item.kind, item.form))
  }
  return allowed
    .filter((item) => scopedForms.includes(item.form))
    .map((item) => toValue(item.kind, item.form))
}

function payloadFromSelection(values) {
  const selected = Array.isArray(values) && values.length > 0 ? [...new Set(values)] : [DEFAULT_VALUE]
  const selectedItems = selected.map((value) => {
    const separatorIndex = value.indexOf(':')
    return {
      kind: value.slice(0, separatorIndex),
      form: value.slice(separatorIndex + 1),
    }
  }).filter((item) => item.kind && item.form)
  const selectedKinds = [...new Set(selectedItems.map((item) => item.kind))]
  const resourceKind = selectedKinds.length > 0 ? selectedKinds : [DEFAULT_KIND]
  const selectedForms = selectedItems.map((item) => item.form)
  const allSelectedKindForms = allowedFormsForKinds(resourceKind).map((item) => item.form)
  const hasAllFormsForSelectedKinds = allSelectedKindForms.every((form) => selectedForms.includes(form))
  return {
    resourceKind,
    resourceForm: hasAllFormsForSelectedKinds ? [] : selectedForms,
  }
}
</script>
