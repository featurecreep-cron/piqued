import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'

// ── Mock useApi BEFORE importing the SUT ────────────────────────
// Captures every call so tests can assert on the request payload.
type MockCall = { method: string; path: string; body?: unknown }
const calls: MockCall[] = []
const responses: Record<string, unknown> = {}

vi.mock('@/composables/useApi', () => {
  class ApiError extends Error {
    detail: string
    constructor(detail: string) {
      super(detail)
      this.detail = detail
    }
  }
  return {
    ApiError,
    useApi: () => ({
      get: async (path: string) => {
        calls.push({ method: 'GET', path })
        return responses[`GET ${path}`] ?? {}
      },
      put: async (path: string, body: unknown) => {
        calls.push({ method: 'PUT', path, body })
        return responses[`PUT ${path}`] ?? {}
      },
      post: async (path: string, body?: unknown) => {
        calls.push({ method: 'POST', path, body })
        return responses[`POST ${path}`] ?? {}
      },
      delete: async (path: string) => {
        calls.push({ method: 'DELETE', path })
        return responses[`DELETE ${path}`] ?? {}
      },
    }),
  }
})

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAdmin: true,
    username: 'admin',
  }),
}))

import SettingsView from '@/views/SettingsView.vue'

const BALANCED_SETTINGS = {
  auth_methods: 'oidc,local',
  session_secret_key: '••••••••',
  trusted_proxy_ip: '',
  oidc_client_id: 'piqued',
  oidc_client_secret: '••••••••',
  oidc_server_metadata_url: 'https://auth.example.com/.well-known/openid-configuration',
  oidc_admin_group: 'piqued-admin',
  llm_provider: 'gemini',
  llm_model: 'gemini-2.5-flash',
  llm_api_key: '••••••••',
  llm_base_url: '',
  llm_classify_provider: '',
  llm_classify_model: '',
  llm_classify_api_key: '',
  llm_classify_base_url: '',
  llm_scoring_provider: '',
  llm_scoring_model: '',
  llm_scoring_api_key: '',
  llm_scoring_base_url: '',
  freshrss_base_url: 'https://freshrss.example.com',
  freshrss_username: 'chris',
  freshrss_api_pass: '••••••••',
  feed_poll_interval_minutes: '15',
  max_concurrent_articles: '3',
  max_article_words: '15000',
  daily_token_budget: '500000',
  max_retries: '3',
  backlog_order: 'newest_first',
  max_articles_per_cycle: '25',
  confidence_threshold: '0.4',
  surprise_surface_pct: '0.10',
  scoring_mode: 'hybrid',
  profile_synthesis_threshold: '3',
  profile_max_words: '500',
  scoring_batch_size: '50',
  interest_decay_rate: '0.05',
  interest_decay_after_days: '14',
  rss_feed_api_key: '',
}

function seedResponses(settings: Record<string, string>) {
  responses['GET /profile'] = { profile_text: '', profile_version: 0, pending_feedback_count: 0 }
  responses['GET /keys'] = { keys: [] }
  responses['GET /users'] = { users: [] }
  responses['GET /settings'] = { settings, is_admin: true }
}

async function mountSettings(initialSettings = BALANCED_SETTINGS) {
  calls.length = 0
  for (const k of Object.keys(responses)) delete responses[k]
  seedResponses({ ...initialSettings })
  setActivePinia(createPinia())
  const wrapper = mount(SettingsView, {
    global: {
      stubs: { LoadingSpinner: true },
    },
  })
  // Wait for onMounted Promise.all to settle and DOM to update
  await flushPromises()
  await nextTick()
  // Switch to config tab
  await wrapper.find('button.tab:nth-child(3)').trigger('click')
  await nextTick()
  return wrapper
}

