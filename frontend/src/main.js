import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useMediaImageSettingsStore } from '@/stores/media-image-settings'
import { i18n } from '@/i18n'

import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import Tooltip from 'primevue/tooltip'
import AuraCustom from '@/presets/aura-custom'
import { createPrimeVuePt } from '@/config/primevue-pt'
import 'primeicons/primeicons.css'

import './styles/tailwind.css'

const pref = localStorage.getItem('theme-preference') || 'auto'
const isDark = pref === 'auto'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : pref === 'dark'

if (isDark) {
    document.documentElement.classList.add('dark')
} else {
    document.documentElement.classList.remove('dark')
}

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(PrimeVue, {
    theme: {
        preset: AuraCustom,
        options: {
            prefix: 'p',
            darkModeSelector: '.dark',
            cssLayer: {
                name: 'primevue',
                order: 'theme, base, primevue, components, utilities'
            }
        }
    },
    pt: createPrimeVuePt()
})

app.use(ToastService)
app.use(ConfirmationService)
app.directive('tooltip', Tooltip)
app.use(i18n)
app.use(router)
useMediaImageSettingsStore(pinia).fetch()

app.mount('#app')
