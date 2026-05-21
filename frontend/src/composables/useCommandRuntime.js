import { computed, onUnmounted, ref, watch } from 'vue'
import { useOperationsStore } from '@/stores/operations'

const DEFAULT_POLL_INTERVAL_MS = 3000
const TERMINAL_STATUSES = ['succeeded', 'failed', 'cancelled']

function isTerminalCommand(command) {
  return TERMINAL_STATUSES.includes(command?.status)
}

export function useCommandRuntime(options = {}) {
  const operations = useOperationsStore()
  const {
    scope,
    commandTypes = [],
    pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
    onTerminal,
  } = options
  const inFlightIds = new Set()
  const handledTerminalIds = new Set()
  const pollTimer = ref(null)

  const activeCommands = computed(() => {
    const currentScope = typeof scope === 'function' ? scope() : scope
    if (!currentScope) return []
    if (currentScope.mediaId) {
      return operations.getActiveCommandsForMedia(currentScope.mediaId, {
        seasonNumber: currentScope.seasonNumber || null,
        types: commandTypes,
      })
    }
    if (currentScope.targetType && currentScope.targetId) {
      return operations.getActiveCommandsForTarget(
        currentScope.targetType,
        currentScope.targetId,
        commandTypes,
      )
    }
    if (currentScope.targetType && Array.isArray(currentScope.targetIds)) {
      const commands = currentScope.targetIds.flatMap((targetId) => {
        if (currentScope.targetType === 'media') {
          return operations.getActiveCommandsForMedia(targetId, { types: commandTypes })
        }
        return operations.getActiveCommandsForTarget(currentScope.targetType, targetId, commandTypes)
      })
      return [...new Map(commands.filter(command => command?.id).map(command => [command.id, command])).values()]
    }
    return []
  })

  async function refreshActiveCommands() {
    const currentScope = typeof scope === 'function' ? scope() : scope
    if (!currentScope) return
    if (currentScope.mediaId) {
      const params = { media_id: currentScope.mediaId }
      if (currentScope.seasonNumber) params.season_number = currentScope.seasonNumber
      if (commandTypes.length > 0) params.types = commandTypes
      await operations.refreshActiveCommands(params)
      return
    }
    if (currentScope.targetType) {
      if (!currentScope.targetId && Array.isArray(currentScope.targetIds) && currentScope.targetIds.length === 0) return
      const params = { target_type: currentScope.targetType }
      if (currentScope.targetId) params.target_id = currentScope.targetId
      if (Array.isArray(currentScope.targetIds)) params.target_ids = currentScope.targetIds
      if (commandTypes.length > 0) params.types = commandTypes
      await operations.refreshActiveCommands(params)
    }
  }

  async function pollCommand(command) {
    if (!command?.id || inFlightIds.has(command.id)) return
    inFlightIds.add(command.id)
    try {
      const latest = await operations.fetchCommandById(command.id)
      const terminalCommand = latest || command
      if (!isTerminalCommand(terminalCommand) || handledTerminalIds.has(command.id)) return
      handledTerminalIds.add(command.id)
      await onTerminal?.(terminalCommand, command)
    } finally {
      inFlightIds.delete(command.id)
    }
  }

  async function pollActiveCommands() {
    const commands = activeCommands.value
    if (commands.length === 0) return
    for (const command of commands) {
      await pollCommand(command)
    }
  }

  function startPolling() {
    if (pollTimer.value) return
    void pollActiveCommands()
    pollTimer.value = window.setInterval(pollActiveCommands, pollIntervalMs)
  }

  function stopPolling() {
    if (!pollTimer.value) return
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }

  watch(
    () => activeCommands.value.map(command => `${command.id}:${command.status}`).join(','),
    () => {
      if (activeCommands.value.length > 0) {
        startPolling()
        return
      }
      stopPolling()
    },
    { immediate: true },
  )

  onUnmounted(stopPolling)

  return {
    activeCommands,
    refreshActiveCommands,
    pollActiveCommands,
    startPolling,
    stopPolling,
  }
}
