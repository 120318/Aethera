import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  clearDefaultNamingTemplate,
  createNamingTemplate,
  deleteNamingTemplate,
  previewNamingTemplate,
  setDefaultNamingTemplate,
  updateNamingTemplate,
} from '@/api/config'
import { useNotificationStore } from '@/stores/notification'

const MOVIE_VARIABLES = [
  { token: '{title}', descKey: 'settings.naming.variablesMap.title' },
  { token: '{year}', descKey: 'settings.naming.variablesMap.year' },
  { token: '{quality}', descKey: 'settings.naming.variablesMap.quality' },
  { token: '{resolution}', descKey: 'settings.naming.variablesMap.resolution' },
  { token: '{source}', descKey: 'settings.naming.variablesMap.source' },
  { token: '{group}', descKey: 'settings.naming.variablesMap.group' },
  { token: '{language}', descKey: 'settings.naming.variablesMap.language' },
  { token: '{audio}', descKey: 'settings.naming.variablesMap.audio' },
  { token: '{video_codec}', descKey: 'settings.naming.variablesMap.videoCodec' },
  { token: '{tmdb_id}', descKey: 'settings.naming.variablesMap.tmdbId' },
  { token: '{imdb_id}', descKey: 'settings.naming.variablesMap.imdbId' },
  { token: '{disc_package_name}', descKey: 'settings.naming.variablesMap.discPackageName' },
  { token: '{disc_folder}', descKey: 'settings.naming.variablesMap.discFolder' },
  { token: '{disc_suffix}', descKey: 'settings.naming.variablesMap.discSuffix' },
  { token: '{disc:00}', descKey: 'settings.naming.variablesMap.discIndex' },
  { token: '{package_layout}', descKey: 'settings.naming.variablesMap.packageLayout' },
]

const TV_VARIABLES = [
  { token: '{title}', descKey: 'settings.naming.variablesMap.title' },
  { token: '{year}', descKey: 'settings.naming.variablesMap.year' },
  { token: '{season:00}', descKey: 'settings.naming.variablesMap.season' },
  { token: '{episode:00}', descKey: 'settings.naming.variablesMap.episode' },
  { token: '{episode_title}', descKey: 'settings.naming.variablesMap.episodeTitle' },
  { token: '{quality}', descKey: 'settings.naming.variablesMap.quality' },
  { token: '{resolution}', descKey: 'settings.naming.variablesMap.resolution' },
  { token: '{source}', descKey: 'settings.naming.variablesMap.source' },
  { token: '{group}', descKey: 'settings.naming.variablesMap.group' },
  { token: '{language}', descKey: 'settings.naming.variablesMap.language' },
  { token: '{audio}', descKey: 'settings.naming.variablesMap.audio' },
  { token: '{video_codec}', descKey: 'settings.naming.variablesMap.videoCodec' },
  { token: '{disc_package_name}', descKey: 'settings.naming.variablesMap.discPackageName' },
  { token: '{disc_folder}', descKey: 'settings.naming.variablesMap.discFolder' },
  { token: '{disc_suffix}', descKey: 'settings.naming.variablesMap.discSuffix' },
  { token: '{disc:00}', descKey: 'settings.naming.variablesMap.discIndex' },
  { token: '{package_layout}', descKey: 'settings.naming.variablesMap.packageLayout' },
]

const DEFAULT_TEMPLATES = {
  movie: {
    dir_template: '{title} ({year})/{disc_package_name}',
    file_template: '{title} ({year}){disc_suffix}',
  },
  tv: {
    dir_template: '{title} ({year})/Season {season:00}/{disc_package_name}',
    file_template: '{title} - S{season:00}E{episode:00}{disc_suffix}',
  },
}

