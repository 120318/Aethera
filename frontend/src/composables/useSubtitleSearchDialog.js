import { ref, watch } from 'vue'

import { installSubtitle, previewSubtitle, searchSubtitles } from '@/api/resource'

export function useSubtitleSearchDialog(visible, resource) {
  const loading = ref(false)
  const installingId = ref('')
  const candidates = ref([])
  const previewingId = ref('')
  const previewCandidateId = ref('')
  const previewContent = ref('')

  let generation = 0
  let activeFileId = ''
  let previewRequest = 0

  function reset() {
    loading.value = false
    installingId.value = ''
    candidates.value = []
    previewingId.value = ''
    previewCandidateId.value = ''
    previewContent.value = ''
  }

  function isCurrent(requestGeneration, fileId) {
    return requestGeneration === generation && fileId === activeFileId
  }

  async function load(fileId, requestGeneration) {
    loading.value = true
    try {
      const response = await searchSubtitles(fileId)
      if (isCurrent(requestGeneration, fileId)) candidates.value = response?.items || []
    } finally {
      if (isCurrent(requestGeneration, fileId)) loading.value = false
    }
  }

  async function preview(candidate) {
    const fileId = activeFileId
    const requestGeneration = generation
    const requestId = ++previewRequest
    previewingId.value = candidate.id
    try {
      const result = await previewSubtitle(candidate.file_id)
      if (isCurrent(requestGeneration, fileId) && requestId === previewRequest) {
        previewCandidateId.value = candidate.id
        previewContent.value = result?.content || ''
      }
    } finally {
      if (isCurrent(requestGeneration, fileId) && requestId === previewRequest) {
        previewingId.value = ''
      }
    }
  }

  async function install(candidate) {
    const fileId = activeFileId
    const requestGeneration = generation
    if (!fileId) return false
    installingId.value = candidate.id
    try {
      await installSubtitle({
        file_id: fileId,
        candidate_file_id: candidate.file_id,
        language: candidate.language,
        format: candidate.format,
      })
      return isCurrent(requestGeneration, fileId)
    } finally {
      if (isCurrent(requestGeneration, fileId)) installingId.value = ''
    }
  }

  watch(
    () => [visible.value, resource.value?.id],
    ([isVisible, fileId]) => {
      generation += 1
      previewRequest += 1
      activeFileId = isVisible && fileId ? fileId : ''
      reset()
      if (activeFileId) void load(activeFileId, generation)
    },
    { immediate: true },
  )

  return {
    loading,
    installingId,
    candidates,
    previewingId,
    previewCandidateId,
    previewContent,
    preview,
    install,
  }
}
