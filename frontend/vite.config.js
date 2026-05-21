import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

const pageChunkNames = {
  'components/DiscoverPage.vue': 'page-discover',
  'components/MediaDetail.vue': 'page-media-detail',
  'components/CalendarPage.vue': 'page-calendar',
  'components/MediaManagementPage.vue': 'page-media-management',
  'components/EventLogsPage.vue': 'page-event-logs',
  'components/SchedulerJobsPage.vue': 'page-scheduler-jobs',
  'components/ConfigPage.vue': 'page-config',
  'components/LoginPage.vue': 'page-login',
}

const appRuntimeModulePatterns = [
  '/src/api/actions.js',
  '/src/api/commands.js',
  '/src/api/config.js',
  '/src/api/mediaManagement.js',
  '/src/api/subscription.js',
  '/src/composables/mediaIdentitySupport.js',
  '/src/composables/useCommandRuntime.js',
  '/src/stores/notification.js',
  '/src/stores/operations.js',
  '/src/utils/formatters.js',
  '/src/utils/localizedMessage.js',
  '/src/utils/queryParams.js',
]

function manualChunks(id) {
  if (!id.includes('node_modules')) {
    if (appRuntimeModulePatterns.some(pattern => id.includes(pattern))) {
      return 'app-runtime'
    }
    if (
      id.includes('/src/components/media-management/DirectoryIntegrity')
      || id.includes('/src/components/media-management/directoryIntegritySupport.js')
    ) {
      return 'page-media-management-directories'
    }
    if (
      id.includes('/src/components/common/AppTabs.vue')
      || id.includes('/src/components/common/AppTag.vue')
      || id.includes('/src/components/common/ConfigDialog.vue')
    ) {
      return 'app-common'
    }
    const pageChunk = Object.entries(pageChunkNames).find(([pattern]) => id.includes(pattern))
    if (pageChunk) return pageChunk[1]
    if (id.includes('/src/components/config/')) return 'page-config'
    if (id.includes('/src/components/media-management/')) return 'page-media-management'
    return undefined
  }

  if (
    id.includes('/node_modules/vue/')
    || id.includes('/node_modules/@vue/')
    || id.includes('/node_modules/vue-i18n/')
    || id.includes('/node_modules/@intlify/')
    || id.includes('/node_modules/hookable/')
    || id.includes('/node_modules/perfect-debounce/')
  ) {
    return 'vue-core'
  }

  if (id.includes('/node_modules/vue-router/') || id.includes('/node_modules/pinia/')) {
    return 'vue-routing'
  }

  if (id.includes('/node_modules/primeicons/')) {
    return 'prime-icons'
  }

  if (id.includes('/node_modules/primevue/')) {
    return 'primevue'
  }

  if (id.includes('/node_modules/@primevue/') || id.includes('/node_modules/@primeuix/') || id.includes('/node_modules/@primevue/themes/') || id.includes('/node_modules/@primeuix/themes/')) {
    return 'primevue-theme'
  }

  if (id.includes('/node_modules/axios/')) {
    return 'http-client'
  }

  return 'vendor'
}

function firstHeaderValue(value) {
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function resolveForwardedProto(req) {
  const forwardedProto = firstHeaderValue(req.headers['x-forwarded-proto'])
  if (forwardedProto) {
    return forwardedProto.split(',')[0].trim() || 'http'
  }
  return req.socket?.encrypted ? 'https' : 'http'
}

const apiProxy = {
  target: 'http://backend:3001',
  changeOrigin: true,
  secure: false,
  configure: (proxy) => {
    proxy.on('proxyReq', (proxyReq, req) => {
      proxyReq.setHeader('X-Forwarded-Proto', resolveForwardedProto(req))
    })
  },
}

// Fix dev server port and proxy /api to backend (http://localhost:3001)
export default defineConfig({
  plugins: [
    tailwindcss(),
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks,
      }
    }
  },
  server: {
    port: 5173,
    strictPort: true, // fail if port taken (avoid auto-increment to 5174...)
    // Dev server runs behind reverse proxies in Docker setups, so do not
    // restrict by host header here.
    allowedHosts: true,
    proxy: {
      '/api': apiProxy,
    }
  },
  preview: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': apiProxy,
    },
  }
})
