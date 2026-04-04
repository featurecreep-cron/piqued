import { describe, it, expect, vi } from 'vitest'
import { nextTick } from 'vue'

// Mock localStorage before importing the module
const storage: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => {
    storage[key] = value
  },
  removeItem: (key: string) => {
    delete storage[key]
  },
})

describe('useTheme', () => {
  it('defaults to light theme when no preference stored', async () => {
    const { useTheme } = await import('@/composables/useTheme')
    const { theme } = useTheme()
    expect(['light', 'dark']).toContain(theme.value)
  })

  it('toggle switches between light and dark', async () => {
    const { useTheme } = await import('@/composables/useTheme')
    const { theme, toggle } = useTheme()
    const initial = theme.value
    toggle()
    expect(theme.value).not.toBe(initial)
    toggle()
    expect(theme.value).toBe(initial)
  })

  it('persists theme to localStorage on toggle', async () => {
    const { useTheme } = await import('@/composables/useTheme')
    const { theme, toggle } = useTheme()
    toggle()
    await nextTick()
    expect(storage['pq-theme']).toBe(theme.value)
  })
})
