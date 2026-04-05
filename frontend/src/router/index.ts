import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { useLayout } from '@/composables/useLayout'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'triage',
      component: () => import('@/views/TriageView.vue'),
    },
    {
      path: '/feeds',
      name: 'feeds',
      component: () => import('@/views/FeedsView.vue'),
    },
    {
      path: '/feed/:id',
      name: 'feed',
      component: () => import('@/views/FeedView.vue'),
    },
    {
      path: '/article/:id',
      name: 'article',
      component: () => import('@/views/ArticleView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/log',
      name: 'log',
      component: () => import('@/views/LogView.vue'),
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
    // Network error or server down — redirect to login as a safe default
    auth.redirectToLogin()
    return false
  }
})

export default router
