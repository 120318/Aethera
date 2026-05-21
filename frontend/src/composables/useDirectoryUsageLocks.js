import { computed, ref } from 'vue'
import { getDirectoryUsage } from '@/api/config'

function emptyUsage() {
  return {
    task_count: 0,
    subscription_count: 0,
    directory_count: 0,
    library_file_count: 0,
    is_default: false,
  }
}

function count(value) {
  return Number(value || 0)
}

function pathLocked(usage) {
  return count(usage?.library_file_count) > 0
}

function downloadPathLocked(usage) {
  return count(usage?.task_count) > 0 || count(usage?.library_file_count) > 0
}

export function useDirectoryUsageLocks() {
  const usage = ref(emptyUsage())
  const usageLoading = ref(false)

  async function loadDirectoryUsage(directoryId) {
    if (!directoryId) {
      usage.value = emptyUsage()
      return usage.value
    }
    usageLoading.value = true
    try {
      const response = await getDirectoryUsage(directoryId)
      usage.value = {
        ...emptyUsage(),
        ...(response?.usage || {}),
      }
      return usage.value
    } finally {
      usageLoading.value = false
    }
  }

  async function validateDirectoryPathChanges(original, next) {
    if (!original || !next || !next.id) return { allowed: true, usage: emptyUsage(), reason: '' }
    const latestUsage = await loadDirectoryUsage(next.id)
    if (original.path !== next.path && pathLocked(latestUsage)) {
      return { allowed: false, usage: latestUsage, reason: 'path' }
    }
    if (original.download_path !== next.download_path && downloadPathLocked(latestUsage)) {
      return { allowed: false, usage: latestUsage, reason: 'download_path' }
    }
    return { allowed: true, usage: latestUsage, reason: '' }
  }

  return {
    usage,
    usageLoading,
    isPathLocked: computed(() => pathLocked(usage.value)),
    isDownloadPathLocked: computed(() => downloadPathLocked(usage.value)),
    loadDirectoryUsage,
    validateDirectoryPathChanges,
  }
}
