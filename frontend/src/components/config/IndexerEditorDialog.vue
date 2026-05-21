<template>
  <ConfigDialog
    :model-value="visible"
    :title="title"
    size="md"
    :intro="$t('settings.indexer.intro')"
    @update:model-value="$emit('update:visible', $event)"
  >
    <div class="ui-dialog-section">
      <label for="dialog-indexer-type" class="ui-dialog-item-title block">{{ $t('common.type') }}</label>
      <Select
        id="dialog-indexer-type"
        v-model="indexer.type"
        :options="typeOptions"
        option-label="label"
        option-value="value"
        class="w-full"
        @update:model-value="$emit('type-change', $event)"
      />
    </div>

    <div class="ui-dialog-section">
      <label for="dialog-indexer-name" class="ui-dialog-item-title block">{{ $t('settings.indexer.name') }}</label>
      <InputText
        id="dialog-indexer-name"
        v-model="indexer.name"
        :placeholder="$t('settings.indexer.namePlaceholder')"
        class="w-full"
      />
    </div>

    <div class="ui-dialog-section">
      <label for="dialog-indexer-url" class="ui-dialog-item-title block">{{ $t('common.url') }}</label>
      <InputText
        id="dialog-indexer-url"
        v-model="indexer.url"
        :placeholder="urlPlaceholder"
        class="w-full"
      />
      <div class="ui-dialog-help">
        {{ urlHelp }}
      </div>
    </div>

    <div class="ui-dialog-section">
      <label for="dialog-indexer-api-key" class="ui-dialog-item-title block">{{ $t('common.apiKey') }}</label>
      <InputText
        id="dialog-indexer-api-key"
        v-model="indexer.api_key"
        :placeholder="$t('common.apiKey')"
        class="w-full"
      />
    </div>

    <div class="ui-dialog-section">
      <label for="dialog-indexer-min-seeders" class="ui-dialog-item-title block">{{ $t('settings.indexer.minSeedersLabel') }}</label>
      <InputNumber
        v-model="indexer.min_seeders"
        input-id="dialog-indexer-min-seeders"
        :min="0"
        class="w-full"
        show-buttons
      />
    </div>

    <div class="ui-dialog-section">
      <label for="dialog-indexer-enabled" class="ui-dialog-item-title block">{{ $t('settings.indexer.enabledLabel') }}</label>
      <div class="flex items-center gap-item">
        <ToggleSwitch
          v-model="indexer.enabled"
          input-id="dialog-indexer-enabled"
        />
        <span class="text-muted-size text-muted-size font-muted text-muted">{{
          indexer.enabled ? $t('common.enabled') : $t('common.disabled')
        }}</span>
      </div>
    </div>
    <template #footer>
      <Button
        :label="$t('common.cancel')"
        severity="secondary"
        text
        @click="$emit('update:visible', false)"
      />
      <Button :label="$t('common.save')" severity="primary" @click="$emit('save')" />
    </template>
  </ConfigDialog>
</template>

<script setup>
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import ConfigDialog from '@/components/common/ConfigDialog.vue'

defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  indexer: { type: Object, required: true },
  typeOptions: { type: Array, default: () => [] },
  urlPlaceholder: { type: String, default: '' },
  urlHelp: { type: String, default: '' },
})

defineEmits(['update:visible', 'type-change', 'save'])
</script>
