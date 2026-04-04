import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useContentStore } from '@/stores/content'
import type { SectionItem } from '@/types/api'

function makeSectionList(overrides: Partial<{ threshold: number }> = {}) {
  const sections: SectionItem[] = [
    {
      id: 1,
      article_id: 10,
      article_title: 'Linux 6.12',
      feed_title: 'LWN',
      heading: 'Container Security',
      summary: 'New container features',
      topic_tags: ['linux', 'containers'],
      score: 0.85,
      reasoning: 'High relevance',
      is_surprise: false,
      has_humor: false,
      has_surprise_data: false,
      has_actionable_advice: true,
      article_url: 'https://lwn.net/1',
      published_at: '2026-04-03T00:00:00Z',
    },
    {
      id: 2,
      article_id: 11,
      article_title: 'Rust Weekly',
      feed_title: 'TWIR',
      heading: 'Cargo Workspaces',
      summary: 'Workspace improvements',
      topic_tags: ['rust'],
      score: 0.45,
      reasoning: null,
      is_surprise: false,
      has_humor: false,
      has_surprise_data: false,
      has_actionable_advice: false,
      article_url: null,
      published_at: null,
    },
    {
      id: 3,
      article_id: 12,
      article_title: 'Surprise Article',
      feed_title: 'HN',
      heading: 'Unexpected Discovery',
      summary: 'Surprising content',
      topic_tags: ['ai'],
      score: 0.3,
      reasoning: 'Surprise recommendation',
      is_surprise: true,
      has_humor: true,
      has_surprise_data: true,
      has_actionable_advice: false,
      article_url: 'https://hn.com/3',
      published_at: '2026-04-03T00:00:00Z',
    },
  ]

  return {
    sections,
    date: '2026-04-03',
    dates_available: ['2026-04-03', '2026-04-02', '2026-04-01'],
    threshold: overrides.threshold ?? 0.7,
    surprise_section_ids: [3],
  }
}

describe('content store', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    setActivePinia(createPinia())
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  function mockFetch(body: unknown) {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.resolve(body),
    })
  }

  it('loadSections populates state', async () => {
    const data = makeSectionList()
    mockFetch(data)

    const store = useContentStore()
    await store.loadSections()

    expect(store.sections).toHaveLength(3)
    expect(store.date).toBe('2026-04-03')
    expect(store.threshold).toBe(0.7)
    expect(store.datesAvailable).toHaveLength(3)
  })

  it('computes above/below/surprise tiers', async () => {
    const data = makeSectionList()
    mockFetch(data)

    const store = useContentStore()
    await store.loadSections()

    expect(store.aboveSections).toHaveLength(1)
    expect(store.aboveSections[0].id).toBe(1)

    expect(store.belowSections).toHaveLength(1)
    expect(store.belowSections[0].id).toBe(2)

    expect(store.surpriseSections).toHaveLength(1)
    expect(store.surpriseSections[0].id).toBe(3)
  })

  it('focus navigation works', async () => {
    const data = makeSectionList()
    mockFetch(data)

    const store = useContentStore()
    await store.loadSections()

    expect(store.focusedIndex).toBe(0)
    expect(store.focusedSection?.id).toBe(1)

    store.focusNext()
    expect(store.focusedIndex).toBe(1)

    store.focusNext()
    expect(store.focusedIndex).toBe(2)

    // Can't go past end
    store.focusNext()
    expect(store.focusedIndex).toBe(2)

    store.focusPrev()
    expect(store.focusedIndex).toBe(1)

    // Can't go below 0
    store.focusPrev()
    store.focusPrev()
    expect(store.focusedIndex).toBe(0)
  })

  it('sets error on API failure', async () => {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: 'Server error' }),
    })

    const store = useContentStore()
    await store.loadSections()

    expect(store.error).toBe('Server error')
    expect(store.sections).toHaveLength(0)
  })

  it('$reset clears state', async () => {
    const data = makeSectionList()
    mockFetch(data)

    const store = useContentStore()
    await store.loadSections()
    store.$reset()

    expect(store.sections).toHaveLength(0)
    expect(store.date).toBe('')
    expect(store.focusedIndex).toBe(0)
  })
})
