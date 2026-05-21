import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const DiscoverPage = () => import('../components/DiscoverPage.vue')
const MediaDetail = () => import('../components/MediaDetail.vue')
const CalendarPage = () => import('../components/CalendarPage.vue')
const MediaManagementPage = () => import('../components/MediaManagementPage.vue')
const EventLogsPage = () => import('../components/EventLogsPage.vue')
const SchedulerJobsPage = () => import('../components/SchedulerJobsPage.vue')
const ConfigPage = () => import('../components/ConfigPage.vue')
const LoginPage = () => import('../components/LoginPage.vue')
const BootstrapPage = () => import('../components/BootstrapPage.vue')

const routes = [
  {
    path: '/',
    name: 'RootPage',
    beforeEnter: () => {
      const authStore = useAuthStore()

      return authStore.isAuthenticated
        ? { path: '/discover' }
        : { path: '/login', query: { next: '/discover' } }
    }
  },
  {
    path: '/setup',
    name: 'BootstrapPage',
    component: BootstrapPage,
    meta: { titleKey: 'route.setup' }
  },
  {
    path: '/login',
    name: 'LoginPage',
    component: LoginPage,
    meta: { titleKey: 'route.login' }
  },
  {
    path: '/detail',
    redirect: (to) => {
      const mediaId = to.query.media_id || to.query.id
      if (!mediaId) return '/discover'
      const query = { ...to.query }
      delete query.media_id
      delete query.id
      return {
        path: `/media/${mediaId}`,
        query
      }
    }
  },
  {
    path: '/media/:mediaId',
    name: 'MediaDetail',
    component: MediaDetail,
    meta: { titleKey: 'route.detail' }
  },
  {
    path: '/media-source',
    name: 'MediaSourceDetail',
    component: MediaDetail,
    meta: { titleKey: 'route.detail' }
  },
  {
    path: '/media',
    redirect: '/discover'
  },
  {
    path: '/discover',
    name: 'DiscoverPage',
    component: DiscoverPage,
    meta: {
      titleKey: 'route.discover'
    }
  },
  {
    path: '/calendar',
    name: 'CalendarPage',
    component: CalendarPage,
    meta: {
      titleKey: 'route.calendar'
    }
  },
  {
    path: '/resources/manage',
    redirect: '/media-management'
  },
  {
    path: '/resources',
    redirect: '/media-management'
  },
  {
    path: '/media-management',
    name: 'MediaManagementPage',
    component: MediaManagementPage,
    meta: {
      titleKey: 'route.mediaManagement'
    }
  },
  {
    path: '/event-logs',
    name: 'EventLogsPage',
    component: EventLogsPage,
    meta: {
      titleKey: 'route.eventLogs'
    }
  },
  {
    path: '/scheduler-jobs',
    name: 'SchedulerJobsPage',
    component: SchedulerJobsPage,
    meta: {
      titleKey: 'route.schedulerJobs'
    }
  },
  {
    path: '/config',
    redirect: '/settings'
  },
  {
    path: '/settings',
    name: 'ConfigPage',
    component: ConfigPage,
    meta: {
      titleKey: 'route.settings'
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.path === '/login') {
    if (!authStore.isAuthenticated) return true
    const rawNext = typeof to.query.next === 'string' && to.query.next.startsWith('/')
      ? to.query.next
      : '/discover'
    return { path: rawNext }
  }

  return true
})

export default router
