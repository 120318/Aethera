<template>
  <div class="flex flex-col gap-container">
    <div
      v-if="config.naming_templates && config.naming_templates.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular"
    >
      <div v-for="template in config.naming_templates" :key="template.id" class="ui-settings-card h-full">
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h5 class="m-0 text-body font-semibold text-color">{{ template.name || $t('settings.naming.unnamed') }}</h5>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag :value="template.type === 'movie' ? $t('settings.naming.movie') : $t('settings.naming.tv')" tone="accent" />
            <AppTag v-if="template.is_default" :value="$t('common.default')" tone="success" />
            <ToggleSwitch
              :model-value="template.enabled"
              :input-id="`naming-template-enabled-${template.id}`"
              @update:model-value="toggleTemplateEnabled(template)"
            />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p class="info-item"><strong class="font-semibold">{{ $t('settings.naming.dirTemplate') }}</strong> {{ template.dir_template || $t('common.unset') }}</p>
            <p class="info-item"><strong class="font-semibold">{{ $t('settings.naming.fileTemplate') }}</strong> {{ template.file_template || $t('common.unset') }}</p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button
            v-if="!template.is_default"
            :label="$t('common.setDefault')"
            severity="secondary"
            outlined
            size="small"
            @click="setDefaultTemplate(template)"
          />
          <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="editTemplate(template)" />
          <Button
            :label="$t('common.delete')"
            severity="secondary"
            outlined
            size="small"
            :disabled="template.is_default"
            @click="removeTemplate(template.id)"
          />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addTemplate">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular"
    >
      <button type="button" class="ui-settings-add-card" @click="addTemplate">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <ConfigDialog
      v-model:visible="templateDialogVisible"
      :title="templateDialogTitle"
      size="lg"
      :intro="$t('settings.naming.intro')"
    >
      <div class="ui-dialog-section">
        <label for="dialog-template-name" class="ui-dialog-item-title block">{{ $t('settings.naming.name') }}</label>
        <InputText id="dialog-template-name" v-model="currentTemplate.name" :placeholder="$t('settings.naming.namePlaceholder')" class="w-full" />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-template-type" class="ui-dialog-item-title block">{{ $t('settings.naming.type') }}</label>
        <Select
          v-model="currentTemplate.type"
          input-id="dialog-template-type"
          class="w-full"
          :disabled="templateDialogMode === 'edit'"
          :options="templateTypeOptions"
          option-label="label"
          option-value="value"
          @update:model-value="handleTemplateTypeChange"
        />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-dir-template" class="ui-dialog-item-title block">{{ $t('settings.naming.dirTemplateLabel') }}</label>
        <InputText
          id="dialog-dir-template"
          v-model="currentTemplate.dir_template"
          :placeholder="$t('settings.naming.dirTemplatePlaceholder')"
          class="w-full"
          @focus="activeTemplateField = 'dir_template'"
          @input="onTemplateContentChange"
        />
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-file-template" class="ui-dialog-item-title block">{{ $t('settings.naming.fileTemplateLabel') }}</label>
        <InputText
          id="dialog-file-template"
          v-model="currentTemplate.file_template"
          :placeholder="$t('settings.naming.fileTemplatePlaceholder')"
          class="w-full"
          @focus="activeTemplateField = 'file_template'"
          @input="onTemplateContentChange"
        />
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.naming.variables') }}</label>
        <NamingTemplateVariablePicker :variables="availableVariables" @select="insertVariable" />
      </div>

      <div v-if="hasPreview" class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.naming.preview') }}</label>
        <div v-if="previewError" class="preview-error">
          {{ previewError }}
        </div>
        <div v-else class="grid grid-cols-1 gap-item">
          <div>
            <div class="preview-label">{{ $t('settings.naming.normalDir') }}</div>
            <div class="template-preview">{{ dirPreview || $t('settings.naming.empty') }}</div>
          </div>
          <div>
            <div class="preview-label">{{ $t('settings.naming.normalFile') }}</div>
            <div class="template-preview">{{ filePreview || $t('settings.naming.empty') }}</div>
          </div>
          <div>
            <div class="preview-label">{{ $t('settings.naming.normalFullPath') }}</div>
            <div class="template-preview">{{ fullPreview || $t('settings.naming.empty') }}</div>
          </div>
          <div>
            <div class="preview-label">{{ $t('settings.naming.discDir') }}</div>
            <div class="template-preview">{{ discDirPreview || $t('settings.naming.empty') }}</div>
          </div>
          <div>
            <div class="preview-label">{{ $t('settings.naming.discFile') }}</div>
            <div class="template-preview">{{ discFilePreview || $t('settings.naming.empty') }}</div>
          </div>
          <div>
            <div class="preview-label">{{ $t('settings.naming.discIsoPath') }}</div>
            <div class="template-preview">{{ discFullPreview || $t('settings.naming.empty') }}</div>
          </div>
        </div>
      </div>

      <div class="ui-dialog-section">
        <label for="dialog-template-enabled" class="ui-dialog-item-title block">{{ $t('settings.naming.enabledStatus') }}</label>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="flex items-center gap-item">
            <ToggleSwitch v-model="currentTemplate.enabled" input-id="dialog-template-enabled" />
            <span class="text-muted-size font-muted text-muted">{{ currentTemplate.enabled ? $t('common.enabled') : $t('common.disabled') }}</span>
          </div>
          <div class="flex items-center gap-item">
            <ToggleSwitch v-model="currentTemplate.is_default" input-id="dialog-template-default" />
            <span class="text-muted-size font-muted text-muted">{{ currentTemplate.is_default ? $t('settings.naming.defaultTemplate') : $t('common.setDefault') }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="templateDialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" @click="saveTemplate" />
      </template>
    </ConfigDialog>
  </div>
</template>

<script setup>
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import NamingTemplateVariablePicker from '@/components/config/NamingTemplateVariablePicker.vue'
import { useNamingTemplateConfig } from '@/composables/useNamingTemplateConfig'
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

const { t } = useI18n()

const templateTypeOptions = computed(() => [
  { label: t('settings.naming.movie'), value: 'movie' },
  { label: t('settings.naming.tv'), value: 'tv' },
])

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
  applyConfigPatch: {
    type: Function,
    required: true,
  },
})

