/**
 * Theme toggle composable.
 *
 * Persists to localStorage for instant load, syncs to API for cross-device.
 */

import { ref, watchEffect } from 'vue'
import { useApi } from '@/composables/useApi'
import type { UserPreferences } from '@/types/api'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'pq-theme'

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  if (typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

const theme = ref<Theme>(getInitialTheme())
let synced = false

watchEffect(() => {
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem(STORAGE_KEY, theme.value)
})

export function useTheme() {
  function toggle() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    const api = useApi()
    api.put<UserPreferences>('/preferences', { theme: theme.value }).catch(() => {})
  }

  async function syncFromServer() {
    if (synced) return
    synced = true
    try {
      const api = useApi()
      const prefs = await api.get<UserPreferences>('/preferences')
      if (prefs.theme === 'light' || prefs.theme === 'dark') {
        theme.value = prefs.theme
      }
    } catch {
      // Offline or not logged in — keep localStorage value
    }
  }

  return {
    theme,
    toggle,
    syncFromServer,
  }
}
