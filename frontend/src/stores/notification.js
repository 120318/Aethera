import { defineStore } from 'pinia'
import { ref } from 'vue'
import { t } from '@/i18n'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref([])

  function notify(severity, summary, detail, life = 3000) {
    notifications.value.push({ severity, summary, detail, life, id: Date.now() + Math.random() })
  }

  function success(detail, summary = t('notification.success')) {
    notify('success', summary, detail)
  }

  function error(detail, summary = t('notification.error')) {
    notify('error', summary, detail)
  }

  function warn(detail, summary = t('notification.warn')) {
    notify('warn', summary, detail)
  }

  function info(detail, summary = t('notification.info')) {
    notify('info', summary, detail)
  }

  function clear() {
    notifications.value = []
  }

  function drain() {
    const queued = [...notifications.value]
    notifications.value = []
    return queued
  }

  return {
    notifications,
    notify,
    success,
    error,
    warn,
    info,
    clear,
    drain
  }
})