describe('SettingsView — config tab', () => {
  beforeEach(() => {
    calls.length = 0
  })

  describe('throughput preset detection', () => {
    it('detects Balanced preset from default values', async () => {
      const wrapper = await mountSettings()
      const activeCard = wrapper.find('.preset-card--active')
      expect(activeCard.exists()).toBe(true)
      expect(activeCard.text()).toContain('Balanced')
    })

    it('detects Conservative preset', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        max_articles_per_cycle: '5',
        feed_poll_interval_minutes: '30',
        max_concurrent_articles: '2',
        daily_token_budget: '200000',
      })
      expect(wrapper.find('.preset-card--active').text()).toContain('Conservative')
    })

    it('detects Aggressive preset', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        max_articles_per_cycle: '100',
        feed_poll_interval_minutes: '10',
        max_concurrent_articles: '6',
        daily_token_budget: '2000000',
      })
      expect(wrapper.find('.preset-card--active').text()).toContain('Aggressive')
    })

    it('falls back to Custom when values do not match any preset', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        max_articles_per_cycle: '42',
      })
      expect(wrapper.find('.preset-card--active').text()).toContain('Custom')
    })
  })

  describe('preset application', () => {
    it('clicking Aggressive sets all four throughput fields', async () => {
      const wrapper = await mountSettings()
      const cards = wrapper.findAll('.preset-card')
      const aggressive = cards.find((c) => c.text().includes('Aggressive'))
      expect(aggressive).toBeTruthy()
      await aggressive!.trigger('click')
      await nextTick()
      // After click, the active card should now be Aggressive
      expect(wrapper.find('.preset-card--active').text()).toContain('Aggressive')
    })

    it('clicking Custom card is a no-op (it is informational)', async () => {
      const wrapper = await mountSettings()
      const cards = wrapper.findAll('.preset-card')
      const custom = cards.find((c) => c.text().includes('Custom'))
      await custom!.trigger('click')
      await nextTick()
      // Active should still be Balanced
      expect(wrapper.find('.preset-card--active').text()).toContain('Balanced')
    })
  })

  describe('auth method checkboxes', () => {
    it('renders one checkbox per method, checked from comma-separated state', async () => {
      const wrapper = await mountSettings()
      const checkboxes = wrapper.findAll('.checkbox-row input[type="checkbox"]')
      expect(checkboxes.length).toBe(3)
      // BALANCED_SETTINGS has 'oidc,local' enabled — 'header' off
      const checked = checkboxes.map((c) => (c.element as HTMLInputElement).checked)
      expect(checked).toEqual([true, true, false])
    })

    it('toggling header on updates auth_methods to include header', async () => {
      const wrapper = await mountSettings()
      const headerBox = wrapper.findAll('.checkbox-row input[type="checkbox"]')[2]
      await headerBox.setValue(true)
      await nextTick()

      // Save and inspect the PUT body
      await wrapper.find('button.btn--primary').trigger('click')
      await flushPromises()
      const putCall = calls.find((c) => c.method === 'PUT' && c.path === '/settings')
      expect(putCall).toBeTruthy()
      const body = putCall!.body as Record<string, string>
      expect(body.auth_methods.split(',').sort()).toEqual(['header', 'local', 'oidc'])
    })

    it('toggling oidc off removes it from auth_methods', async () => {
      const wrapper = await mountSettings()
      const oidcBox = wrapper.findAll('.checkbox-row input[type="checkbox"]')[0]
      await oidcBox.setValue(false)
      await nextTick()

      await wrapper.find('button.btn--primary').trigger('click')
      await flushPromises()
      const putCall = calls.find((c) => c.method === 'PUT' && c.path === '/settings')
      const body = putCall!.body as Record<string, string>
      expect(body.auth_methods).toBe('local')
    })
  })

  describe('conditional visibility', () => {
    it('hides OIDC section when oidc is not in auth_methods', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        auth_methods: 'local',
      })
      const titles = wrapper.findAll('.config-group-title').map((t) => t.text())
      expect(titles).not.toContain('OIDC (single sign-on)')
    })

    it('shows OIDC section when oidc IS in auth_methods', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        auth_methods: 'oidc',
      })
      const titles = wrapper.findAll('.config-group-title').map((t) => t.text())
      expect(titles).toContain('OIDC (single sign-on)')
    })

    it('hides trusted_proxy_ip field when header method is not enabled', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        auth_methods: 'local',
      })
      expect(wrapper.find('#config-trusted_proxy_ip').exists()).toBe(false)
    })

    it('shows trusted_proxy_ip field when header method IS enabled', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        auth_methods: 'header',
      })
      expect(wrapper.find('#config-trusted_proxy_ip').exists()).toBe(true)
    })

    it('hides advanced sections by default and reveals on toggle', async () => {
      const wrapper = await mountSettings()
      let titles = wrapper.findAll('.config-group-title').map((t) => t.text())
      expect(titles).not.toContain('Interest decay')
      expect(titles).not.toContain('Processing — advanced')

      // Click "Show advanced settings"
      const advancedBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Show advanced'))
      await advancedBtn!.trigger('click')
      await nextTick()

      titles = wrapper.findAll('.config-group-title').map((t) => t.text())
      expect(titles).toContain('Interest decay')
      expect(titles).toContain('Processing — advanced')
    })
  })

  describe('password reveal toggle', () => {
    it('starts as type=password, switches to type=text on toggle', async () => {
      const wrapper = await mountSettings()
      const llmKey = wrapper.find('#config-llm_api_key')
      expect(llmKey.exists()).toBe(true)
      expect(llmKey.attributes('type')).toBe('password')

      // Find the Show button next to it (inside the same .password-row)
      const passwordRow = llmKey.element.parentElement!
      const showBtn = passwordRow.querySelector('button.password-toggle') as HTMLButtonElement
      expect(showBtn.textContent?.trim()).toBe('Show')
      showBtn.click()
      await nextTick()

      expect(wrapper.find('#config-llm_api_key').attributes('type')).toBe('text')
      const newBtn = wrapper.find('#config-llm_api_key').element.parentElement!.querySelector(
        'button.password-toggle',
      ) as HTMLButtonElement
      expect(newBtn.textContent?.trim()).toBe('Hide')
    })
  })

  describe('status panel', () => {
    it('marks all four checks OK when fully configured', async () => {
      const wrapper = await mountSettings()
      const items = wrapper.findAll('.status-item')
      expect(items.length).toBe(4)
      for (const item of items) {
        expect(item.classes()).toContain('status-item--ok')
      }
    })

    it('marks Primary LLM as missing when api_key is empty', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        llm_api_key: '',
      })
      const llmItem = wrapper
        .findAll('.status-item')
        .find((i) => i.text().includes('Primary LLM'))
      expect(llmItem!.classes()).toContain('status-item--missing')
    })

    it('marks FreshRSS as missing when api_pass is empty', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        freshrss_api_pass: '',
      })
      const item = wrapper
        .findAll('.status-item')
        .find((i) => i.text().includes('FreshRSS'))
      expect(item!.classes()).toContain('status-item--missing')
    })

    it('marks Authentication as missing when no methods enabled', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        auth_methods: '',
      })
      const item = wrapper
        .findAll('.status-item')
        .find((i) => i.text().includes('Authentication'))
      expect(item!.classes()).toContain('status-item--missing')
    })

    it('marks Authentication missing when OIDC enabled but client_id empty', async () => {
      const wrapper = await mountSettings({
        ...BALANCED_SETTINGS,
        auth_methods: 'oidc',
        oidc_client_id: '',
      })
      const item = wrapper
        .findAll('.status-item')
        .find((i) => i.text().includes('Authentication'))
      expect(item!.classes()).toContain('status-item--missing')
    })
  })

  describe('test connection buttons', () => {
    it('Test LLM button posts to /settings/test-llm and shows ok result', async () => {
      const wrapper = await mountSettings()
      responses['POST /settings/test-llm'] = {
        ok: true,
        detail: 'gemini/gemini-2.5-flash responded: ok',
      }

      const btn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Test LLM connection'))
      await btn!.trigger('click')
      await flushPromises()

      const call = calls.find((c) => c.path === '/settings/test-llm')
      expect(call).toBeTruthy()
      expect(call!.method).toBe('POST')
      const body = call!.body as Record<string, string>
      expect(body.provider).toBe('gemini')
      expect(body.model).toBe('gemini-2.5-flash')
      // Masked api_key must NOT be sent — only saved value lives server-side
      expect(body.api_key).toBeUndefined()

      const result = wrapper.find('.test-result--ok')
      expect(result.exists()).toBe(true)
      expect(result.text()).toContain('gemini/gemini-2.5-flash')
    })

    it('Test LLM button surfaces failure result', async () => {
      const wrapper = await mountSettings()
      responses['POST /settings/test-llm'] = {
        ok: false,
        detail: 'RuntimeError: invalid api key',
      }

      const btn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Test LLM connection'))
      await btn!.trigger('click')
      await flushPromises()

      const result = wrapper.find('.test-result--fail')
      expect(result.exists()).toBe(true)
      expect(result.text()).toContain('invalid api key')
    })

    it('Test FreshRSS button posts to /settings/test-freshrss', async () => {
      const wrapper = await mountSettings()
      responses['POST /settings/test-freshrss'] = {
        ok: true,
        detail: 'Authenticated. 12 subscriptions visible.',
      }

      const btn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Test FreshRSS connection'))
      await btn!.trigger('click')
      await flushPromises()

      const call = calls.find((c) => c.path === '/settings/test-freshrss')
      expect(call).toBeTruthy()
      const body = call!.body as Record<string, string>
      expect(body.freshrss_base_url).toBe('https://freshrss.example.com')
      expect(body.freshrss_username).toBe('chris')
      // Masked password must NOT be transmitted
      expect(body.freshrss_api_pass).toBeUndefined()

      expect(wrapper.find('.test-result--ok').text()).toContain('12 subscriptions')
    })

    it('Test LLM forwards a freshly typed api_key (not the masked placeholder)', async () => {
      const wrapper = await mountSettings()
      responses['POST /settings/test-llm'] = { ok: true, detail: 'ok' }

      // User types a new key into the field
      const input = wrapper.find('#config-llm_api_key')
      await input.setValue('sk-newly-typed-key')

      const btn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Test LLM connection'))
      await btn!.trigger('click')
      await flushPromises()

      const call = calls.find((c) => c.path === '/settings/test-llm')
      const body = call!.body as Record<string, string>
      expect(body.api_key).toBe('sk-newly-typed-key')
    })
  })
})
