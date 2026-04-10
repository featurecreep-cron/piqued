<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi, ApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import type {
  SettingsResponse,
  UserProfileResponse,
  UserInfo,
  UserList,
  ApiKeyItem,
  ApiKeyList,
  ApiKeyCreated,
} from '@/types/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const api = useApi()
const toast = useToast()
const auth = useAuthStore()

const activeTab = ref<'profile' | 'config' | 'keys' | 'users'>('profile')
const loading = ref(false)

// Profile state
const profileText = ref('')
const profileVersion = ref(0)
const pendingFeedback = ref(0)
const synthesizing = ref(false)
const savingProfile = ref(false)

// Config state (admin)
const settings = ref<Record<string, string>>({})
const savingConfig = ref(false)

// API keys state
const apiKeys = ref<ApiKeyItem[]>([])
const newKeyName = ref('')
const createdKey = ref<string | null>(null)
const confirmingRevoke = ref<number | null>(null)

// Users state (admin)
const users = ref<UserInfo[]>([])
const newUsername = ref('')
const newPassword = ref('')
const newRole = ref('user')
const confirmingRoleChange = ref<{ userId: number; role: string } | null>(null)

// ── Config field metadata ────────────────────────────────────────
interface ConfigField {
  key: string
  label: string
  help: string
  type?: 'text' | 'password' | 'number' | 'select' | 'model'
  options?: { value: string; label: string }[]
  providerKey?: string
  showIf?: () => boolean
}

interface ConfigSection {
  id: string
  title: string
  description?: string
  advanced?: boolean
  showIf?: () => boolean
  fields: ConfigField[]
}

// Auth method checkbox state — derived from comma-separated auth_methods
const authMethods = computed<Set<string>>(() => {
  const raw = settings.value.auth_methods || ''
  return new Set(raw.split(',').map((m) => m.trim()).filter(Boolean))
})
function setAuthMethod(method: string, enabled: boolean) {
  const current = new Set(authMethods.value)
  if (enabled) current.add(method)
  else current.delete(method)
  settings.value.auth_methods = Array.from(current).join(',')
}
function hasAuthMethod(m: string): boolean {
  return authMethods.value.has(m)
}

