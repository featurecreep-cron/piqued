/**
 * Layout mode composable.
 *
 * Manages which triage layout is active (river, reader, columns).
 * Persists to localStorage for instant load, syncs to API for cross-device.
 */

import { ref, computed } from 'vue'
import { useApi } from '@/composables/useApi'
import type { UserPreferences } from '@/types/api'

export type LayoutMode = 'river' | 'reader' | 'columns'

const STORAGE_KEY = 'pq-layout'
const MODES: LayoutMode[] = ['river', 'reader', 'columns']

function getInitialMode(): LayoutMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && MODES.includes(stored as LayoutMode)) return stored as LayoutMode
  return 'river'
}

const mode = ref<LayoutMode>(getInitialMode())
let synced = false

export function useLayout() {
  function setMode(m: LayoutMode) {
    mode.value = m
    localStorage.setItem(STORAGE_KEY, m)
    const api = useApi()
    api.put<UserPreferences>('/preferences', { layout_mode: m }).catch(() => {})
  }

  function cycle() {
    const idx = MODES.indexOf(mode.value)
    const next = MODES[(idx + 1) % MODES.length]
    setMode(next)
  }

  async function syncFromServer() {
    if (synced) return
    synced = true
    try {
      const api = useApi()
      const prefs = await api.get<UserPreferences>('/preferences')
      if (prefs.layout_mode && MODES.includes(prefs.layout_mode as LayoutMode)) {
        mode.value = prefs.layout_mode as LayoutMode
        localStorage.setItem(STORAGE_KEY, mode.value)
      }
    } catch {
      // Offline or not logged in — keep localStorage value
    }
  }

  const isRiver = computed(() => mode.value === 'river')
  const isReader = computed(() => mode.value === 'reader')
  const isColumns = computed(() => mode.value === 'columns')

  return {
    mode,
    setMode,
    cycle,
    syncFromServer,
    isRiver,
    isReader,
    isColumns,
  }
}
