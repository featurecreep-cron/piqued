import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { useLayout } from '@/composables/useLayout'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'triage',
      component: () => import('@/views/TriageView.vue'),
      meta: { title: 'Triage' },
    },
    {
      path: '/feeds',
      name: 'feeds',
      component: () => import('@/views/FeedsView.vue'),
      meta: { title: 'Feeds' },
    },
    {
      path: '/feed/:id',
      name: 'feed',
      component: () => import('@/views/FeedView.vue'),
      meta: { title: 'Feed' },
    },
    {
      path: '/article/:id',
      name: 'article',
      component: () => import('@/views/ArticleView.vue'),
      meta: { title: 'Article' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: 'Settings' },
    },
    {
      path: '/log',
      name: 'log',
      component: () => import('@/views/LogView.vue'),
      meta: { title: 'Log' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { title: 'Not Found' },
    },
  ],
})

router.beforeEach(async () => {
  const auth = useAuthStore()
  try {
    const ok = await auth.checkSession()
    if (!ok) {
      auth.redirectToLogin()
      return false
    }
    // Sync preferences from server (no-op after first call)
    const { syncFromServer: syncTheme } = useTheme()
    const { syncFromServer: syncLayout } = useLayout()
    syncTheme()
    syncLayout()
  } catch {
    // Network error or server down
    if (auth.isAuthenticated) {
      // Already authenticated from a prior check — let navigation proceed.
      // View-level error handling will show inline errors if API calls fail.
      return
    }
    // First load, never authenticated — redirect to login as safe default
    auth.redirectToLogin()
    return false
  }
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} — Piqued` : 'Piqued'
})

export default router