// Show/hide password fields
const revealedPasswords = ref<Set<string>>(new Set())
function togglePasswordReveal(key: string) {
  const next = new Set(revealedPasswords.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  revealedPasswords.value = next
}
function isPlaceholderPassword(key: string): boolean {
  return settings.value[key] === '••••••••'
}

// Provider → model suggestions
const MODEL_SUGGESTIONS: Record<string, { value: string; label: string }[]> = {
  gemini: [
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
    { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  ],
  openai: [
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'gpt-4.1-nano', label: 'GPT-4.1 Nano' },
  ],
  claude: [
    { value: 'claude-haiku-4-5-20251001', label: 'Claude 4.5 Haiku' },
    { value: 'claude-sonnet-4-6-20250514', label: 'Claude 4.6 Sonnet' },
  ],
  ollama: [],
}
function getModelSuggestions(providerKey: string): { value: string; label: string }[] {
  const provider = settings.value[providerKey] || ''
  return MODEL_SUGGESTIONS[provider] || []
}

// ── Throughput presets ──────────────────────────────────────────
interface ThroughputPreset {
  label: string
  description: string
  values: Record<string, string>
}
const THROUGHPUT_PRESETS: Record<string, ThroughputPreset> = {
  conservative: {
    label: 'Conservative',
    description: '5 articles per 30-minute cycle, 2 in parallel, 200K tokens/day. Cheap free-tier LLMs.',
    values: {
      max_articles_per_cycle: '5',
      feed_poll_interval_minutes: '30',
      max_concurrent_articles: '2',
      daily_token_budget: '200000',
    },
  },
  balanced: {
    label: 'Balanced',
    description: '25 articles every 15 minutes, 3 in parallel, 500K tokens/day. The right starting point for most users.',
    values: {
      max_articles_per_cycle: '25',
      feed_poll_interval_minutes: '15',
      max_concurrent_articles: '3',
      daily_token_budget: '500000',
    },
  },
  aggressive: {
    label: 'Aggressive',
    description: '100 articles every 10 minutes, 6 in parallel, 2M tokens/day. Drains a backlog fast — watch your bill.',
    values: {
      max_articles_per_cycle: '100',
      feed_poll_interval_minutes: '10',
      max_concurrent_articles: '6',
      daily_token_budget: '2000000',
    },
  },
}
const PRESET_KEYS = ['max_articles_per_cycle', 'feed_poll_interval_minutes', 'max_concurrent_articles', 'daily_token_budget']

const activeThroughputPreset = computed<string>(() => {
  for (const [name, preset] of Object.entries(THROUGHPUT_PRESETS)) {
    if (PRESET_KEYS.every((k) => settings.value[k] === preset.values[k])) {
      return name
    }
  }
  return 'custom'
})

function applyThroughputPreset(name: string) {
  if (name === 'custom') return
  const preset = THROUGHPUT_PRESETS[name]
  if (!preset) return
  for (const [k, v] of Object.entries(preset.values)) {
    settings.value[k] = v
  }
}

// ── Config sections (declarative) ────────────────────────────────
const CONFIG_SECTIONS: ConfigSection[] = [
  {
    id: 'auth',
    title: 'Authentication',
    description: 'How users log in. Pick one or more methods.',
    fields: [
      // auth_methods rendered as checkboxes — handled in template
      {
        key: 'session_secret_key',
        label: 'Session secret',
        help: 'Auto-generated on first boot. Change this to immediately log out every active session — useful if you suspect a leaked cookie.',
        type: 'password',
      },
      {
        key: 'trusted_proxy_ip',
        label: 'Trusted proxy IP',
        help: 'Only relevant when "Header (forward auth)" is enabled. Set this to the IP of your reverse proxy (Authentik outpost, Traefik, etc.) so piqued only trusts X-authentik-username headers from that source.',
        showIf: () => hasAuthMethod('header'),
      },
    ],
  },
  {
    id: 'oidc',
    title: 'OIDC (single sign-on)',
    description: 'OAuth2 / OpenID Connect provider config. Hidden unless OIDC is enabled above.',
    showIf: () => hasAuthMethod('oidc'),
    fields: [
      {
        key: 'oidc_client_id',
        label: 'Client ID',
        help: 'OAuth2 client ID created in your identity provider (e.g. Authentik application slug).',
      },
      {
        key: 'oidc_client_secret',
        label: 'Client secret',
        help: 'OAuth2 client secret. Stored encrypted in the DB after save and never returned to the browser as plaintext.',
        type: 'password',
      },
      {
        key: 'oidc_server_metadata_url',
        label: 'Metadata URL',
        help: 'OpenID Connect discovery URL — usually ends in /.well-known/openid-configuration. Authentik example: https://auth.example.com/application/o/piqued/.well-known/openid-configuration',
      },
      {
        key: 'oidc_admin_group',
        label: 'Admin group',
        help: 'Group claim that grants the admin role. Members of this group at your IdP are auto-promoted to piqued admin on next login.',
      },
    ],
  },
  {
    id: 'llm_primary',
    title: 'LLM — Primary',
    description: 'The main model used for article segmentation and (by default) classification + scoring. This is the only LLM block most users need.',
    fields: [
      {
        key: 'llm_provider',
        label: 'Provider',
        help: 'Which LLM vendor to use. Gemini and Claude have generous free tiers; OpenAI is paid; Ollama is local.',
        type: 'select',
        options: [
          { value: 'gemini', label: 'Gemini (Google)' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'claude', label: 'Claude (Anthropic)' },
          { value: 'ollama', label: 'Ollama (local)' },
        ],
      },
      {
        key: 'llm_model',
        label: 'Model',
        help: 'Exact model identifier. Pick from the list or type a custom value. Cheaper/faster models are fine — segmentation does not need a frontier model.',
        type: 'model',
        providerKey: 'llm_provider',
      },
      {
        key: 'llm_api_key',
        label: 'API key',
        help: 'Vendor API key. Stored in the database — do not paste a personal key into a shared instance. Saving "••••••••" leaves the existing value alone.',
        type: 'password',
      },
      {
        key: 'llm_base_url',
        label: 'Base URL',
        help: 'Only needed for Ollama (e.g. http://localhost:11434) or OpenAI-compatible proxies. Leave empty for cloud providers.',
      },
    ],
  },
  {
    id: 'freshrss',
    title: 'FreshRSS',
    description: 'Where piqued pulls articles from. Uses the FreshRSS GReader API.',
    fields: [
      {
        key: 'freshrss_base_url',
        label: 'URL',
        help: 'Base URL of your FreshRSS instance, no trailing slash. Example: https://freshrss.example.com',
      },
      {
        key: 'freshrss_username',
        label: 'Username',
        help: 'Your FreshRSS account username (not the admin user — the account whose feeds you want triaged).',
      },
      {
        key: 'freshrss_api_pass',
        label: 'API password',
        help: 'The API password from FreshRSS → Settings → Authentication. This is NOT your login password — it is a separate token FreshRSS generates for API clients.',
        type: 'password',
      },
    ],
  },
  // Throughput is rendered specially via the preset selector
  {
    id: 'scoring_mode',
    title: 'Scoring mode',
    description: 'How piqued ranks articles against your interest profile.',
    fields: [
      {
        key: 'scoring_mode',
        label: 'Scoring mode',
        help: 'formula = fast keyword/embedding match (no LLM cost). llm = the model writes a confidence score per section (slow + token-heavy). hybrid = formula first, then LLM only on borderline items. Hybrid is the right answer for most users.',
        type: 'select',
        options: [
          { value: 'hybrid', label: 'Hybrid (recommended)' },
          { value: 'formula', label: 'Formula only (no LLM)' },
          { value: 'llm', label: 'LLM only (expensive)' },
        ],
      },
      {
        key: 'confidence_threshold',
        label: 'Confidence threshold',
        help: 'Sections scoring above this appear in the "Likely" tier in your river view. 0.4 is a good middle ground — raise to be pickier, lower to surface more.',
        type: 'number',
      },
      {
        key: 'surprise_surface_pct',
        label: 'Surprise surface',
        help: 'Fraction of low-scoring items piqued randomly promotes to "Discover" so you don\'t live in a filter bubble. 0.10 = 10%.',
        type: 'number',
      },
    ],
  },
  // ── Advanced sections (collapsed by default) ──────────────────
  {
    id: 'llm_classify',
    title: 'LLM — Classification override',
    description: 'Use a different model for content classification. Leave provider empty to inherit from primary.',
    advanced: true,
    fields: [
      {
        key: 'llm_classify_provider',
        label: 'Provider',
        help: 'Empty = use primary LLM. Set to override.',
        type: 'select',
        options: [
          { value: '', label: '(use primary)' },
          { value: 'gemini', label: 'Gemini' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'claude', label: 'Claude' },
          { value: 'ollama', label: 'Ollama' },
        ],
      },
      { key: 'llm_classify_model', label: 'Model', help: 'Model name override.', type: 'model', providerKey: 'llm_classify_provider' },
      { key: 'llm_classify_api_key', label: 'API key', help: 'API key for the override provider.', type: 'password' },
      { key: 'llm_classify_base_url', label: 'Base URL', help: 'Base URL override.' },
    ],
  },
  {
    id: 'llm_scoring',
    title: 'LLM — Scoring override',
    description: 'Use a tiny/cheap model just for interest scoring. Inherits from classification, then primary, if empty.',
    advanced: true,
    fields: [
      {
        key: 'llm_scoring_provider',
        label: 'Provider',
        help: 'Empty = inherit from classification or primary. Useful for routing scoring to a $0/M-token model like gemini-flash-lite.',
        type: 'select',
        options: [
          { value: '', label: '(inherit)' },
          { value: 'gemini', label: 'Gemini' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'claude', label: 'Claude' },
          { value: 'ollama', label: 'Ollama' },
        ],
      },
      { key: 'llm_scoring_model', label: 'Model', help: 'Model name override.', type: 'model', providerKey: 'llm_scoring_provider' },
      { key: 'llm_scoring_api_key', label: 'API key', help: 'API key for scoring override.', type: 'password' },
      { key: 'llm_scoring_base_url', label: 'Base URL', help: 'Base URL override.' },
    ],
  },
  {
    id: 'processing_advanced',
    title: 'Processing — advanced',
    description: 'Knobs that the throughput preset does not cover.',
    advanced: true,
    fields: [
      {
        key: 'max_article_words',
        label: 'Max article words',
        help: 'Articles longer than this are truncated before being sent to the LLM. Keeps token usage predictable on long-form sites.',
        type: 'number',
      },
      {
        key: 'max_retries',
        label: 'Max retries',
        help: 'How many times to retry a failing LLM call before giving up and logging an error.',
        type: 'number',
      },
      {
        key: 'backlog_order',
        label: 'Backlog order',
        help: 'newest_first = catch up on what just landed. oldest_first = drain your unread queue chronologically.',
        type: 'select',
        options: [
          { value: 'newest_first', label: 'Newest first' },
          { value: 'oldest_first', label: 'Oldest first' },
        ],
      },
      {
        key: 'profile_synthesis_threshold',
        label: 'Auto-synthesis threshold',
        help: 'Number of votes piqued waits for before automatically rolling them into your profile. Lower = profile updates faster but is jumpier.',
        type: 'number',
      },
      {
        key: 'profile_max_words',
        label: 'Profile max words',
        help: 'Profile text is truncated to this length when sent to the LLM as context. Keeps prompt cost bounded.',
        type: 'number',
      },
      {
        key: 'scoring_batch_size',
        label: 'Scoring batch size',
        help: 'How many sections piqued packs into a single scoring LLM call. Larger = cheaper per section but slower per request.',
        type: 'number',
      },
    ],
  },
  {
    id: 'decay',
    title: 'Interest decay',
    description: 'Old interests gradually lose weight so your profile follows your tastes. Most users never touch these.',
    advanced: true,
    fields: [
      {
        key: 'interest_decay_rate',
        label: 'Decay rate',
        help: 'Fraction of weight removed per nightly decay cycle (0-1). 0.05 = 5% off per night.',
        type: 'number',
      },
      {
        key: 'interest_decay_after_days',
        label: 'Decay after (days)',
        help: 'Days an interest can sit untouched before decay starts eating it.',
        type: 'number',
      },
    ],
  },
  {
    id: 'output',
    title: 'RSS output',
    description: 'Expose your scored feed as an RSS endpoint other readers can consume.',
    advanced: true,
    fields: [
      {
        key: 'rss_feed_api_key',
        label: 'Feed API key',
        help: 'Static key required to access /rss.xml. Generate something random — anyone with this URL can read your filtered feed.',
        type: 'password',
      },
    ],
  },
]

const showAdvanced = ref(false)

const visibleSections = computed(() =>
  CONFIG_SECTIONS.filter((s) => {
    if (s.showIf && !s.showIf()) return false
    if (s.advanced && !showAdvanced.value) return false
    return true
  }),
)

function visibleFields(section: ConfigSection): ConfigField[] {
  return section.fields.filter((f) => (f.showIf ? f.showIf() : true))
}

// ── Status panel ────────────────────────────────────────────────
const configStatus = computed(() => {
  const llmOk = !!settings.value.llm_provider && !!settings.value.llm_model && (
    settings.value.llm_provider === 'ollama' ||
    !!settings.value.llm_api_key ||
    settings.value.llm_api_key === '••••••••'
  )
  const freshrssOk = !!settings.value.freshrss_base_url && !!settings.value.freshrss_username && (
    !!settings.value.freshrss_api_pass || settings.value.freshrss_api_pass === '••••••••'
  )
  const authOk = authMethods.value.size > 0
  const oidcOk = !hasAuthMethod('oidc') || (
    !!settings.value.oidc_client_id && !!settings.value.oidc_server_metadata_url
  )
  return [
    { label: 'Authentication', ok: authOk && oidcOk },
    { label: 'Primary LLM', ok: llmOk },
    { label: 'FreshRSS', ok: freshrssOk },
    { label: 'Throughput', ok: !!settings.value.max_articles_per_cycle },
  ]
})

// ── Test connection state ───────────────────────────────────────
const testingLlm = ref(false)
const testingFreshrss = ref(false)
const llmTestResult = ref<{ ok: boolean; detail: string } | null>(null)
const freshrssTestResult = ref<{ ok: boolean; detail: string } | null>(null)

async function testLlm() {
  testingLlm.value = true
  llmTestResult.value = null
  try {
    const body: Record<string, string> = {
      provider: settings.value.llm_provider || '',
      model: settings.value.llm_model || '',
      base_url: settings.value.llm_base_url || '',
    }
    // Only include api_key if user changed it (not the masked placeholder)
    if (settings.value.llm_api_key && settings.value.llm_api_key !== '••••••••') {
      body.api_key = settings.value.llm_api_key
    }
    const result = await api.post<{ ok: boolean; detail: string }>('/settings/test-llm', body)
    llmTestResult.value = result
  } catch (err) {
    llmTestResult.value = { ok: false, detail: err instanceof ApiError ? err.detail : 'Test failed' }
  } finally {
    testingLlm.value = false
  }
}

async function testFreshrss() {
  testingFreshrss.value = true
  freshrssTestResult.value = null
  try {
    const body: Record<string, string> = {
      freshrss_base_url: settings.value.freshrss_base_url || '',
      freshrss_username: settings.value.freshrss_username || '',
    }
    if (settings.value.freshrss_api_pass && settings.value.freshrss_api_pass !== '••••••••') {
      body.freshrss_api_pass = settings.value.freshrss_api_pass
    }
    const result = await api.post<{ ok: boolean; detail: string }>('/settings/test-freshrss', body)
    freshrssTestResult.value = result
  } catch (err) {
    freshrssTestResult.value = { ok: false, detail: err instanceof ApiError ? err.detail : 'Test failed' }
  } finally {
    testingFreshrss.value = false
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).then(
    () => toast.success('Copied to clipboard'),
    () => toast.error('Copy failed — select and copy manually'),
  )
}

async function loadProfile() {
  try {
    const data = await api.get<UserProfileResponse>('/profile')
    profileText.value = data.profile_text
    profileVersion.value = data.profile_version
    pendingFeedback.value = data.pending_feedback_count
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Failed to load profile')
  }
}

async function saveProfile() {
  savingProfile.value = true
  try {
    await api.put('/profile', { profile_text: profileText.value })
    toast.success('Profile saved')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Save failed')
  } finally {
    savingProfile.value = false
  }
}

async function synthesize() {
  synthesizing.value = true
  try {
    await api.post('/profile/synthesize')
    toast.success('Synthesis started')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Synthesis failed')
  } finally {
    synthesizing.value = false
  }
}

async function loadConfig() {
  try {
    const data = await api.get<SettingsResponse>('/settings')
    settings.value = data.settings
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Failed to load settings')
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    await api.put('/settings', settings.value)
    toast.success('Settings saved')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Save failed')
  } finally {
    savingConfig.value = false
  }
}

async function loadKeys() {
  try {
    const data = await api.get<ApiKeyList>('/keys')
    apiKeys.value = data.keys
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Failed to load keys')
  }
}

async function createKey() {
  try {
    const result = await api.post<ApiKeyCreated>('/keys', { name: newKeyName.value })
    createdKey.value = result.key
    newKeyName.value = ''
    await loadKeys()
    toast.success('API key created')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Create failed')
  }
}

function requestRevoke(keyId: number) {
  confirmingRevoke.value = keyId
}

function cancelRevoke() {
  confirmingRevoke.value = null
}

async function confirmRevoke(keyId: number) {
  confirmingRevoke.value = null
  try {
    await api.delete(`/keys/${keyId}`)
    apiKeys.value = apiKeys.value.filter((k) => k.id !== keyId)
    toast.success('Key revoked')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Revoke failed')
  }
}

async function loadUsers() {
  try {
    const data = await api.get<UserList>('/users')
    users.value = data.users
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Failed to load users')
  }
}

async function createUser() {
  if (!newUsername.value || !newPassword.value) return
  try {
    await api.post('/users', {
      username: newUsername.value,
      password: newPassword.value,
      role: newRole.value,
    })
    newUsername.value = ''
    newPassword.value = ''
    newRole.value = 'user'
    await loadUsers()
    toast.success('User created')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Create failed')
  }
}

function requestRoleChange(userId: number, role: string) {
  confirmingRoleChange.value = { userId, role }
}

function cancelRoleChange() {
  confirmingRoleChange.value = null
}

async function confirmRoleChange() {
  if (!confirmingRoleChange.value) return
  const { userId, role } = confirmingRoleChange.value
  confirmingRoleChange.value = null
  try {
    await api.put(`/users/${userId}/role`, { role })
    await loadUsers()
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Role change failed')
  }
}

onMounted(async () => {
  loading.value = true
  const promises: Promise<void>[] = [loadProfile(), loadKeys()]
  if (auth.isAdmin) {
    promises.push(loadConfig(), loadUsers())
  }
  await Promise.all(promises)
  loading.value = false
})
</script>

<template>
  <div class="settings-view">
    <h2 class="settings-title">Settings</h2>

    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'profile' }"
        @click="activeTab = 'profile'"
      >
        Profile
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'keys' }"
        @click="activeTab = 'keys'"
      >
        API Keys
      </button>
      <button
        v-if="auth.isAdmin"
        class="tab"
        :class="{ active: activeTab === 'config' }"
        @click="activeTab = 'config'"
      >
        Config
      </button>
      <button
        v-if="auth.isAdmin"
        class="tab"
        :class="{ active: activeTab === 'users' }"
        @click="activeTab = 'users'"
      >
        Users
      </button>
    </div>

    <LoadingSpinner
      v-if="loading"
      message="Loading settings..."
    />

    <!-- Profile tab -->
    <div
      v-else-if="activeTab === 'profile'"
      class="tab-content"
    >
      <div class="field">
        <label
          for="profile-text"
          class="field-label"
        >Interest profile</label>
        <textarea
          id="profile-text"
          v-model="profileText"
          class="field-textarea"
          rows="6"
          placeholder="Describe your interests..."
        />
      </div>
      <div class="field-row">
        <span class="field-info">v{{ profileVersion }} &middot; {{ pendingFeedback }} pending feedback</span>
        <div class="field-actions">
          <div class="synthesize-group">
            <button
              class="btn"
              :disabled="synthesizing || pendingFeedback === 0"
              :title="pendingFeedback === 0 ? 'No pending feedback to incorporate' : ''"
              @click="synthesize"
            >
              {{ synthesizing ? 'Synthesizing...' : 'Synthesize' }}
            </button>
            <span class="field-help">Incorporates your upvote/downvote feedback into your interest profile</span>
          </div>
          <button
            class="btn btn--primary"
            :disabled="savingProfile"
            @click="saveProfile"
          >
            {{ savingProfile ? 'Saving...' : 'Save profile' }}
          </button>
        </div>
      </div>
    </div>

    <!-- API Keys tab -->
    <div
      v-else-if="activeTab === 'keys'"
      class="tab-content"
    >
      <div class="key-create">
        <label
          for="key-name"
          class="sr-only"
        >Key name</label>
        <input
          id="key-name"
          v-model="newKeyName"
          class="field-input"
          type="text"
          placeholder="Key name (optional)"
        >
        <button
          class="btn btn--primary"
          @click="createKey"
        >
          Create key
        </button>
      </div>
      <div
        v-if="createdKey"
        class="key-created"
      >
        <p class="key-created-label">New key (copy now — it won't be shown again):</p>
        <div class="key-created-row">
          <code class="key-created-value">{{ createdKey }}</code>
          <button
            class="btn btn--small"
            @click="copyToClipboard(createdKey!)"
          >
            Copy
          </button>
        </div>
      </div>
      <div class="keys-list">
        <div
          v-for="key in apiKeys"
          :key="key.id"
          class="key-row"
        >
          <div class="key-info">
            <span class="key-name">{{ key.name || 'Unnamed' }}</span>
            <span class="key-date">Created {{ formatDate(key.created_at) }}</span>
          </div>
          <div
            v-if="confirmingRevoke === key.id"
            class="confirm-group"
          >
            <span class="confirm-text">Revoke this key?</span>
            <button
              class="btn btn--danger btn--small"
              @click="confirmRevoke(key.id)"
            >
              Confirm
            </button>
            <button
              class="btn btn--small"
              @click="cancelRevoke"
            >
              Cancel
            </button>
          </div>
          <button
            v-else
            class="btn btn--danger"
            @click="requestRevoke(key.id)"
          >
            Revoke
          </button>
        </div>
        <p
          v-if="!apiKeys.length"
          class="empty-text"
        >
          No API keys.
        </p>
      </div>
    </div>

    <!-- Config tab (admin) -->
    <div
      v-else-if="activeTab === 'config'"
      class="tab-content"
    >
      <!-- Status panel -->
      <div class="status-panel">
        <h3 class="status-title">What's configured</h3>
        <div class="status-grid">
          <div
            v-for="item in configStatus"
            :key="item.label"
            class="status-item"
            :class="{ 'status-item--ok': item.ok, 'status-item--missing': !item.ok }"
          >
            <span class="status-mark">{{ item.ok ? '✓' : '✗' }}</span>
            <span class="status-label">{{ item.label }}</span>
          </div>
        </div>
      </div>

      <!-- Auth section: special checkbox handling -->
      <div class="config-group">
        <h3 class="config-group-title">Authentication</h3>
        <p class="config-group-desc">How users log in. Pick one or more methods.</p>
        <div class="field">
          <span class="field-label">Enabled methods</span>
          <div class="checkbox-group">
            <label class="checkbox-row">
              <input
                type="checkbox"
                :checked="hasAuthMethod('oidc')"
                @change="setAuthMethod('oidc', ($event.target as HTMLInputElement).checked)"
              >
              <span class="checkbox-text">
                <strong>OIDC</strong>
                <span class="field-help">Single sign-on via Authentik, Keycloak, Google, etc. Requires the OIDC section below.</span>
              </span>
            </label>
            <label class="checkbox-row">
              <input
                type="checkbox"
                :checked="hasAuthMethod('local')"
                @change="setAuthMethod('local', ($event.target as HTMLInputElement).checked)"
              >
              <span class="checkbox-text">
                <strong>Local password</strong>
                <span class="field-help">Username + password stored in piqued's database. The simplest option if you don't already have a single sign-on provider.</span>
              </span>
            </label>
            <label class="checkbox-row">
              <input
                type="checkbox"
                :checked="hasAuthMethod('header')"
                @change="setAuthMethod('header', ($event.target as HTMLInputElement).checked)"
              >
              <span class="checkbox-text">
                <strong>Header (forward auth)</strong>
                <span class="field-help">Trust an X-authentik-username header from a reverse proxy. Only enable if a trusted proxy IP is set below — otherwise anyone can spoof the header.</span>
              </span>
            </label>
          </div>
        </div>
        <template
          v-for="field in visibleFields(CONFIG_SECTIONS[0])"
          :key="field.key"
        >
          <div class="field">
            <label
              :for="`config-${field.key}`"
              class="field-label"
            >{{ field.label }}</label>
            <div
              v-if="field.type === 'password'"
              class="password-row"
            >
              <input
                :id="`config-${field.key}`"
                v-model="settings[field.key]"
                class="field-input"
                :type="revealedPasswords.has(field.key) ? 'text' : 'password'"
                autocomplete="off"
              >
              <button
                v-if="!isPlaceholderPassword(field.key)"
                type="button"
                class="btn btn--small password-toggle"
                :aria-label="revealedPasswords.has(field.key) ? 'Hide value' : 'Show value'"
                @click="togglePasswordReveal(field.key)"
              >
                {{ revealedPasswords.has(field.key) ? 'Hide' : 'Show' }}
              </button>
              <span
                v-else
                class="password-placeholder-hint"
              >Saved — enter a new value to change</span>
            </div>
            <input
              v-else
              :id="`config-${field.key}`"
              v-model="settings[field.key]"
              class="field-input"
              :type="field.type || 'text'"
            >
            <span
              v-if="field.help"
              class="field-help"
            >{{ field.help }}</span>
          </div>
        </template>
      </div>

      <!-- Remaining sections, declarative -->
      <template
        v-for="section in visibleSections"
        :key="section.id"
      >
        <div
          v-if="section.id !== 'auth'"
          class="config-group"
        >
          <h3 class="config-group-title">{{ section.title }}</h3>
          <p
            v-if="section.description"
            class="config-group-desc"
          >
            {{ section.description }}
          </p>

          <!-- Test buttons live inside the relevant sections -->
          <div
            v-if="section.id === 'llm_primary'"
            class="test-row"
          >
            <button
              type="button"
              class="btn"
              :disabled="testingLlm"
              @click="testLlm"
            >
              {{ testingLlm ? 'Testing...' : 'Test LLM connection' }}
            </button>
            <span
              v-if="llmTestResult"
              class="test-result"
              :class="{ 'test-result--ok': llmTestResult.ok, 'test-result--fail': !llmTestResult.ok }"
            >
              {{ llmTestResult.detail }}
            </span>
          </div>
          <div
            v-if="section.id === 'freshrss'"
            class="test-row"
          >
            <button
              type="button"
              class="btn"
              :disabled="testingFreshrss"
              @click="testFreshrss"
            >
              {{ testingFreshrss ? 'Testing...' : 'Test FreshRSS connection' }}
            </button>
            <span
              v-if="freshrssTestResult"
              class="test-result"
              :class="{ 'test-result--ok': freshrssTestResult.ok, 'test-result--fail': !freshrssTestResult.ok }"
            >
              {{ freshrssTestResult.detail }}
            </span>
          </div>

          <div
            v-for="field in visibleFields(section)"
            :key="field.key"
            class="field"
          >
            <label
              :for="`config-${field.key}`"
              class="field-label"
            >{{ field.label }}</label>

            <select
              v-if="field.type === 'select'"
              :id="`config-${field.key}`"
              v-model="settings[field.key]"
              class="field-select"
            >
              <option
                v-for="opt in field.options"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>

            <div
              v-else-if="field.type === 'model'"
              class="model-row"
            >
              <select
                v-if="field.providerKey && getModelSuggestions(field.providerKey).length"
                :id="`config-${field.key}`"
                v-model="settings[field.key]"
                class="field-select"
              >
                <option
                  v-for="opt in getModelSuggestions(field.providerKey)"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </option>
                <option value="">Other (type below)</option>
              </select>
              <input
                v-if="!field.providerKey || !getModelSuggestions(field.providerKey).length || !settings[field.key]"
                :id="!field.providerKey || !getModelSuggestions(field.providerKey).length ? `config-${field.key}` : undefined"
                v-model="settings[field.key]"
                class="field-input"
                type="text"
                placeholder="e.g. llama3.1:8b"
              >
            </div>

            <div
              v-else-if="field.type === 'password'"
              class="password-row"
            >
              <input
                :id="`config-${field.key}`"
                v-model="settings[field.key]"
                class="field-input"
                :type="revealedPasswords.has(field.key) ? 'text' : 'password'"
                autocomplete="off"
              >
              <button
                v-if="!isPlaceholderPassword(field.key)"
                type="button"
                class="btn btn--small password-toggle"
                :aria-label="revealedPasswords.has(field.key) ? 'Hide value' : 'Show value'"
                @click="togglePasswordReveal(field.key)"
              >
                {{ revealedPasswords.has(field.key) ? 'Hide' : 'Show' }}
              </button>
              <span
                v-else
                class="password-placeholder-hint"
              >Saved — enter a new value to change</span>
            </div>

            <input
              v-else
              :id="`config-${field.key}`"
              v-model="settings[field.key]"
              class="field-input"
              :type="field.type || 'text'"
            >
            <span
              v-if="field.help"
              class="field-help"
            >{{ field.help }}</span>
          </div>
        </div>

        <!-- Throughput section is rendered separately right after FreshRSS -->
        <div
          v-if="section.id === 'freshrss'"
          class="config-group"
        >
          <h3 class="config-group-title">Throughput</h3>
          <p class="config-group-desc">How fast piqued chews through articles. Pick a preset, or switch to Custom in the advanced section.</p>
          <div class="preset-grid">
            <button
              v-for="(preset, name) in THROUGHPUT_PRESETS"
              :key="name"
              type="button"
              class="preset-card"
              :class="{ 'preset-card--active': activeThroughputPreset === name }"
              @click="applyThroughputPreset(name)"
            >
              <span class="preset-name">{{ preset.label }}</span>
              <span class="preset-desc">{{ preset.description }}</span>
            </button>
            <div
              class="preset-card preset-card--info"
              :class="{ 'preset-card--active': activeThroughputPreset === 'custom' }"
            >
              <span class="preset-name">Custom</span>
              <span class="preset-desc">Edit individual values in Processing — advanced below.</span>
            </div>
          </div>
        </div>
      </template>

      <!-- Advanced toggle -->
      <div class="advanced-toggle">
        <button
          type="button"
          class="btn"
          @click="showAdvanced = !showAdvanced"
        >
          {{ showAdvanced ? 'Hide advanced settings' : 'Show advanced settings' }}
        </button>
      </div>

      <div class="field-row">
        <span />
        <button
          class="btn btn--primary"
          :disabled="savingConfig"
          @click="saveConfig"
        >
          {{ savingConfig ? 'Saving...' : 'Save settings' }}
        </button>
      </div>
    </div>

    <!-- Users tab (admin) -->
    <div
      v-else-if="activeTab === 'users'"
      class="tab-content"
    >
      <div class="user-create">
        <div class="user-create-field">
          <label
            for="new-username"
            class="sr-only"
          >Username</label>
          <input
            id="new-username"
            v-model="newUsername"
            class="field-input"
            type="text"
            placeholder="Username"
          >
        </div>
        <div class="user-create-field">
          <label
            for="new-password"
            class="sr-only"
          >Password</label>
          <input
            id="new-password"
            v-model="newPassword"
            class="field-input"
            type="password"
            placeholder="Password"
          >
        </div>
        <label
          for="new-role"
          class="sr-only"
        >Role</label>
        <select
          id="new-role"
          v-model="newRole"
          class="field-select"
        >
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>
        <button
          class="btn btn--primary"
          @click="createUser"
        >
          Create
        </button>
      </div>
      <div class="users-list">
        <div
          v-for="user in users"
          :key="user.id"
          class="user-row"
        >
          <div class="user-info">
            <span class="user-name">{{ user.username }}</span>
            <span class="user-email">{{ user.email || 'No email' }}</span>
          </div>
          <div
            v-if="confirmingRoleChange && confirmingRoleChange.userId === user.id"
            class="confirm-group"
          >
            <span class="confirm-text">
              Change to {{ confirmingRoleChange.role }}?
            </span>
            <button
              class="btn btn--primary btn--small"
              @click="confirmRoleChange"
            >
              Confirm
            </button>
            <button
              class="btn btn--small"
              @click="cancelRoleChange"
            >
              Cancel
            </button>
          </div>
          <div v-else>
            <label
              :for="`role-${user.id}`"
              class="sr-only"
            >Role for {{ user.username }}</label>
            <select
              :id="`role-${user.id}`"
              :value="user.role"
              class="field-select field-select--small"
              @change="requestRoleChange(user.id, ($event.target as HTMLSelectElement).value)"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  max-width: 40rem;
  margin: 0 auto;
}

