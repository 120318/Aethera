<template>
  <ConfigDialog
    v-model="visible"
    :title="$t('mediaManagement.directoryIntegrity.policyDialogTitle')"
    size="md"
  >
    <div v-if="loading" class="flex flex-col gap-item">
      <Skeleton v-for="index in 3" :key="index" height="var(--size-control-field-md)" border-radius="var(--radius-item)" />
    </div>
    <div v-else class="directory-integrity-policy-list">
      <div
        v-for="policy in policies"
        :key="policy.directory_id"
        class="directory-integrity-policy-item"
      >
        <div class="directory-integrity-policy-item__head">
          <label class="directory-integrity-policy-switch">
            <ToggleSwitch v-model="policy.enabled" />
            <span>{{ $t('mediaManagement.directoryIntegrity.policyEnabled') }}</span>
          </label>
        </div>

        <div class="directory-integrity-policy-scope">
          <label class="directory-integrity-policy-check">
            <Checkbox v-model="policy.scan_library" binary :disabled="!policy.enabled" />
            <span>{{ $t('mediaManagement.directoryIntegrity.scanLibrary') }}</span>
          </label>
          <label class="directory-integrity-policy-check">
            <Checkbox v-model="policy.scan_download" binary :disabled="!policy.enabled" />
            <span>{{ $t('mediaManagement.directoryIntegrity.scanDownload') }}</span>
          </label>
        </div>

        <div class="flex flex-col gap-inline">
          <p class="m-0 text-caption text-muted">{{ $t('mediaManagement.directoryIntegrity.policyIssueTypes') }}</p>
          <div class="directory-integrity-policy-issue-grid">
            <label
              v-for="option in issueOptions"
              :key="option.value"
              class="directory-integrity-policy-check"
            >
              <Checkbox v-model="policy.issue_types" :value="option.value" :disabled="!policy.enabled" />
              <span>{{ option.label }}</span>
            </label>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button :label="$t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="$t('common.save')"
        icon="pi pi-save"
        :loading="saving"
        @click="$emit('save')"
      />
    </template>
  </ConfigDialog>
</template>

<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Skeleton from 'primevue/skeleton'
import ToggleSwitch from 'primevue/toggleswitch'
import ConfigDialog from '@/components/common/ConfigDialog.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  saving: {
    type: Boolean,
    default: false,
  },
  policies: {
    type: Array,
    default: () => [],
  },
  issueOptions: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue', 'save'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
</script>

<style scoped>
.directory-integrity-policy-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-container);
}

.directory-integrity-policy-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-item);
  padding-block-end: var(--spacing-container);
  border-bottom: 1px solid var(--border-subtle);
}

.directory-integrity-policy-item:last-child {
  padding-block-end: 0;
  border-bottom: 0;
}

.directory-integrity-policy-item__head {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: var(--spacing-container);
}

.directory-integrity-policy-scope,
.directory-integrity-policy-issue-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--spacing-inline) var(--spacing-item);
}

.directory-integrity-policy-check {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: var(--spacing-inline);
  color: var(--text-default);
  font-size: var(--text-caption);
}

.directory-integrity-policy-check span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.directory-integrity-policy-switch {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: var(--spacing-inline);
  color: var(--text-default);
  font-size: var(--text-caption);
}

@media (max-width: 767px) {
  .directory-integrity-policy-item__head {
    flex-direction: column;
  }

  .directory-integrity-policy-scope,
  .directory-integrity-policy-issue-grid {
    grid-template-columns: 1fr;
  }
}
</style>
