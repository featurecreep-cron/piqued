import { describe, it, expect, vi } from 'vitest'

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

describe('useLayout', () => {
  it('defaults to river mode', async () => {
    const { useLayout } = await import('@/composables/useLayout')
    const { mode } = useLayout()
    expect(mode.value).toBe('river')
  })

  it('cycle goes river -> reader -> columns -> river', async () => {
    const { useLayout } = await import('@/composables/useLayout')
    const { mode, cycle } = useLayout()

    // Start at river (from previous test, module-level ref)
    // Force to river first
    const { setMode } = useLayout()
    setMode('river')
    expect(mode.value).toBe('river')

    cycle()
    expect(mode.value).toBe('reader')

    cycle()
    expect(mode.value).toBe('columns')

    cycle()
    expect(mode.value).toBe('river')
  })

  it('persists mode to localStorage', async () => {
    const { useLayout } = await import('@/composables/useLayout')
    const { setMode } = useLayout()

    setMode('reader')
    expect(storage['pq-layout']).toBe('reader')

    setMode('river')
    expect(storage['pq-layout']).toBe('river')
  })

  it('computed helpers reflect current mode', async () => {
    const { useLayout } = await import('@/composables/useLayout')
    const { setMode, isRiver, isReader, isColumns } = useLayout()

    setMode('river')
    expect(isRiver.value).toBe(true)
    expect(isReader.value).toBe(false)

    setMode('reader')
    expect(isReader.value).toBe(true)
    expect(isRiver.value).toBe(false)

    setMode('columns')
    expect(isColumns.value).toBe(true)
  })
})
