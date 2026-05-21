<template>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular">
    <div
      v-for="(indexer, index) in indexers"
      :key="indexer.id"
      class="ui-settings-card h-full transition-colors"
      :class="[
        draggedIndexerId === indexer.id ? 'opacity-60' : '',
        dragOverIndexerId === indexer.id ? 'border-primary bg-emphasis' : '',
      ]"
      draggable="true"
      @dragstart="$emit('drag-start', indexer.id)"
      @dragover.prevent="$emit('drag-over', indexer.id)"
      @drop.prevent="$emit('drop', index)"
      @dragend="$emit('drag-end')"
    >
      <div class="ui-settings-card-header">
        <div class="ui-settings-card-copy">
          <div class="flex items-center gap-item min-w-0">
            <i class="pi pi-bars text-muted cursor-grab shrink-0" aria-hidden="true" />
            <h4 class="m-none text-body font-semibold text-color truncate">
              {{ indexer.name || $t('settings.indexer.unnamed') }}
            </h4>
          </div>
        </div>
        <div class="ui-settings-card-meta">
          <AppTag :value="indexer.type" tone="accent" />
          <ToggleSwitch
            :model-value="indexer.enabled"
            :input-id="`indexer-enabled-${indexer.id}`"
            @update:model-value="$emit('toggle-enabled', indexer)"
          />
        </div>
      </div>

      <div class="ui-settings-card-body">
        <div class="flex flex-col gap-inline text-caption text-muted">
          <p class="info-item m-none">
            <strong class="font-semibold">{{ $t('common.url') }}:</strong> {{ indexer.url || $t('common.unset') }}
          </p>
          <p class="info-item m-none">
            <strong class="font-semibold">{{ $t('settings.indexer.minSeeders') }}</strong>
            {{ indexer.min_seeders || 0 }}
          </p>
          <p class="info-item m-none">
            <strong class="font-semibold">{{ $t('settings.indexer.priority') }}</strong>
            {{ $t('settings.indexer.priorityValue', { index: index + 1 }) }}
          </p>
        </div>
      </div>

      <div class="ui-settings-card-actions">
        <Button
          :label="$t('settings.indexer.siteSettings')"
          severity="secondary"
          outlined
          size="small"
          @click="$emit('open-sites', indexer)"
        />
        <Button
          :label="$t('common.edit')"
          severity="secondary"
          outlined
          size="small"
          @click="$emit('edit', indexer)"
        />
        <Button
          :label="$t('settings.indexer.testConnection')"
          severity="secondary"
          outlined
          size="small"
          :loading="testLoading && currentTestingIndexer === indexer.id"
          @click="$emit('test', indexer)"
        />
        <Button
          :label="$t('common.delete')"
          severity="secondary"
          outlined
          size="small"
          @click="$emit('remove', indexer.id)"
        />
      </div>
    </div>

    <button type="button" class="ui-settings-add-card" @click="$emit('add')">
      <i class="pi pi-plus text-title" aria-hidden="true"></i>
      <span class="text-body font-medium">{{ $t('common.add') }}</span>
    </button>
  </div>
</template>

<script setup>
import Button from 'primevue/button'
import ToggleSwitch from 'primevue/toggleswitch'
import AppTag from '@/components/common/AppTag.vue'

defineProps({
  indexers: { type: Array, default: () => [] },
  draggedIndexerId: { type: String, default: '' },
  dragOverIndexerId: { type: String, default: '' },
  testLoading: { type: Boolean, default: false },
  currentTestingIndexer: { type: String, default: null },
})

defineEmits([
  'add',
  'edit',
  'remove',
  'test',
  'toggle-enabled',
  'open-sites',
  'drag-start',
  'drag-over',
  'drop',
  'drag-end',
])
</script>

<style scoped>
.info-item {
  margin: 0;
  font-size: var(--text-small);
  line-height: 1.5;
  color: var(--text-muted);
}
</style>
