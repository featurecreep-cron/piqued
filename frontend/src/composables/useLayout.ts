/**
 * Layout mode composable.
 *
 * Manages which triage layout is active (river, reader, columns).
 * Mode persists to localStorage. The `v` key cycles modes.
 */

import { ref, computed } from 'vue'

export type LayoutMode = 'river' | 'reader' | 'columns'

const STORAGE_KEY = 'pq-layout'
const MODES: LayoutMode[] = ['river', 'reader', 'columns']

function getInitialMode(): LayoutMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && MODES.includes(stored as LayoutMode)) return stored as LayoutMode
  return 'river'
}

const mode = ref<LayoutMode>(getInitialMode())

export function useLayout() {
  function setMode(m: LayoutMode) {
    mode.value = m
    localStorage.setItem(STORAGE_KEY, m)
  }

  function cycle() {
    const idx = MODES.indexOf(mode.value)
    const next = MODES[(idx + 1) % MODES.length]
    setMode(next)
  }

  const isRiver = computed(() => mode.value === 'river')
  const isReader = computed(() => mode.value === 'reader')
  const isColumns = computed(() => mode.value === 'columns')

  return {
    mode,
    setMode,
    cycle,
    isRiver,
    isReader,
    isColumns,
  }
}
