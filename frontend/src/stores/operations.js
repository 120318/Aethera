import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getActiveActions } from '@/api/actions'
import { cancelCommand as cancelCommandApi, createCommand, getActiveCommands, getCommand, getCommands } from '@/api/commands'
import { buildMediaTarget, mediaTargetKey } from '@/composables/mediaIdentitySupport'
import { useAlertCenterStore } from '@/stores/alert-center'
import { t } from '@/i18n'
const RECENT_LIMIT = 20
const FINISHED_STATUSES = ['succeeded', 'failed', 'cancelled']
const ACTIVE_STATUSES = ['queued', 'running']

function commandMediaTarget(command) {
  const target = command?.target
  const mediaId = target?.media_id
    || command?.media_id
    || (command?.target_type === 'media' ? command?.target_id : '')
  if (!mediaId) return null
  return buildMediaTarget({
    media_id: mediaId,
    season_number: target?.season_number ?? command?.target_season_number,
  })
}

function commandTargetKey(command) {
  if (!command?.target_type || !command?.target_id) return ''
  if (command.target_type === 'media') {
    return `media:${mediaTargetKey(commandMediaTarget(command) || { media_id: command.target_id })}`
  }
  return `${command.target_type}:${command.target_id}`
}

function commandIsActive(command) {
  return ACTIVE_STATUSES.includes(command?.status)
}

function commandMatchesTypes(command, commandTypes = []) {
  return commandTypes.length === 0 || commandTypes.includes(command?.type)
}

function targetKey(targetType, targetId, options = {}) {
  if (!targetType || !targetId) return ''
  if (targetType !== 'media') return `${targetType}:${targetId}`
  return `media:${mediaTargetKey({ media_id: targetId, season_number: options.seasonNumber ?? options.season_number })}`
}

function commandMatchesMediaScope(command, mediaId, seasonNumber = null) {
  if (!mediaId) return false
  const target = commandMediaTarget(command)
  if (!target?.media_id || target.media_id !== mediaId) return false
  const commandSeasonNumber = target.season_number || null
  return !seasonNumber || commandSeasonNumber === seasonNumber
}

function paramsTargetKeys(params = {}) {
  if (!params.target_type) return new Set()
  const targetIds = []
  if (params.target_id) targetIds.push(params.target_id)
  if (Array.isArray(params.target_ids)) {
    for (const item of params.target_ids) {
      if (item) targetIds.push(String(item))
    }
  }
  return new Set(targetIds.map((targetId) => {
    if (params.target_type !== 'media') return `${params.target_type}:${targetId}`
    return `media:${mediaTargetKey({ media_id: targetId, season_number: params.season_number })}`
  }))
}

function paramsMediaWorkKeys(params = {}) {
  if (params.target_type !== 'media') return new Set()
  const targetIds = paramsTargetIds(params)
  return new Set([...targetIds].map(targetId => `media:${mediaTargetKey({ media_id: targetId })}`))
}

function paramsTargetIds(params = {}) {
  const targetIds = []
  if (params.target_id) targetIds.push(String(params.target_id))
  if (Array.isArray(params.target_ids)) {
    for (const item of params.target_ids) {
      if (item) targetIds.push(String(item))
    }
  }
  return new Set(targetIds)
}

function dedupeCommandsById(commands) {
  const seen = new Set()
  const deduped = []
  for (const command of commands || []) {
    if (!command?.id || seen.has(command.id)) continue
    seen.add(command.id)
    deduped.push(command)
  }
  return deduped
}

function commandCoveredByParams(command, params = {}, scopedTargetIds = new Set(), scopedKeys = new Set()) {
  const scopedTypes = params.types || params.command_types || []
  if (Array.isArray(scopedTypes) && scopedTypes.length > 0 && !scopedTypes.includes(command?.type)) {
    return false
  }
  if (params.media_id) {
    return commandMatchesMediaScope(command, params.media_id, params.season_number || null)
  }
  if (command?.target_type !== params.target_type) return false
  if (scopedTargetIds.size === 0) return true
  if (params.target_type === 'media') {
    return scopedKeys.has(commandTargetKey(command)) || paramsMediaWorkKeys(params).has(commandTargetKey(command))
  }
  return scopedKeys.has(commandTargetKey(command))
}

