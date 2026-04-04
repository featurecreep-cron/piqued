import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
  } catch {
    // Network error — let the page load, it'll show an error state
  }
})

export default router
