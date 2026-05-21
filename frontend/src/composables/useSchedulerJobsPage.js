import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { saveSchedulerConfig } from '@/api/config'
import { getSchedulerJobs, triggerSchedulerJob } from '@/api/scheduler'
import {
  formatSchedulerConfigSource,
  formatSchedulerDateTime,
  formatSchedulerDuration,
  formatSchedulerJobDescription,
  formatSchedulerJobName,
  formatSchedulerSourceLabel,
  formatSchedulerTriggerLabel,
} from '@/composables/schedulerJobsSupport'
import { useSystemConfig } from '@/composables/useSystemConfig'
import { useNotificationStore } from '@/stores/notification'
import { useI18n } from 'vue-i18n'

export function useSchedulerJobsPage() {
  const route = useRoute()
  const router = useRouter()
  const notification = useNotificationStore()
  const { t } = useI18n()
  const { system, fetchSystemConfig } = useSystemConfig()

  const loading = ref(false)
  const jobs = ref([])
  const lastError = ref('')
  const editableIntervals = ref({})
  const savingJobId = ref('')
  const triggeringJobId = ref('')
  const intervalDialogVisible = ref(false)
  const editingIntervalJobId = ref('')
  const editingIntervalValue = ref(0)
  const historyDialogVisible = ref(false)
  const historyDialogJobId = ref('')
  const historyDialogJobName = ref('')

  function syncEditableIntervals() {
    editableIntervals.value = Object.fromEntries(
      jobs.value
        .filter(job => job.editable_in_scheduler)
        .map(job => [job.id, job.interval_seconds || 0]),
    )
  }

  function openIntervalDialog(job) {
    editingIntervalJobId.value = job.id
    editingIntervalValue.value = Number(editableIntervals.value[job.id] || job.interval_seconds || 0)
    intervalDialogVisible.value = true
  }

  function closeIntervalDialog() {
    intervalDialogVisible.value = false
    editingIntervalJobId.value = ''
    editingIntervalValue.value = 0
  }

  const canSaveEditingInterval = computed(() => {
    const job = jobs.value.find(item => item.id === editingIntervalJobId.value)
    if (!job) return false
    const nextValue = Number(editingIntervalValue.value || 0)
    return job.editable_in_scheduler && nextValue >= 1 && nextValue !== Number(job.interval_seconds || 0)
  })

  async function refreshJobs() {
    loading.value = true
    try {
      const data = await getSchedulerJobs()
      jobs.value = data.items || []
      syncEditableIntervals()
      lastError.value = ''
    } catch (error) {
      lastError.value = error?.message || t('scheduler.loadFailed')
    } finally {
      loading.value = false
    }
  }

  const historyDialogTitle = computed(() => (
    historyDialogJobName.value ? t('scheduler.historyTitleWithName', { name: historyDialogJobName.value }) : t('scheduler.history')
  ))

  function openHistoryDialog(job) {
    historyDialogJobId.value = job.id
    historyDialogJobName.value = formatSchedulerJobName(job)
    historyDialogVisible.value = true
  }

  function openConfig(job) {
    if (job.id === 'media_server_sync_incremental_sweep') {
      router.push({
        path: '/settings',
        hash: '#mediaserver',
        query: route.query,
      })
      return
    }
    if (job.config_scope === 'addon') {
      router.push({
        path: '/settings',
        hash: '#addon',
        query: { focus: job.config_target || job.source_name || '' },
      })
      return
    }
    router.push({
      path: '/settings',
      hash: '#system',
    })
  }

  async function saveInterval(job) {
    const field = job.config_target
    const nextValue = Number(editableIntervals.value[job.id] || 0)
    if (!field || nextValue < 1) return
    savingJobId.value = job.id
    try {
      const nextSchedulerConfig = {
        ...system.scheduler,
        [field]: nextValue,
      }
      await saveSchedulerConfig({ scheduler: nextSchedulerConfig })
      system.scheduler = nextSchedulerConfig
      notification.success(t('scheduler.intervalSaved'))
      await refreshJobs()
    } finally {
      savingJobId.value = ''
    }
  }

  async function saveEditingInterval() {
    const job = jobs.value.find(item => item.id === editingIntervalJobId.value)
    if (!job) return
    editableIntervals.value[job.id] = Number(editingIntervalValue.value || 0)
    await saveInterval(job)
    if (!savingJobId.value) {
      closeIntervalDialog()
    }
  }

  async function triggerJob(job) {
    triggeringJobId.value = job.id
    try {
      await triggerSchedulerJob(job.id)
      notification.success(t('scheduler.jobTriggered'))
      window.setTimeout(() => {
        refreshJobs()
      }, 400)
    } finally {
      triggeringJobId.value = ''
    }
  }

  onMounted(async () => {
    await Promise.all([fetchSystemConfig(), refreshJobs()])
  })

  return {
    loading,
    jobs,
    lastError,
    savingJobId,
    triggeringJobId,
    intervalDialogVisible,
    editingIntervalJobId,
    editingIntervalValue,
    historyDialogVisible,
    historyDialogJobId,
    formatJobName: formatSchedulerJobName,
    formatJobDescription: formatSchedulerJobDescription,
    formatSourceLabel: formatSchedulerSourceLabel,
    formatTriggerLabel: formatSchedulerTriggerLabel,
    formatDateTime: formatSchedulerDateTime,
    formatDuration: formatSchedulerDuration,
    formatConfigSource: formatSchedulerConfigSource,
    canOpenConfig: (job) => job.config_scope === 'addon' || job.id === 'media_server_sync_incremental_sweep',
    openIntervalDialog,
    closeIntervalDialog,
    canSaveEditingInterval,
    historyDialogTitle,
    openHistoryDialog,
    openConfig,
    saveEditingInterval,
    triggerJob,
  }
}
