import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'primevue/useconfirm'
import { getDirectoryIntegrityLatest } from '@/api/config'
import { endCurrentSubscription, getSubscriptionState, updateMediaSubscriptionState } from '@/api/subscription'
import { useCommandRuntime } from '@/composables/useCommandRuntime'
import { useMediaManagement } from '@/composables/useMediaManagement'
import {
  buildMediaManagementSortOptions,
  buildMediaManagementSummaryCards,
  buildMediaManagementTypeOptions,
  buildMediaManagementStatusOptions,
  cloneManagedItem,
  getManagedItemActionLoading,
  getManagedItemKey,
  shouldKeepManagedItem,
} from '@/composables/mediaManagementPageSupport'
import {
  toggleManagedFollow,
  toggleManagedSubscription,
} from '@/composables/mediaManagementActionSupport'
import { buildMediaTarget } from '@/composables/mediaIdentitySupport'
import { useNotificationStore } from '@/stores/notification'
import { useOperationsStore } from '@/stores/operations'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'

const MEDIA_DELETE_COMMAND_TYPES = ['media.delete']

export function useMediaManagementPage() {
  const { t } = useI18n()
  const notification = useNotificationStore()
  const operations = useOperationsStore()
  const confirm = useConfirm()
  const {
    summary,
    items,
    summaryLoading,
    loading,
    filters,
    total,
    first,
    rows,
    onPage,
    patchItem,
    restoreItem,
    refreshSummary,
    refreshAll,
  } = useMediaManagement()

  const actionLoading = ref('')
  const directoryIntegrityResult = ref(null)
  const directoryIntegrityLoading = ref(false)
  const mediaLoaded = ref(false)
  const directoryIntegrityLoaded = ref(false)
  const deleteCommandRuntime = useCommandRuntime({
    scope: () => ({
      targetType: 'media',
      targetIds: items.value.map(item => item.media_id).filter(Boolean),
    }),
    commandTypes: MEDIA_DELETE_COMMAND_TYPES,
    onTerminal: handleDeleteCommandTerminal,
  })

  const summaryCards = computed(() => buildMediaManagementSummaryCards(summary.value, t))
  const mediaTypeOptions = computed(() => buildMediaManagementTypeOptions(t))
  const statusOptions = computed(() => buildMediaManagementStatusOptions(t))
  const sortOptions = computed(() => buildMediaManagementSortOptions(t))

  function getItemActionLoading(item) {
    return getManagedItemActionLoading(actionLoading.value, item)
  }

  function getItemKey(item) {
    return getManagedItemKey(item)
  }

  function isDeletePending(item) {
    if (!item?.media_id) return false
    return operations.isTargetBusy('media', item.media_id, MEDIA_DELETE_COMMAND_TYPES, {
      seasonNumber: item.season_number || null,
    })
  }

  function shouldKeepItem(item) {
    return shouldKeepManagedItem(item, filters.value)
  }

  function cloneItem(item) {
    return cloneManagedItem(item)
  }

  async function handleQuickToggleSubscription(item) {
    await toggleManagedSubscription({
      item,
      actionLoading,
      patchItem,
      restoreItem,
      cloneItem,
      shouldKeepItem,
      endCurrentSubscription,
      notification,
      refreshSummary,
      t,
    })
  }

  async function handleQuickToggleFollow(item) {
    await toggleManagedFollow({
      item,
      actionLoading,
      patchItem,
      restoreItem,
      cloneItem,
      shouldKeepItem,
      getSubscriptionState,
      updateMediaSubscriptionState,
      notification,
      refreshSummary,
      t,
    })
  }

  async function handleDeleteCommandTerminal(command) {
    if (command?.status === 'succeeded') {
      notification.success(t('mediaManagement.notifications.deleteCompleted'))
      await refreshAll()
      return
    }
    if (command?.status === 'failed') {
      notification.error(command.error || resolveLocalizedRecordMessage(command, t('mediaManagement.notifications.deleteFailed')))
      return
    }
    if (command?.status === 'cancelled') {
      notification.warn(t('mediaManagement.notifications.deleteCancelled'))
    }
  }

  function handleQuickDeleteFiles(item) {
    if (!item?.media_id) return
    confirm.require({
      message: t('mediaManagement.deleteConfirm.message'),
      header: t('mediaManagement.deleteConfirm.header'),
      icon: null,
      acceptLabel: t('mediaManagement.deleteConfirm.accept'),
      rejectLabel: t('common.cancel'),
      rejectProps: {
        severity: 'secondary',
        outlined: true,
      },
      acceptProps: {
        severity: 'primary',
      },
      accept: async () => {
        actionLoading.value = `delete:${getManagedItemKey(item)}`
        try {
          const target = buildMediaTarget({ media_id: item.media_id, seasonNumber: item.season_number || null })
          if (!target) {
            notification.warn(t('backendErrors.seasonRequired'))
            return
          }
          const command = await operations.submitCommand(
            {
              type: 'media.delete',
              initiator: 'manual',
              payload: {
                target,
                mode: 'tasks_and_library',
                delete_files: true,
                force: false,
              },
            },
            { dedupeKey: `media:${target.media_id}:${target.season_number || ''}:media.delete` },
          )
          if (command) {
            deleteCommandRuntime.startPolling()
            notification.success(t('mediaManagement.notifications.deleteSubmitted'))
          }
        } finally {
          actionLoading.value = ''
        }
      },
    })
  }

  async function loadDirectoryIntegrityLatest() {
    directoryIntegrityLoading.value = true
    try {
      const response = await getDirectoryIntegrityLatest()
      directoryIntegrityResult.value = response.result || null
      directoryIntegrityLoaded.value = true
    } catch (error) {
      notification.error(t('mediaManagement.directoryIntegrity.loadFailed', { message: error.message }))
    } finally {
      directoryIntegrityLoading.value = false
    }
  }

  async function loadMediaTab() {
    if (mediaLoaded.value) return
    await refreshAll()
    mediaLoaded.value = true
  }

  async function loadDirectoryIntegrityTab() {
    if (directoryIntegrityLoaded.value) return
    await loadDirectoryIntegrityLatest()
  }

  watch(
    () => items.value.map(item => `${item.media_id}:${item.season_number || ''}`).join(','),
    () => {
      void deleteCommandRuntime.refreshActiveCommands()
    },
  )

  return {
    summaryLoading,
    loading,
    items,
    filters,
    total,
    first,
    rows,
    onPage,
    summaryCards,
    directoryIntegrityResult,
    directoryIntegrityLoading,
    mediaTypeOptions,
    statusOptions,
    sortOptions,
    getItemActionLoading,
    getItemKey,
    isDeletePending,
    handleQuickToggleFollow,
    handleQuickToggleSubscription,
    handleQuickDeleteFiles,
    loadDirectoryIntegrityLatest,
    loadMediaTab,
    loadDirectoryIntegrityTab,
  }
}
