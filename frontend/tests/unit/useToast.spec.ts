import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useToast } from '@/composables/useToast'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Clear any leftover toasts from previous tests
    const { toasts } = useToast()
    toasts.value.splice(0, toasts.value.length)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('adds success toast', () => {
    const toast = useToast()
    toast.success('Saved')
    expect(toast.toasts.value).toHaveLength(1)
    expect(toast.toasts.value[0].type).toBe('success')
    expect(toast.toasts.value[0].message).toBe('Saved')
  })

  it('adds error toast', () => {
    const toast = useToast()
    toast.error('Failed')
    expect(toast.toasts.value).toHaveLength(1)
    expect(toast.toasts.value[0].type).toBe('error')
  })

  it('auto-dismisses after 4 seconds', () => {
    const toast = useToast()
    toast.info('Processing...')
    expect(toast.toasts.value).toHaveLength(1)

    vi.advanceTimersByTime(4000)
    expect(toast.toasts.value).toHaveLength(0)
  })

  it('manual dismiss removes toast immediately', () => {
    const toast = useToast()
    toast.success('Done')
    const id = toast.toasts.value[0].id
    toast.dismiss(id)
    expect(toast.toasts.value).toHaveLength(0)
  })

  it('stacks multiple toasts', () => {
    const toast = useToast()
    toast.success('One')
    toast.error('Two')
    toast.info('Three')
    expect(toast.toasts.value).toHaveLength(3)
  })
})
