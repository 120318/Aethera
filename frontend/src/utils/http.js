import axios from 'axios'
import { useNotificationStore } from '@/stores/notification'
import { useAuthStore } from '@/stores/auth'
import { t } from '@/i18n'
import { normalizeMessageParams } from '@/utils/localizedMessage'

const http = axios.create({
  baseURL: '/',
  timeout: 60000
})

function resolveApiMessage(data, fallbackKey = 'http.requestFailed') {
  if (data?.message_key) {
    const translated = t(data.message_key, normalizeMessageParams(data.params || {}))
    if (translated && translated !== data.message_key) {
      return translated
    }
  }
  return t(fallbackKey)
}

function buildApiError(message, code, isSystemError, originalError = null, response = null, messageKey = null, params = {}) {
  const normalizedParams = normalizeMessageParams(params || {})
  const error = new Error(message || t('http.requestFailed'))
  error.code = code
  error.isSystemError = Boolean(isSystemError)
  error.originalError = originalError || null
  error.messageKey = messageKey || null
  error.params = normalizedParams

  if (response) {
    error.response = response
    error.status = response.status
    error.data = response.data?.data || null
  } else if (originalError?.response) {
    error.response = originalError.response
    error.status = originalError.response.status
    error.data = originalError.response.data?.data || null
  }

  if (originalError?.config) {
    error.config = originalError.config
  }
  if (originalError?.request) {
    error.request = originalError.request
  }
  if (originalError?.isAxiosError) {
    error.isAxiosError = true
  }
  return error
}

http.interceptors.response.use(
  response => {
    if (response.config.url && response.config.url.startsWith('/api/')) {
      const { data } = response
      const notification = useNotificationStore()

      if (data && typeof data === 'object' && 'code' in data && 'data' in data) {
        const isSystemError = Boolean(data.is_system_error)

        if (data.code === 0 || data.code === 200) {
          return data.data
        } else {
          if (data.code === 460 || data.code === 461) {
            const authStore = useAuthStore()
            authStore.requireSetup({ preserveAuth: data.code === 461 })
            const message = resolveApiMessage(data, 'http.setupRequired')
            return Promise.reject(buildApiError(message, data.code, isSystemError, null, response, data.message_key, data.params))
          }
          if (data.code === 401) {
            const authStore = useAuthStore()
            authStore.requireAuth()
            const message = resolveApiMessage(data, 'http.notLoggedIn')
            return Promise.reject(buildApiError(message, data.code, isSystemError, null, response, data.message_key, data.params))
          }
          const message = resolveApiMessage(data)
          if (isSystemError) {
            notification.error(message)
          } else {
            notification.warn(message)
          }
          return Promise.reject(buildApiError(message, data.code, isSystemError, null, response, data.message_key, data.params))
        }
      }

      return data
    }

    return response
  },
  error => {
    let errorMessage = t('http.networkFailed')
    const notification = useNotificationStore()
    let errorCode = null
    let isSystemError = true
    let messageKey = null
    let messageParams = {}

    if (error.response) {
      const { data, status } = error.response

      if (error.config.url && error.config.url.startsWith('/api/')) {
        if (data && typeof data === 'object' && 'code' in data) {
          errorMessage = resolveApiMessage(data)
          errorCode = data.code ?? null
          messageKey = data.message_key || null
          messageParams = data.params || {}
          isSystemError = data.is_system_error !== undefined ? Boolean(data.is_system_error) : true
        } else if (data && typeof data === 'object' && 'detail' in data) {
          errorMessage = data.detail
        } else if (status === 401) {
          errorMessage = t('http.notLoggedIn')
          const authStore = useAuthStore()
          authStore.requireAuth()
        } else if (status === 403) {
          errorMessage = t('http.forbidden')
        } else if (status === 404) {
          errorMessage = t('http.notFound')
        } else if (status === 500) {
          errorMessage = t('http.serverError')
        }
      }
    } else if (error.request) {
      errorMessage = t('http.timeout')
    } else {
      errorMessage = error.message || t('http.requestFailed')
    }

    if (errorCode === 460 || errorCode === 461) {
      const authStore = useAuthStore()
      authStore.requireSetup({ preserveAuth: errorCode === 461 })
      return Promise.reject(buildApiError(errorMessage, errorCode, false, error, null, messageKey, messageParams))
    }

    if (errorCode === 401) {
      const authStore = useAuthStore()
      authStore.requireAuth()
      return Promise.reject(buildApiError(errorMessage, 401, false, error, null, messageKey, messageParams))
    }

    if (isSystemError) {
      notification.error(errorMessage)
    } else {
      notification.warn(errorMessage)
    }
    return Promise.reject(buildApiError(errorMessage, errorCode, isSystemError, error, null, messageKey, messageParams))
  }
)

export default http
export const isAxiosError = axios.isAxiosError
