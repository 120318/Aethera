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
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

import { installSubtitle, previewSubtitle, searchSubtitles } from '@/api/resource'
import { useNotificationStore } from '@/stores/notification'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  visible: { type: Boolean, default: false },
  resource: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'installed'])
const { t } = useI18n()
const notification = useNotificationStore()
const loading = ref(false)
const installingId = ref('')
const candidates = ref([])
const previewingId = ref('')
const previewCandidateId = ref('')
const previewContent = ref('')

async function load() {
  if (!props.visible || !props.resource?.id) return
  loading.value = true
  candidates.value = []
  try {
    const response = await searchSubtitles(props.resource.id)
    candidates.value = response?.items || []
  } finally {
    loading.value = false
  }
}

async function preview(candidate) {
  previewingId.value = candidate.id
  try {
    const result = await previewSubtitle(candidate.file_id)
    previewCandidateId.value = candidate.id
    previewContent.value = result?.content || ''
  } finally {
    previewingId.value = ''
  }
}

async function install(candidate) {
  installingId.value = candidate.id
  try {
    await installSubtitle({
      file_id: props.resource.id,
      candidate_file_id: candidate.file_id,
      language: candidate.language,
      format: candidate.format,
    })
    notification.success(t('localResources.subtitles.installed'))
    emit('installed')
    emit('update:visible', false)
  } finally {
    installingId.value = ''
  }
}

watch(() => [props.visible, props.resource?.id], load, { immediate: true })
</script>