.settings-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0 0 1rem;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--pq-border);
  margin-bottom: 1.25rem;
}

.tab {
  padding: 0.5rem 1rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--pq-muted);
  font-size: 0.8125rem;
  cursor: pointer;
}

.tab:hover {
  color: var(--pq-text);
}

.tab.active {
  color: var(--pq-accent);
  border-bottom-color: var(--pq-accent);
  font-weight: 500;
}

.tab-content {
  padding: 0.5rem 0;
}

.field {
  margin-bottom: 0.75rem;
}

.field-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--pq-muted);
  margin-bottom: 0.25rem;
}

.field-help {
  display: block;
  font-size: 0.6875rem;
  color: var(--pq-muted);
  margin-top: 0.125rem;
  opacity: 0.8;
}

.field-input,
.field-textarea,
.field-select {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: var(--pq-bg);
  color: var(--pq-text);
  font-family: var(--pq-font-sans);
  font-size: 0.8125rem;
}

.field-textarea {
  resize: vertical;
}

.field-input:focus,
.field-textarea:focus,
.field-select:focus {
  border-color: var(--pq-accent);
  outline: none;
}

.field-input:focus-visible,
.field-textarea:focus-visible,
.field-select:focus-visible {
  outline: 2px solid var(--pq-accent);
  outline-offset: 1px;
}

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.5rem;
}

