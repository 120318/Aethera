<template>
  <div class="directory-integrity-actions">
    <Button
      :label="$t('mediaManagement.directoryIntegrity.scan')"
      icon="pi pi-refresh"
      severity="primary"
      size="small"
      :loading="scanning"
      @click="$emit('scan')"
    />
    <Button
      :label="$t('mediaManagement.directoryIntegrity.repairSelected')"
      icon="pi pi-wrench"
      severity="danger"
      size="small"
      :disabled="selectedDisabled"
      :loading="repairing"
      @click="$emit('repair-selected')"
    />
    <Button
      :label="$t('mediaManagement.directoryIntegrity.repairAll')"
      severity="secondary"
      outlined
      size="small"
      :disabled="allDisabled"
      :loading="repairing"
      @click="$emit('repair-all')"
    />
    <Button
      :label="$t('mediaManagement.directoryIntegrity.config')"
      icon="pi pi-cog"
      severity="secondary"
      outlined
      size="small"
      :disabled="configDisabled"
      :loading="policyLoading"
      @click="$emit('config')"
    />
  </div>
</template>

<script setup>
import Button from 'primevue/button'

defineProps({
  scanning: {
    type: Boolean,
    default: false,
  },
  repairing: {
    type: Boolean,
    default: false,
  },
  policyLoading: {
    type: Boolean,
    default: false,
  },
  selectedDisabled: {
    type: Boolean,
    default: false,
  },
  allDisabled: {
    type: Boolean,
    default: false,
  },
  configDisabled: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['scan', 'repair-selected', 'repair-all', 'config'])
</script>

<style scoped>
.directory-integrity-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: var(--spacing-item);
  padding-block-start: max(0px, calc(var(--spacing-item) - var(--spacing-inline)));
}
</style>
