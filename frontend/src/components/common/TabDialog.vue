<template>
  <Dialog
    :visible="modelValue"
    modal
    :dismissable-mask="true"
    :show-header="false"
    :class="dialogClass"
    content-class="tab-dialog-content tab-dialog-content-scroll p-none"
    @update:visible="$emit('update:modelValue', $event)"
  >
    <div class="tab-dialog-body">
      <AppTabs
        :model-value="activeTab"
        :tabs="tabs"
        :min-height="minHeight"
        header-class="tab-dialog-tabs-header border-l-0 border-r-0 border-t-0"
        content-class="tab-dialog-tabs-content border-l-0 border-r-0 border-b-0 rounded-b-none shadow-none"
        :content-body-class="contentBodyClass"
        @update:model-value="$emit('update:activeTab', $event)"
      >
        <template #actions>
          <slot name="actions">
            <Button icon="pi pi-times" severity="secondary" text rounded :aria-label="$t('common.close')" @click="$emit('update:modelValue', false)" />
          </slot>
        </template>

        <slot />
      </AppTabs>
    </div>

    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import AppTabs from '@/components/common/AppTabs.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  activeTab: {
    type: String,
    required: true,
  },
  tabs: {
    type: Array,
    required: true,
    default: () => [],
  },
  size: {
    type: String,
    default: 'lg',
  },
  minHeight: {
    type: Boolean,
    default: false,
  },
  contentBodyClass: {
    type: [String, Array, Object],
    default: '',
  },
})

defineEmits(['update:modelValue', 'update:activeTab'])

const dialogClass = computed(() => {
  if (props.size === 'sm') return 'tab-dialog-shell w-full max-w-dialog-sm'
  if (props.size === 'md') return 'tab-dialog-shell w-full max-w-dialog-md'
  return 'tab-dialog-shell w-full max-w-dialog-lg'
})
</script>

<style>
.tab-dialog-shell {
  color: var(--text-default);
  overflow: hidden;
}

.tab-dialog-shell .tab-dialog-content {
  width: 100%;
  padding: 0;
  overflow-x: hidden;
}

.tab-dialog-shell .tab-dialog-content-scroll {
  max-height: var(--max-height-dialog-body);
  overflow-y: auto;
}

.tab-dialog-shell .tab-dialog-body {
  width: 100%;
  padding: 0;
}
</style>
