import { useOperationsStore } from '@/stores/operations'

function resolveTaskId(task) {
  return task?.id || task?.task_data?.id || ''
}

export function useTaskOperations(emit) {
  const operations = useOperationsStore()

  async function submitTaskCommand(type, task, extraPayload = {}) {
    const taskId = resolveTaskId(task)
    if (!taskId) return null
    const command = await operations.submitCommand(
      {
        type,
        payload: {
          task_id: taskId,
          ...extraPayload,
        },
      },
      { dedupeKey: `task:${taskId}:${type}` },
    )
    if (command) emit('command-submitted', command)
    return command
  }

  function isTaskPending(task) {
    const taskId = resolveTaskId(task)
    return !!taskId && (
      operations.isTargetBusy('task', taskId)
      || [...operations.submittingKeys].some(key => key.startsWith(`task:${taskId}:`))
    )
  }

  async function handlePause(task) {
    return submitTaskCommand('task.pause', task)
  }

  async function handleResume(task) {
    return submitTaskCommand('task.resume', task)
  }

  async function handleManualTransfer(task) {
    return submitTaskCommand('task.transfer', task)
  }

  async function handleMediaServerSync(task) {
    return submitTaskCommand('task.media_server_sync', task)
  }

  async function handleDanmuGenerate(task) {
    return submitTaskCommand('task.danmu_generate', task)
  }

  async function handleDelete(task, options = {}) {
    const { force = false, deleteLibraryFiles = false, deleteFiles = true } = options
    return submitTaskCommand('task.delete', task, {
      delete_files: !!deleteFiles,
      force: !!force,
      delete_library_files: !!deleteLibraryFiles,
    })
  }

  return {
    isTaskPending,
    handlePause,
    handleResume,
    handleManualTransfer,
    handleMediaServerSync,
    handleDanmuGenerate,
    handleDelete,
  }
}
