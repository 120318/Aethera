const BUILTIN_RESOURCE_ACTIONS = {
  'danmu.generate.library_file': {
    labelKey: 'taskLive.actions.danmuGenerate',
    availabilityAction: 'danmu_generate',
    execute: ({ submitCommand, resource }) => submitCommand(
      'addon.run',
      resource,
      { addon_id: 'danmu', operation_id: 'generate' },
    ),
  },
  'subtitles.search.library_file': {
    labelKey: 'localResources.subtitles.search',
    supports: resource => !resource.is_package,
    execute: ({ openSubtitleSearch, resource }) => openSubtitleSearch(resource),
  },
  'danmu.generate.task': {
    taskAction: {
      id: 'danmu_generate',
      icon: 'pi pi-comments',
      commandTypes: ['addon.run'],
    },
  },
}

export function resolveLibraryAddonActions(addons) {
  const result = []
  for (const addon of addons || []) {
    if (!addon?.enabled) continue
    for (const contribution of addon.resource_actions || []) {
      if (contribution?.target_type !== 'library_file') continue
      const builtin = BUILTIN_RESOURCE_ACTIONS[contribution.id]
      if (!builtin) continue
      result.push({
        ...builtin,
        id: contribution.id,
        addonId: addon.name,
        interactionKind: contribution.interaction_kind,
      })
    }
  }
  return result
}

export function resolveTaskAddonActions(addons, { t, handleDanmuGenerate }) {
  const result = []
  for (const addon of addons || []) {
    if (!addon?.enabled) continue
    for (const contribution of addon.resource_actions || []) {
      if (contribution?.target_type !== 'task') continue
      const taskAction = BUILTIN_RESOURCE_ACTIONS[contribution.id]?.taskAction
      if (!taskAction) continue
      if (contribution.id === 'danmu.generate.task') {
        result.push({
          ...taskAction,
          severity: 'secondary',
          label: t('taskLive.actions.danmuGenerate'),
          tooltip: t('taskLive.actions.danmuGenerate'),
          menuOnly: true,
          handler: (event, task) => handleDanmuGenerate(task),
        })
      }
    }
  }
  return result
}