export const useOperationsStore = defineStore('operations', () => {
  const activeActions = ref([])
  const activeCommands = ref([])
  const recentCommands = ref([])
  const submittingKeys = ref(new Set())
  const loading = ref(false)
  const recentLoading = ref(false)
  const lastError = ref('')

  const allCommands = computed(() => {
    const seen = new Set()
    const merged = []
    for (const command of [...activeCommands.value, ...recentCommands.value]) {
      if (!command?.id || seen.has(command.id)) continue
      seen.add(command.id)
      merged.push(command)
    }
    return merged
  })

  const activeCount = computed(() => activeCommands.value.length)
  const activeActionCount = computed(() => activeActions.value.length)

  const activeByTargetKey = computed(() => {
    const map = new Map()
    for (const command of activeCommands.value) {
      const key = commandTargetKey(command)
      if (!key) continue
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(command)
    }
    return map
  })

  const byId = computed(() => {
    const map = new Map()
    for (const command of allCommands.value) {
      map.set(command.id, command)
    }
    return map
  })

  function registerSubmittedCommand(command) {
    if (!command?.id) return
    activeCommands.value = [
      command,
      ...activeCommands.value.filter(item => item?.id !== command.id),
    ]
  }

  function markSubmitting(key) {
    if (!key) return
    const next = new Set(submittingKeys.value)
    next.add(key)
    submittingKeys.value = next
  }

  function clearSubmitting(key) {
    if (!key || !submittingKeys.value.has(key)) return
    const next = new Set(submittingKeys.value)
    next.delete(key)
    submittingKeys.value = next
  }

  function isSubmittingKey(key) {
    return !!key && submittingKeys.value.has(key)
  }

  async function submitCommand(request, options = {}) {
    const dedupeKey = options.dedupeKey || ''
    if (dedupeKey && isSubmittingKey(dedupeKey)) return null
    markSubmitting(dedupeKey)
    try {
      const command = await createCommand(request)
      registerSubmittedCommand(command)
      useAlertCenterStore().notifyActivity()
      return command
    } finally {
      clearSubmitting(dedupeKey)
    }
  }

  function cacheCommand(command) {
    if (!command?.id) return null

    if (command.status === 'queued' || command.status === 'running') {
      activeCommands.value = [
        command,
        ...activeCommands.value.filter(item => item?.id !== command.id),
      ]
      recentCommands.value = recentCommands.value.filter(item => item?.id !== command.id)
      useAlertCenterStore().notifyActivity()
      return command
    }

    activeCommands.value = activeCommands.value.filter(item => item?.id !== command.id)
    recentCommands.value = [
      command,
      ...recentCommands.value.filter(item => item?.id !== command.id),
    ].slice(0, RECENT_LIMIT)
    return command
  }

  function mergeScopedActiveCommands(commands, params = {}) {
    const nextCommands = dedupeCommandsById(commands)
    if (!params.target_type && !params.media_id) {
      activeCommands.value = nextCommands
      return
    }

    const scopedKeys = paramsTargetKeys(params)
    const scopedTargetIds = paramsTargetIds(params)
    const nextIds = new Set(nextCommands.map(command => command.id))

    const retained = activeCommands.value.filter(command => {
      if (!command?.id || nextIds.has(command.id)) return false
      return !commandCoveredByParams(command, params, scopedTargetIds, scopedKeys)
    })

    activeCommands.value = [...nextCommands, ...retained]
  }

  function hydrateActiveCommands(commands, params = {}) {
    mergeScopedActiveCommands(commands, params)
  }

  async function refreshActiveCommands(params = {}) {
    loading.value = true
    try {
      const commands = await getActiveCommands(params)
      mergeScopedActiveCommands(commands, params)
      lastError.value = ''
    } catch (error) {
      lastError.value = error?.message || t('operations.loadStatusFailed')
    } finally {
      loading.value = false
    }
  }

  async function refreshActiveActions(params = {}) {
    loading.value = true
    try {
      const data = await getActiveActions(params)
      activeActions.value = data.items || []
      lastError.value = ''
    } catch (error) {
      lastError.value = error?.message || t('operations.loadStatusFailed')
    } finally {
      loading.value = false
    }
  }

  async function refreshRecentCommands() {
    recentLoading.value = true
    try {
      recentCommands.value = await getCommands({
        limit: RECENT_LIMIT,
        statuses: FINISHED_STATUSES,
      })
      lastError.value = ''
    } catch (error) {
      lastError.value = error?.message || t('operations.loadRecordsFailed')
    } finally {
      recentLoading.value = false
    }
  }

  async function refreshAll() {
    await Promise.all([refreshActiveActions(), refreshActiveCommands(), refreshRecentCommands()])
  }

  async function fetchCommandById(commandId) {
    if (!commandId) return null
    try {
      const command = await getCommand(commandId)
      lastError.value = ''
      return cacheCommand(command)
    } catch (error) {
      lastError.value = error?.message || t('operations.loadStatusFailed')
      return null
    }
  }

  async function cancelCommand(commandId) {
    if (!commandId) return null
    try {
      const command = await cancelCommandApi(commandId)
      lastError.value = ''
      return cacheCommand(command)
    } catch (error) {
      lastError.value = error?.message || t('operations.loadStatusFailed')
      throw error
    }
  }

  function getActiveCommandsForMedia(mediaId, options = {}) {
    const seasonNumber = options.seasonNumber ?? options.season_number ?? null
    const commandTypes = Array.isArray(options.types) ? options.types : []
    return activeCommands.value.filter(command => (
      commandIsActive(command)
      && commandMatchesMediaScope(command, mediaId, seasonNumber)
      && commandMatchesTypes(command, commandTypes)
    ))
  }

  function getActiveCommandsForTarget(targetType, targetId, commandTypes = [], options = {}) {
    const key = targetKey(targetType, targetId, options)
    if (!key) return []
    return (activeByTargetKey.value.get(key) || []).filter(command => (
      commandIsActive(command) && commandMatchesTypes(command, commandTypes)
    ))
  }

  function getActiveCommandByTarget(targetType, targetId, commandTypes = [], options = {}) {
    const commands = getActiveCommandsForTarget(targetType, targetId, commandTypes, options)
    return commands[0] || null
  }

  function isTargetBusy(targetType, targetId, commandTypes = [], options = {}) {
    return getActiveCommandsForTarget(targetType, targetId, commandTypes, options).length > 0
  }

  function getCommandById(commandId) {
    return byId.value.get(commandId) || null
  }

  return {
    activeCommands,
    activeActions,
    recentCommands,
    submittingKeys,
    loading,
    recentLoading,
    lastError,
    allCommands,
    activeCount,
    activeActionCount,
    registerSubmittedCommand,
    submitCommand,
    cancelCommand,
    fetchCommandById,
    refreshActiveCommands,
    refreshActiveActions,
    hydrateActiveCommands,
    refreshRecentCommands,
    refreshAll,
    getActiveCommandsForMedia,
    getActiveCommandsForTarget,
    getActiveCommandByTarget,
    getCommandById,
    isSubmittingKey,
    isTargetBusy,
  }
})
