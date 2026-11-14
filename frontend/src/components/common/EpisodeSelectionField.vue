<template>
  <div class="flex flex-col gap-item">
    <label class="ui-dialog-item-title">{{ label }}</label>
    <MultiSelect
      v-model="selection"
      :options="episodeOptions"
      option-label="label"
      option-value="value"
      option-disabled="locked"
      :aria-label="label"
      :placeholder="$t('episodeSelection.placeholder')"
      :max-selected-labels="3"
      :selected-items-label="$t('episodeSelection.selectedCount', { count: modelValue.length })"
      filter
      class="w-full"
    />
    <p v-if="lockedEpisodes.length" class="text-caption text-muted m-none">
      {{ $t('episodeSelection.lockedHint') }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MultiSelect from 'primevue/multiselect'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  availableEpisodes: { type: Array, default: () => [] },
  lockedEpisodes: { type: Array, default: () => [] },
  label: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const lockedSet = computed(() => new Set(props.lockedEpisodes))
const episodeOptions = computed(() => [...new Set(props.availableEpisodes)]
  .sort((left, right) => left - right)
  .map(episode => ({
    label: t('taskLive.episodeLabel', { number: episode }),
    value: episode,
    locked: lockedSet.value.has(episode),
  })))
const selection = computed({
  get: () => props.modelValue,
  set: (values) => {
    const available = new Set(props.availableEpisodes)
    const selected = [...new Set([...(values || []), ...props.lockedEpisodes])]
      .filter(episode => available.has(episode))
      .sort((left, right) => left - right)
    emit('update:modelValue', selected)
  },
})
</script>
