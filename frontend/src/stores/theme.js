import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const preference = ref(localStorage.getItem('theme-preference') || 'auto')
  const isDark = ref(false)

  const updateSystemTheme = () => {
    const root = document.documentElement
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    isDark.value = preference.value === 'auto' ? systemDark : preference.value === 'dark'

    root.classList.add('theme-transition')
    root.removeAttribute('data-theme')
    if (isDark.value) {
      root.classList.add('dark')
      root.setAttribute('data-theme', 'dark')
    } else {
      root.classList.remove('dark')
      root.setAttribute('data-theme', 'light')
    }
    window.setTimeout(() => root.classList.remove('theme-transition'), 350)
  }

  const setPreference = (p) => {
    preference.value = p
    localStorage.setItem('theme-preference', p)
    if (p !== 'auto') {
      localStorage.setItem('theme', p)
    }
    updateSystemTheme()
  }

  const toggle = () => {
    const options = ['light', 'auto', 'dark']
    const next = options[(options.indexOf(preference.value) + 1) % options.length]
    setPreference(next)
  }

  const init = () => {
    updateSystemTheme()
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateSystemTheme)
  }

  return {
    preference,
    isDark,
    setPreference,
    toggle,
    init
  }
})
