export async function refreshBootstrapState({
  loading,
  bootstrapError,
  getBootstrapStatus,
  redirecting,
  router,
  nextPath,
  authStore,
  fetchConfig,
  syncSelectedStep,
}) {
  loading.value = true
  bootstrapError.value = false
  try {
    const state = await getBootstrapStatus()
    if (state.password_ready && state.logged_in && !state.onboarding_enabled) {
      redirecting.value = true
      router.replace(nextPath.value)
      return
    }
    authStore.applyBootstrapState(state)
    if (authStore.isAuthenticated) {
      await fetchConfig()
    }
    if (authStore.isInitialized && authStore.isAuthenticated && !authStore.onboardingEnabled) {
      redirecting.value = true
      router.replace(nextPath.value)
      return
    }
    syncSelectedStep()
  } catch (error) {
    bootstrapError.value = true
    throw error
  } finally {
    loading.value = false
  }
}

export async function submitBootstrapPassword({
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
  syncSelectedStep,
}) {
  if (!password.value || password.value !== passwordConfirm.value) {
    notification.warn(t('settings.system.checkPasswordInput'), t('notification.info'))
    return
  }

  working.value = true
  try {
    const state = await bootstrap({ password: password.value })
    const shouldRedirectImmediately = state.password_ready && state.logged_in && !state.onboarding_enabled
    if (shouldRedirectImmediately) {
      redirecting.value = true
    }
    authStore.applyBootstrapState(state)
    authStore.clearAuthRequired()
    password.value = ''
    passwordConfirm.value = ''

    if (shouldRedirectImmediately) {
      router.replace(nextPath.value)
      return
    }

    await fetchConfig()
    syncSelectedStep()
  } finally {
    working.value = false
  }
}
import { t } from '@/i18n'
