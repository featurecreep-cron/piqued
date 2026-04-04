import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi, ApiError } from '@/composables/useApi'
import type { UserInfo } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)
  const checked = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const username = computed(() => user.value?.username ?? '')

  const api = useApi()

  async function checkSession(): Promise<boolean> {
    if (checked.value) return isAuthenticated.value
    loading.value = true
    try {
      user.value = await api.get<UserInfo>('/me')
      checked.value = true
      return true
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        user.value = null
        checked.value = true
        return false
      }
      // Network error or server down — don't mark as checked so we retry
      throw err
    } finally {
      loading.value = false
    }
  }

  function redirectToLogin() {
    window.location.href = '/login'
  }

  function logout() {
    user.value = null
    checked.value = false
    window.location.href = '/logout'
  }

  function $reset() {
    user.value = null
    loading.value = false
    checked.value = false
  }

  return {
    user,
    loading,
    checked,
    isAuthenticated,
    isAdmin,
    username,
    checkSession,
    redirectToLogin,
    logout,
    $reset,
  }
})