.field-info {
  font-size: 0.75rem;
  color: var(--pq-muted);
}

.field-actions {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
}

.synthesize-group {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.125rem;
}

.btn {
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: none;
  color: var(--pq-text);
  font-size: 0.8125rem;
  cursor: pointer;
}

.btn:hover {
  border-color: var(--pq-muted);
}

.btn--primary {
  background: var(--pq-accent);
  color: #fff;
  border-color: var(--pq-accent);
}

.btn--danger {
  color: var(--pq-danger);
  border-color: var(--pq-danger);
}

.btn--small {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.key-create,
.user-create {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.key-create .field-input,
.user-create-field {
  flex: 1;
}

.user-create-field .field-input {
  width: 100%;
}

.user-create .field-select {
  width: auto;
}

.key-created {
  padding: 0.75rem;
  background: color-mix(in srgb, var(--pq-success) 10%, transparent);
  border-radius: var(--pq-radius);
  margin-bottom: 1rem;
}

.key-created-label {
  font-size: 0.75rem;
  color: var(--pq-success);
  margin: 0 0 0.25rem;
}

.key-created-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.key-created-value {
  font-family: var(--pq-font-mono);
  font-size: 0.8125rem;
  color: var(--pq-text);
  word-break: break-all;
  flex: 1;
}

.key-row,
.user-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--pq-border);
}

