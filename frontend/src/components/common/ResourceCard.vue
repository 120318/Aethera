<template>
  <div class="flex flex-col gap-inline py-item border-b border-separator last:border-0">
    <div class="flex items-start gap-item min-w-0">
      <div class="min-w-0 flex-1">
        <a
          v-if="resource.resource?.detail_url" :href="resource.resource.detail_url" target="_blank"
          rel="noopener noreferrer" :title="resource.resource?.title" class="inline text-body break-words whitespace-normal hover:text-primary-emphasis"
        >
          {{ resource.resource?.title || $t('resourceSearch.unknownTitle') }}
        </a>
        <span v-else :title="resource.resource?.title" class="inline text-body break-words whitespace-normal">
          {{ resource.resource?.title || $t('resourceSearch.unknownTitle') }}
        </span>
      </div>
      <slot name="actions" :resource="resource">
        <Button
          v-tooltip.top="$t('actions.download')" icon="pi pi-download" text
          class="shrink-0"
          :loading="isDownloading" :disabled="isDownloading"
          @click="$emit('download', resource)"
        />
      </slot>
    </div>

    <!-- Description. -->
    <p v-if="resource.resource?.description" class="text-caption text-muted m-none">
      {{ resource.resource.description }}
    </p>

    <!-- Metadata. -->
    <div class="flex flex-col gap-inline">
      <div v-if="tags.length > 0" class="flex flex-wrap items-center gap-x-inline gap-y-inline min-w-0">
        <span
          v-for="(tag, idx) in tags"
          :key="`tag-${idx}`"
          v-tooltip.top="tag.tooltip || null"
          class="max-w-full"
        >
          <AppTag :value="tag.value" :icon="tag.icon" :tone="tag.tone" />
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'
import AppTag from '@/components/common/AppTag.vue'
import { useResourceTags } from '@/composables/useResourceTags'

const props = defineProps({
  resource: {
    type: Object,
    required: true
  },
  isDownloading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['download'])

const { getSortedTags } = useResourceTags()
const tags = computed(() => getSortedTags(props.resource))
</script>
