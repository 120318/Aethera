import { defineAsyncComponent } from 'vue'

const AuthAddonCard = defineAsyncComponent(() => import('@/components/config/addons/AuthAddonCard.vue'))
const DanmuAddonCard = defineAsyncComponent(() => import('@/components/config/addons/DanmuAddonCard.vue'))
const NotificationsAddonCard = defineAsyncComponent(() => import('@/components/config/addons/NotificationsAddonCard.vue'))
const SubtitlesAddonCard = defineAsyncComponent(() => import('@/components/config/addons/SubtitlesAddonCard.vue'))

const BUILTIN_ADDONS = {
  auth: {
    initialConfig: () => ({
      enabled: false,
      default_provider_id: null,
      providers: [],
    }),
    settings: {
      component: AuthAddonCard,
      aliases: ['auth_providers'],
      visible: () => import.meta.env.VITE_AETHERA_EXPERIMENTAL_OIDC_AUTH === '1',
    },
  },
  notifications: {
    initialConfig: () => ({
      enabled: false,
      channels: [],
    }),
    settings: {
      component: NotificationsAddonCard,
      aliases: ['telegram'],
    },
  },
  subtitles: {
    initialConfig: () => ({
      enabled: false,
      provider: 'opensubtitles',
      api_key: '',
      username: '',
      password: '',
      languages: ['zh-cn', 'zh-tw', 'en'],
      auto_fill_enabled: false,
    }),
    settings: {
      component: SubtitlesAddonCard,
    },
    resourceActions: {
      'subtitles.search.library_file': {
        labelKey: 'localResources.subtitles.search',
        supports: resource => !resource.is_package,
        execute: ({ openSubtitleSearch, resource }) => openSubtitleSearch(resource),
      },
    },
  },
  danmu: {
    initialConfig: () => ({
      enabled: false,
      directory_ids: [],
      providers: ['iqiyi', 'bilibili', 'youku', 'qq'],
      backfill_enabled: true,
      backfill_interval_seconds: 21600,
      backfill_recent_days: 30,
      backfill_missing_window_days: 90,
      output_xml: true,
      output_ass: true,
      font_size: 60,
      font_opacity_percent: 80,
      scroll_duration_seconds: 20,
      density_percent: 20,
      display_area: 'top',
    }),
    settings: {
      component: DanmuAddonCard,
      props: ({ servicesConfig }) => ({ servicesConfig }),
    },
    resourceActions: {
      'danmu.generate.library_file': {
        labelKey: 'taskLive.actions.danmuGenerate',
        execute: ({ submitCommand, resource }) => submitCommand(
          'addon.run',
          resource,
          { addon_id: 'danmu', operation_id: 'generate' },
        ),
      },
      'danmu.generate.task': {
        taskAction: ({ t, handleDanmuGenerate }) => ({
          id: 'danmu_generate',
          icon: 'pi pi-comments',
          severity: 'secondary',
          label: t('taskLive.actions.danmuGenerate'),
          tooltip: t('taskLive.actions.danmuGenerate'),
          commandTypes: ['addon.run'],
          menuOnly: true,
          addonAction: true,
          supports: task => !!task?.has_primary_library_files,
          handler: (event, task) => handleDanmuGenerate(task),
        }),
      },
    },
  },
}

export function createInitialAddonConfig() {
  return Object.fromEntries(
    Object.entries(BUILTIN_ADDONS).map(([id, addon]) => [id, addon.initialConfig()]),
  )
}

export function resolveAddonSettings(context) {
  return Object.entries(BUILTIN_ADDONS).flatMap(([id, addon]) => {
    const settings = addon.settings
    if (!settings || settings.visible?.() === false) return []
    return [{
      id,
      aliases: settings.aliases || [],
      component: settings.component,
      props: settings.props?.(context) || {},
    }]
  })
}

export function resolveLibraryAddonActions(addons) {
  const result = []
  for (const addon of addons || []) {
    if (!addon?.enabled) continue
    const registered = BUILTIN_ADDONS[addon.name]
    for (const contribution of addon.resource_actions || []) {
      if (contribution?.target_type !== 'library_file') continue
      const action = registered?.resourceActions?.[contribution.id]
      if (!action) continue
      result.push({
        ...action,
        id: contribution.id,
        addonId: addon.name,
        interactionKind: contribution.interaction_kind,
      })
    }
  }
  return result
}

export function resolveTaskAddonActions(addons, context) {
  const result = []
  for (const addon of addons || []) {
    if (!addon?.enabled) continue
    const registered = BUILTIN_ADDONS[addon.name]
    for (const contribution of addon.resource_actions || []) {
      if (contribution?.target_type !== 'task') continue
      const taskAction = registered?.resourceActions?.[contribution.id]?.taskAction
      if (taskAction) result.push(taskAction(context))
    }
  }
  return result
}