export function useNamingTemplateConfig(props) {
  const notification = useNotificationStore()
  const { t } = useI18n()
  const templateDialogVisible = ref(false)
  const currentTemplate = ref(createEmptyTemplate())
  const templateDialogTitle = ref('')
  const templateDialogMode = ref('add')
  const activeTemplateField = ref('file_template')
  const dirPreview = ref('')
  const filePreview = ref('')
  const fullPreview = ref('')
  const discDirPreview = ref('')
  const discFilePreview = ref('')
  const discFullPreview = ref('')
  const previewError = ref('')
  const templatePreviewTimer = ref(null)

  const availableVariables = computed(() => (
    (currentTemplate.value.type === 'tv' ? TV_VARIABLES : MOVIE_VARIABLES).map((item) => ({
      ...item,
      desc: item.descKey ? t(item.descKey) : item.desc,
    }))
  ))
  const hasPreview = computed(() => (
    Boolean(dirPreview.value || filePreview.value || fullPreview.value || discFullPreview.value || previewError.value)
  ))

  onUnmounted(() => {
    if (templatePreviewTimer.value) {
      window.clearTimeout(templatePreviewTimer.value)
    }
  })

  function createEmptyTemplate() {
    return {
      id: '',
      name: '',
      type: 'movie',
      dir_template: '',
      file_template: '',
      enabled: true,
      is_default: false,
    }
  }

  function cloneValue(value) {
    return JSON.parse(JSON.stringify(value))
  }

  function getDefaultTemplates(type) {
    return cloneValue(DEFAULT_TEMPLATES[type] || DEFAULT_TEMPLATES.movie)
  }

  function ensureTemplates() {
    return Array.isArray(props.config.naming_templates) ? props.config.naming_templates : []
  }

  function patchTemplateConfig(
    namingTemplates,
    defaultMovieTemplateId = props.config.default_movie_template_id,
    defaultTvTemplateId = props.config.default_tv_template_id,
  ) {
    props.applyConfigPatch({
      naming_templates: namingTemplates,
      default_movie_template_id: defaultMovieTemplateId,
      default_tv_template_id: defaultTvTemplateId,
    })
  }

  function showSuccess(message) {
    notification.success(message)
  }

  function showError(message) {
    notification.error(message)
  }

  function resetPreview() {
    dirPreview.value = ''
    filePreview.value = ''
    fullPreview.value = ''
    discDirPreview.value = ''
    discFilePreview.value = ''
    discFullPreview.value = ''
    previewError.value = ''
  }

  function addTemplate() {
    templateDialogVisible.value = true
    templateDialogTitle.value = t('settings.naming.addTitle')
    templateDialogMode.value = 'add'
    currentTemplate.value = {
      ...createEmptyTemplate(),
      id: `template_${Date.now()}`,
      name: t('settings.naming.newTemplate'),
      ...getDefaultTemplates('movie'),
    }
    activeTemplateField.value = 'file_template'
    updateTemplatePreview()
  }

  function editTemplate(template) {
    templateDialogVisible.value = true
    templateDialogTitle.value = t('settings.naming.editTitle')
    templateDialogMode.value = 'edit'
    currentTemplate.value = cloneValue(template)
    activeTemplateField.value = 'file_template'
    updateTemplatePreview()
  }

  function handleTemplateTypeChange(type) {
    currentTemplate.value.type = type
    Object.assign(currentTemplate.value, getDefaultTemplates(type))
    activeTemplateField.value = 'file_template'
    onTemplateContentChange()
  }

  async function saveTemplate() {
    if (!currentTemplate.value) return

    const currentTemplates = cloneValue(ensureTemplates())
    const previousDefaultMovieTemplateId = props.config.default_movie_template_id
    const previousDefaultTvTemplateId = props.config.default_tv_template_id

    try {
      let nextTemplates = currentTemplates
      let savedTemplate = cloneValue(currentTemplate.value)

      if (templateDialogMode.value === 'add') {
        const response = await createNamingTemplate({ template: currentTemplate.value })
        savedTemplate = cloneValue(response.template || currentTemplate.value)
        nextTemplates = [...currentTemplates, savedTemplate]
      } else {
        const response = await updateNamingTemplate({ template: currentTemplate.value })
        savedTemplate = cloneValue(response.template || currentTemplate.value)
        const index = currentTemplates.findIndex((item) => item.id === currentTemplate.value.id)
        if (index !== -1) {
          nextTemplates = [...currentTemplates]
          nextTemplates[index] = savedTemplate
        }
      }

      let nextDefaultMovieTemplateId = previousDefaultMovieTemplateId
      let nextDefaultTvTemplateId = previousDefaultTvTemplateId
      if (savedTemplate.is_default) {
        nextTemplates = nextTemplates.map((template) => {
          if (template.type === savedTemplate.type) {
            return { ...template, is_default: template.id === savedTemplate.id }
          }
          return template
        })

        if (savedTemplate.type === 'movie') {
          nextDefaultMovieTemplateId = savedTemplate.id
        } else if (savedTemplate.type === 'tv') {
          nextDefaultTvTemplateId = savedTemplate.id
        }
        await setDefaultNamingTemplate({ template_id: savedTemplate.id })
      } else if (
        previousDefaultMovieTemplateId === savedTemplate.id ||
        previousDefaultTvTemplateId === savedTemplate.id
      ) {
        await clearDefaultNamingTemplate({ template_type: savedTemplate.type })
        if (savedTemplate.type === 'movie') {
          nextDefaultMovieTemplateId = null
        } else if (savedTemplate.type === 'tv') {
          nextDefaultTvTemplateId = null
        }
      }

      patchTemplateConfig(nextTemplates, nextDefaultMovieTemplateId, nextDefaultTvTemplateId)
      templateDialogVisible.value = false
      showSuccess(templateDialogMode.value === 'add' ? t('settings.naming.added') : t('settings.naming.updated'))
    } catch (error) {
      showError(t('common.saveFailed', { message: error.message }))
    }
  }

  async function removeTemplate(templateId) {
    const templates = ensureTemplates()
    if (!templates.some((template) => template.id === templateId)) {
      return
    }

    try {
      await deleteNamingTemplate(templateId)
      patchTemplateConfig(templates.filter((template) => template.id !== templateId))
      showSuccess(t('settings.naming.deleted'))
    } catch (error) {
      showError(t('common.deleteFailed', { message: error.message }))
    }
  }

  async function toggleTemplateEnabled(template) {
    const templates = cloneValue(ensureTemplates())
    const index = templates.findIndex((item) => item.id === template.id)
    if (index === -1) return

    templates[index].enabled = !templates[index].enabled
    const shouldClearDefault = !templates[index].enabled && templates[index].is_default
    let nextDefaultMovieTemplateId = props.config.default_movie_template_id
    let nextDefaultTvTemplateId = props.config.default_tv_template_id

    if (shouldClearDefault) {
      templates[index].is_default = false
      if (templates[index].type === 'movie') {
        nextDefaultMovieTemplateId = null
      } else if (templates[index].type === 'tv') {
        nextDefaultTvTemplateId = null
      }
    }

    try {
      const response = await updateNamingTemplate({ template: templates[index] })
      templates[index] = cloneValue(response.template || templates[index])
      if (shouldClearDefault) {
        await clearDefaultNamingTemplate({ template_type: templates[index].type })
      }
      patchTemplateConfig(templates, nextDefaultMovieTemplateId, nextDefaultTvTemplateId)
      showSuccess(templates[index].enabled ? t('settings.naming.enabled') : t('settings.naming.disabled'))
    } catch (error) {
      showError(t('common.saveFailed', { message: error.message }))
    }
  }

  async function setDefaultTemplate(template) {
    try {
      await setDefaultNamingTemplate({ template_id: template.id })
      const nextTemplates = cloneValue(ensureTemplates()).map((current) => {
        if (current.type === template.type) {
          return { ...current, is_default: current.id === template.id }
        }
        return current
      })
      let nextDefaultMovieTemplateId = props.config.default_movie_template_id
      let nextDefaultTvTemplateId = props.config.default_tv_template_id
      if (template.type === 'movie') {
        nextDefaultMovieTemplateId = template.id
      } else if (template.type === 'tv') {
        nextDefaultTvTemplateId = template.id
      }
      patchTemplateConfig(nextTemplates, nextDefaultMovieTemplateId, nextDefaultTvTemplateId)
      showSuccess(t('settings.naming.defaultSet'))
    } catch (error) {
      showError(t('common.settingFailed', { message: error.message }))
    }
  }

  function onTemplateContentChange() {
    if (templatePreviewTimer.value) {
      window.clearTimeout(templatePreviewTimer.value)
    }
    templatePreviewTimer.value = window.setTimeout(() => {
      updateTemplatePreview()
    }, 400)
  }

  async function updateTemplatePreview() {
    if (!currentTemplate.value?.dir_template && !currentTemplate.value?.file_template) {
      resetPreview()
      return
    }

    try {
      const data = await previewNamingTemplate({
        dir_template: currentTemplate.value.dir_template,
        file_template: currentTemplate.value.file_template,
        media_type: currentTemplate.value.type,
      })
      dirPreview.value = data.dir_preview || ''
      filePreview.value = data.file_preview || ''
      fullPreview.value = data.preview_with_extension || data.preview || ''
      discDirPreview.value = data.disc_dir_preview || ''
      discFilePreview.value = data.disc_file_preview || ''
      discFullPreview.value = data.disc_preview_with_extension || data.disc_preview || ''
      previewError.value = ''
    } catch (error) {
      dirPreview.value = ''
      filePreview.value = ''
      fullPreview.value = ''
      discDirPreview.value = ''
      discFilePreview.value = ''
      discFullPreview.value = ''
      previewError.value = error.message || t('settings.naming.previewFailed')
    }
  }

  function insertVariable(variable) {
    const field = activeTemplateField.value || 'file_template'
    if (!currentTemplate.value) {
      currentTemplate.value = { ...createEmptyTemplate(), [field]: '' }
    }

    const currentValue = currentTemplate.value[field] || ''
    const input = document.getElementById(field === 'dir_template' ? 'dialog-dir-template' : 'dialog-file-template')
    if (input && input.selectionStart !== null) {
      const start = input.selectionStart
      const end = input.selectionEnd
      currentTemplate.value[field] = currentValue.substring(0, start) + variable + currentValue.substring(end)
      window.setTimeout(() => {
        input.focus()
        input.setSelectionRange(start + variable.length, start + variable.length)
      }, 0)
    } else {
      currentTemplate.value[field] = `${currentValue}${variable}`
    }

    onTemplateContentChange()
  }

  return {
    activeTemplateField,
    availableVariables,
    currentTemplate,
    discDirPreview,
    discFilePreview,
    discFullPreview,
    dirPreview,
    filePreview,
    fullPreview,
    handleTemplateTypeChange,
    hasPreview,
    addTemplate,
    editTemplate,
    onTemplateContentChange,
    insertVariable,
    removeTemplate,
    saveTemplate,
    setDefaultTemplate,
    templateDialogMode,
    templateDialogTitle,
    templateDialogVisible,
    toggleTemplateEnabled,
    previewError,
  }
}
