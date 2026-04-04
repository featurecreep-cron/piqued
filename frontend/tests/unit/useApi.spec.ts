import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useApi, ApiError } from '@/composables/useApi'

describe('useApi', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  function mockFetch(status: number, body: unknown, ok?: boolean) {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: ok ?? (status >= 200 && status < 300),
      status,
      statusText: 'OK',
      json: () => Promise.resolve(body),
    })
  }

  it('GET sends request to /api/v1/ path with query params', async () => {
    mockFetch(200, { sections: [] })
    const api = useApi()

    await api.get('/sections', { date: '2026-04-03' })

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/sections'),
      expect.objectContaining({ method: 'GET', credentials: 'same-origin' }),
    )
    const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain('date=2026-04-03')
  })

  it('POST sends JSON body', async () => {
    mockFetch(200, { ok: true, direction: 'up' })
    const api = useApi()

    await api.post('/feedback', { section_id: 1, rating: 1 })

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ section_id: 1, rating: 1 })
  })

  it('throws ApiError on non-OK response', async () => {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: () => Promise.resolve({ detail: 'Article not found' }),
    })
    const api = useApi()

    await expect(api.get('/articles/999')).rejects.toThrow(ApiError)
    try {
      await api.get('/articles/999')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).status).toBe(404)
      expect((err as ApiError).detail).toBe('Article not found')
    }
  })

  it('omits undefined query params', async () => {
    mockFetch(200, {})
    const api = useApi()

    await api.get('/sections', { date: undefined, limit: 50 })

    const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).not.toContain('date')
    expect(url).toContain('limit=50')
  })

  it('DELETE sends request without body', async () => {
    mockFetch(200, { ok: true })
    const api = useApi()

    await api.delete('/keys/1')

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(init.method).toBe('DELETE')
    expect(init.body).toBeUndefined()
  })
})