defineEmits(['save'])

const {
  activeTemplateField,
  availableVariables,
  currentTemplate,
  discDirPreview,
  discFilePreview,
  discFullPreview,
  dirPreview,
  filePreview,
  fullPreview,
  handleTemplateTypeChange,
  hasPreview,
  addTemplate,
  editTemplate,
  onTemplateContentChange,
  insertVariable,
  removeTemplate,
  saveTemplate,
  setDefaultTemplate,
  templateDialogMode,
  templateDialogTitle,
  templateDialogVisible,
  toggleTemplateEnabled,
  previewError,
} = useNamingTemplateConfig(props)

defineExpose({
  addTemplate,
  editTemplate,
  removeTemplate,
  setDefaultTemplate,
})
</script>

<style scoped>
.info-item {
  margin: 0;
  font-size: var(--text-small);
  line-height: 1.5;
  color: var(--text-muted);
}

.preview-label {
  margin-bottom: var(--spacing-inline);
  font-size: var(--text-tiny);
  color: var(--text-muted);
}

.template-preview {
  background-color: var(--surface-content);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-container);
  padding: var(--spacing-item);
  font-family: monospace;
  font-size: var(--text-small);
  color: var(--text-default);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.preview-error {
  border-radius: var(--radius-container);
  padding: var(--spacing-item);
  background-color: color-mix(in srgb, var(--status-danger) 10%, var(--surface-content));
  color: var(--status-danger);
  font-size: var(--text-small);
  line-height: 1.5;
}
</style>
