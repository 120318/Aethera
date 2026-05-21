import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { bootstrap, getBootstrapStatus } from '@/api/auth'
import { saveTMDBConfig, testDirectoryAccess, testServiceConnection } from '@/api/config'
import {
  bootstrapStepLabels,
  bootstrapStepOrder,
  createBootstrapConfigActions,
  getBootstrapNextStepKey,
  isBootstrapStepReady,
  resolveBootstrapNextPath,
  resolveBootstrapPageDescription,
  resolveBootstrapPageTitle,
  resolveBootstrapPageWidthClass,
  syncBootstrapSelectedStep,
} from '@/composables/bootstrapWizardSupport'
import { refreshBootstrapState, submitBootstrapPassword } from '@/composables/bootstrapWizardFlowSupport'
import { createBootstrapValidators } from '@/composables/bootstrapWizardValidationSupport'
import { useConfig } from '@/composables/useConfig'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import { useI18n } from 'vue-i18n'

export function useBootstrapWizard() {
  const route = useRoute()
  const router = useRouter()
  const authStore = useAuthStore()
  const notification = useNotificationStore()
  const { t } = useI18n()
  const { config, fetchConfig } = useConfig()

  const loading = ref(true)
  const working = ref(false)
  const tmdbSaving = ref(false)
  const password = ref('')
  const passwordConfirm = ref('')
  const selectedStep = ref('password')
  const bootstrapError = ref(false)
  const redirecting = ref(false)

  const downloaderConfigRef = ref(null)
  const indexerConfigRef = ref(null)
  const mediaServerConfigRef = ref(null)
  const templateConfigRef = ref(null)
  const directoryConfigRef = ref(null)

  const nextPath = computed(() => resolveBootstrapNextPath(route))
  const pageTitle = computed(() => resolveBootstrapPageTitle(authStore))
  const pageDescription = computed(() => resolveBootstrapPageDescription(authStore))
  const pageWidthClass = computed(() => resolveBootstrapPageWidthClass(authStore))

  const shouldSkipWizard = computed(() => (
    authStore.isInitialized && authStore.isAuthenticated && !authStore.onboardingEnabled
  ))

  const currentStepIndex = computed(() => bootstrapStepOrder.indexOf(selectedStep.value))

  const previousStepKey = computed(() => {
    const index = currentStepIndex.value
    if (index <= 1) return null
    return bootstrapStepOrder[index - 1]
  })
  const configActions = createBootstrapConfigActions({
    downloaderConfigRef,
    indexerConfigRef,
    mediaServerConfigRef,
    templateConfigRef,
    directoryConfigRef,
  })
  const {
    validateDownloaderStep,
    validateIndexerStep,
    validateMediaServerStep,
    validateTemplateStep,
    getTemplateIncompleteReason,
    validateDirectoryStep,
    getDirectoryIncompleteReason,
  } = createBootstrapValidators({ config, notification, testServiceConnection, testDirectoryAccess })

  async function refreshAll() {
    await refreshBootstrapState({
      loading,
      bootstrapError,
      getBootstrapStatus,
      redirecting,
      router,
      nextPath,
      authStore,
      fetchConfig,
      syncSelectedStep: () => syncBootstrapSelectedStep(authStore, selectedStep),
    })
  }

  async function handleBootstrap() {
    await submitBootstrapPassword({
      password,
      passwordConfirm,
      notification,
      working,
      bootstrap,
      redirecting,
      authStore,
      router,
      nextPath,
      fetchConfig,
      syncSelectedStep: () => syncBootstrapSelectedStep(authStore, selectedStep),
    })
  }

  const goLogin = () => router.replace({ path: '/login', query: { next: nextPath.value } })

  async function saveTMDB() {
    tmdbSaving.value = true
    try { await saveTMDBConfig(config.themoviedb) } finally { tmdbSaving.value = false }
  }

  function goPrevious() {
    if (previousStepKey.value) selectedStep.value = previousStepKey.value
  }

  async function advanceStep() {
    working.value = true
    try {
      const currentStep = selectedStep.value

      if (currentStep === 'tmdb') {
        await saveTMDB()
      }

      if (currentStep === 'downloader') {
        const ok = await validateDownloaderStep()
        if (!ok) return
      }

      if (currentStep === 'indexer') {
        const ok = await validateIndexerStep()
        if (!ok) return
      }

      if (currentStep === 'template') {
        const ok = await validateTemplateStep()
        if (!ok) return
      }

      if (currentStep === 'media_server') {
        const ok = await validateMediaServerStep()
        if (!ok) return
      }

      if (currentStep === 'directory') {
        const ok = await validateDirectoryStep()
        if (!ok) return
      }

      await fetchConfig()
      const state = await authStore.refreshBootstrapState({ force: true })
      if (state.completed) {
        selectedStep.value = 'complete'
        notification.success(t('bootstrap.completeTitle'))
        return
      }

      if (isBootstrapStepReady(currentStep, state)) {
        selectedStep.value = getBootstrapNextStepKey(currentStep)
        return
      }

      if (currentStep === 'template') {
        notification.warn(getTemplateIncompleteReason() || t('bootstrap.templateIncomplete'), t('bootstrap.notComplete'))
        return
      }

      if (currentStep === 'directory') {
        notification.warn(getDirectoryIncompleteReason() || t('bootstrap.directoryIncomplete'), t('bootstrap.notComplete'))
        return
      }

      const stepLabel = bootstrapStepLabels[currentStep] ? t(bootstrapStepLabels[currentStep]) : t('bootstrap.currentStep')
      notification.warn(t('bootstrap.currentStepRequired', { step: stepLabel }), t('bootstrap.notComplete'))
    } finally {
      working.value = false
    }
  }

  const enterApp = () => router.replace(nextPath.value)

  const reportRefreshError = () => notification.error(t('bootstrap.statusRefreshFailed')), retryRefresh = () => refreshAll().catch(reportRefreshError)
  onMounted(() => refreshAll().catch(reportRefreshError))

  return {
    authStore,
    config,
    loading,
    working,
    tmdbSaving,
    password,
    passwordConfirm,
    selectedStep,
    bootstrapError,
    redirecting,
    downloaderConfigRef,
    indexerConfigRef,
    mediaServerConfigRef,
    templateConfigRef,
    directoryConfigRef,
    pageTitle,
    pageDescription,
    pageWidthClass,
    shouldSkipWizard,
    previousStepKey,
    handleBootstrap,
    goLogin,
    ...configActions,
    goPrevious,
    advanceStep,
    enterApp,
    retryRefresh,
    fetchConfig,
  }
}