.key-info,
.user-info {
  min-width: 0;
}

.key-name,
.user-name {
  display: block;
  font-size: 0.8125rem;
  color: var(--pq-text);
}

.key-date,
.user-email {
  display: block;
  font-size: 0.6875rem;
  color: var(--pq-muted);
}

.field-select--small {
  width: auto;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.empty-text {
  font-size: 0.8125rem;
  color: var(--pq-muted);
  padding: 1rem 0;
}

.config-group {
  margin-bottom: 1.75rem;
}

.config-group-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0 0 0.25rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--pq-border);
}

.config-group-desc {
  font-size: 0.75rem;
  color: var(--pq-muted);
  margin: 0 0 0.75rem;
  line-height: 1.4;
}

.status-panel {
  padding: 0.75rem 1rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: color-mix(in srgb, var(--pq-accent) 5%, transparent);
  margin-bottom: 1.5rem;
}

.status-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--pq-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.5rem;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 0.375rem 1rem;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}

.status-mark {
  font-weight: 700;
  font-size: 0.875rem;
  width: 1rem;
  text-align: center;
}

.status-item--ok .status-mark {
  color: var(--pq-success);
}

.status-item--missing .status-mark {
  color: var(--pq-danger);
}

.status-label {
  color: var(--pq-text);
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.5rem 0;
}

