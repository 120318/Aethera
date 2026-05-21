import { defineStore } from 'pinia'
import { ref } from 'vue'
import router from '@/router'

const AUTH_HINT_KEY = 'auth.logged_in'
const AUTH_USERNAME_KEY = 'auth.username'

export const useAuthStore = defineStore('auth', () => {
  const isAuthRequired = ref(false)
  const bootstrapChecked = ref(false)
  const isInitialized = ref(true)
  const onboardingEnabled = ref(false)
  const isSetupComplete = ref(false)
  const currentStep = ref('complete')
  const bootstrapState = ref({
    password_ready: true,
    tmdb_ready: false,
    downloaders_ready: false,
    indexers_ready: false,
    directories_ready: false,
    templates_ready: false,
    completed: false,
    current_step: 'password',
    onboarding_enabled: false,
  })
  const isAuthenticated = ref(localStorage.getItem(AUTH_HINT_KEY) === 'true')
  const username = ref(localStorage.getItem(AUTH_USERNAME_KEY) || null)
  let bootstrapRequest = null

  const setAuthenticated = (value, nextUsername = null) => {
    isAuthenticated.value = value
    username.value = value ? (nextUsername || 'admin') : null

    if (value) {
      localStorage.setItem(AUTH_HINT_KEY, 'true')
      localStorage.setItem(AUTH_USERNAME_KEY, username.value || 'admin')
      return
    }

    localStorage.removeItem(AUTH_HINT_KEY)
    localStorage.removeItem(AUTH_USERNAME_KEY)
  }

  const applyBootstrapState = (state = {}) => {
    bootstrapChecked.value = true
    isInitialized.value = !!state.password_ready
    onboardingEnabled.value = !!state.onboarding_enabled
    isSetupComplete.value = !!state.completed
    currentStep.value = state.current_step || (state.completed ? 'complete' : 'password')
    bootstrapState.value = {
      password_ready: !!state.password_ready,
      tmdb_ready: !!state.tmdb_ready,
      downloaders_ready: !!state.downloaders_ready,
      indexers_ready: !!state.indexers_ready,
      directories_ready: !!state.directories_ready,
      templates_ready: !!state.templates_ready,
      completed: !!state.completed,
      current_step: currentStep.value,
      onboarding_enabled: onboardingEnabled.value,
    }

    if (state.logged_in) {
      setAuthenticated(true, state.username || 'admin')
      return
    }

    setAuthenticated(false)
  }

  const refreshBootstrapState = async ({ force = false } = {}) => {
    if (bootstrapChecked.value && !force) {
      return {
        initialized: isInitialized.value,
        onboarding_enabled: onboardingEnabled.value,
        completed: isSetupComplete.value,
        current_step: currentStep.value,
        logged_in: isAuthenticated.value,
        username: username.value,
      }
    }

    if (bootstrapRequest && !force) {
      return bootstrapRequest
    }

    bootstrapRequest = (async () => {
      const response = await window.fetch('/api/v1/auth/bootstrap-status', {
        credentials: 'include',
        headers: {
          Accept: 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`bootstrap status request failed: ${response.status}`)
      }

      const payload = await response.json()
      const data = payload && typeof payload === 'object' && 'data' in payload ? payload.data : payload
      applyBootstrapState(data || {})
      return data || {}
    })()

    try {
      return await bootstrapRequest
    } finally {
      bootstrapRequest = null
    }
  }

  const requireSetup = ({ preserveAuth = false } = {}) => {
    isAuthRequired.value = false
    bootstrapChecked.value = true
    isSetupComplete.value = false
    if (!preserveAuth || !isInitialized.value) {
      setAuthenticated(false)
    }
    const current = router.currentRoute.value
    if (current?.path === '/setup') return
    const next = current?.fullPath || '/discover'
    router.replace({ path: '/setup', query: { next } })
  }

  const requireAuth = () => {
    isAuthRequired.value = true
    setAuthenticated(false)
    if (!isInitialized.value) {
      requireSetup()
      return
    }
    const current = router.currentRoute.value
    if (current?.path === '/login') return
    const next = current?.fullPath || '/discover'
    router.replace({ path: '/login', query: { next } })
  }

  const clearAuthRequired = () => {
    isAuthRequired.value = false
  }

  return {
    isAuthRequired,
    bootstrapChecked,
    isInitialized,
    onboardingEnabled,
    isSetupComplete,
    currentStep,
    bootstrapState,
    isAuthenticated,
    username,
    setAuthenticated,
    applyBootstrapState,
    refreshBootstrapState,
    requireSetup,
    requireAuth,
    clearAuthRequired
  }
})
