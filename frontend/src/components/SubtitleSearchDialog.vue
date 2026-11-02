<template>
  <Dialog :visible="visible" :header="$t('localResources.subtitles.title')" modal :dismissable-mask="true" class="w-full max-w-dialog-lg" @update:visible="emit('update:visible', $event)">
    <div v-if="loading" class="flex justify-center py-container">
      <i class="pi pi-spin pi-spinner text-primary text-xl" />
    </div>
    <div v-else-if="!candidates.length" class="text-caption text-muted py-container text-center">
      {{ $t('localResources.subtitles.empty') }}
    </div>
    <div v-else class="flex flex-col gap-item">
      <div v-for="candidate in candidates" :key="candidate.id" class="ui-dialog-section flex items-start justify-between gap-item">
        <div class="flex flex-col gap-inline min-w-0">
          <div class="flex flex-wrap gap-inline items-center">
            <span class="font-medium">{{ candidate.language }}</span>
            <span class="text-caption text-muted">{{ candidate.format.toUpperCase() }}</span>
            <span v-if="candidate.hash_matched" class="text-caption text-success">{{ $t('localResources.subtitles.hashMatched') }}</span>
            <span class="text-caption text-muted">{{ Math.round(candidate.match_confidence * 100) }}%</span>
          </div>
          <span class="text-caption break-words">{{ candidate.release || candidate.file_name }}</span>
          <span class="text-caption text-muted">
            {{ candidate.provider }} · {{ $t('localResources.subtitles.downloadCount', { count: candidate.download_count }) }}
          </span>
          <Button :label="$t('localResources.subtitles.preview')" size="small" severity="secondary" text :loading="previewingId === candidate.id" @click="preview(candidate)" />
          <pre v-if="previewCandidateId === candidate.id" class="text-caption whitespace-pre-wrap max-h-48 overflow-auto m-none">{{ previewContent }}</pre>
        </div>
        <Button
          :label="$t('localResources.subtitles.install')"
          size="small"
          :loading="installingId === candidate.id"
          :disabled="!!installingId"
          @click="install(candidate)"
        />
      </div>
    </div>
  </Dialog>
</template>

<script setup>
import { toRef } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

import { useSubtitleSearchDialog } from '@/composables/useSubtitleSearchDialog'
import { useNotificationStore } from '@/stores/notification'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  visible: { type: Boolean, default: false },
  resource: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'installed'])
const { t } = useI18n()
const notification = useNotificationStore()
const {
  loading,
  installingId,
  candidates,
  previewingId,
  previewCandidateId,
  previewContent,
  preview,
  install: installCandidate,
} = useSubtitleSearchDialog(toRef(props, 'visible'), toRef(props, 'resource'))

async function install(candidate) {
  const installed = await installCandidate(candidate)
  if (!installed) return
  notification.success(t('localResources.subtitles.installed'))
  emit('installed')
  emit('update:visible', false)
}
</script>