.checkbox-row {
  display: flex;
  gap: 0.625rem;
  align-items: flex-start;
  cursor: pointer;
}

.checkbox-row input[type="checkbox"] {
  margin-top: 0.1875rem;
  flex-shrink: 0;
}

.checkbox-text {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  font-size: 0.8125rem;
  color: var(--pq-text);
}

.checkbox-text strong {
  font-weight: 600;
}

.password-row {
  display: flex;
  gap: 0.375rem;
  align-items: stretch;
  width: 100%;
}

.password-row .field-input {
  flex: 1 1 auto;
  width: auto;
  min-width: 0;
}

.password-toggle {
  flex: 0 0 auto;
  white-space: nowrap;
}

.password-placeholder-hint {
  flex: 0 0 auto;
  font-size: 0.75rem;
  color: var(--pq-muted);
  align-self: center;
  white-space: nowrap;
}

.model-row {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.preset-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: var(--pq-bg);
  text-align: left;
  cursor: pointer;
  font-family: inherit;
}

.preset-card:hover {
  border-color: var(--pq-muted);
}

.preset-card--active {
  border-color: var(--pq-accent);
  background: color-mix(in srgb, var(--pq-accent) 8%, var(--pq-bg));
}

.preset-card--info {
  cursor: default;
}

.preset-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--pq-text);
}

.preset-desc {
  font-size: 0.6875rem;
  color: var(--pq-muted);
  line-height: 1.4;
}

.test-row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.test-result {
  font-size: 0.75rem;
  flex: 1;
  min-width: 0;
}

.test-result--ok {
  color: var(--pq-success);
}

.test-result--fail {
  color: var(--pq-danger);
}

.advanced-toggle {
  display: flex;
  justify-content: center;
  margin: 1rem 0;
  padding-top: 1rem;
  border-top: 1px dashed var(--pq-border);
}

.confirm-group {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.confirm-text {
  font-size: 0.75rem;
  color: var(--pq-muted);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
