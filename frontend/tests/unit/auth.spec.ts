import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('auth store', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    setActivePinia(createPinia())
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  function mockFetchResponse(status: number, body: unknown) {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? 'OK' : 'Unauthorized',
      json: () => Promise.resolve(body),
    })
  }

  it('checkSession sets user on success', async () => {
    mockFetchResponse(200, { id: 1, username: 'chris', email: null, role: 'admin' })
    const store = useAuthStore()

    const result = await store.checkSession()

    expect(result).toBe(true)
    expect(store.isAuthenticated).toBe(true)
    expect(store.username).toBe('chris')
    expect(store.isAdmin).toBe(true)
    expect(store.checked).toBe(true)
  })

  it('checkSession returns false on 401', async () => {
    mockFetchResponse(401, { detail: 'Not authenticated' })
    const store = useAuthStore()

    const result = await store.checkSession()

    expect(result).toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(store.checked).toBe(true)
  })

  it('skips fetch if already checked', async () => {
    mockFetchResponse(200, { id: 1, username: 'chris', email: null, role: 'admin' })
    const store = useAuthStore()

    await store.checkSession()
    await store.checkSession()

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('$reset clears state', async () => {
    mockFetchResponse(200, { id: 1, username: 'chris', email: null, role: 'user' })
    const store = useAuthStore()
    await store.checkSession()

    store.$reset()

    expect(store.isAuthenticated).toBe(false)
    expect(store.checked).toBe(false)
  })
})
