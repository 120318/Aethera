<template>
  <InputGroup>
    <InputText
      :id="inputId"
      :model-value="modelValue"
      :type="inputType"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      class="w-full"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <InputGroupAddon class="p-none">
      <Button
        :icon="visible ? 'pi pi-eye-slash' : 'pi pi-eye'"
        severity="secondary"
        text
        class="secret-input-toggle"
        :aria-label="visible ? $t('common.hideSecret') : $t('common.showSecret')"
        @click="toggleVisible"
      />
    </InputGroupAddon>
  </InputGroup>
</template>

<script setup>
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import InputText from 'primevue/inputtext'

defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  inputId: {
    type: String,
    default: undefined,
  },
  placeholder: {
    type: String,
    default: '',
  },
  autocomplete: {
    type: String,
    default: 'off',
  },
})

defineEmits(['update:modelValue'])

const visible = ref(false)
const inputType = computed(() => (visible.value ? 'text' : 'password'))

function toggleVisible() {
  visible.value = !visible.value
}
</script>

<style scoped>
.secret-input-toggle {
  width: var(--size-control-md);
  min-width: var(--size-control-md);
  height: var(--size-control-md);
}
</style>
