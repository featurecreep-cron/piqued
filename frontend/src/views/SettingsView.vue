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
  label: string
  help: string
  type?: 'text' | 'password' | 'number'
}

const CONFIG_META: Record<string, { title: string; fields: Record<string, ConfigField> }> = {
  auth: {
    title: 'Authentication',
    fields: {
      auth_methods: {
        label: 'Auth methods',
        help: 'Comma-separated list of enabled methods: oidc, local, header',
      },
      session_secret_key: {
        label: 'Session secret',
        help: 'Auto-generated on first boot. Change to invalidate all sessions.',
        type: 'password',
      },
      trusted_proxy_ip: {
        label: 'Trusted proxy IP',
        help: 'IP allowed to send X-authentik-username headers for proxy auth',
      },
    },
  },
  oidc: {
    title: 'OIDC (Authentik)',
    fields: {
      oidc_client_id: { label: 'Client ID', help: 'OAuth2 client ID from your identity provider' },
      oidc_client_secret: { label: 'Client secret', help: 'OAuth2 client secret', type: 'password' },
      oidc_server_metadata_url: {
        label: 'Metadata URL',
        help: 'OpenID Connect discovery URL, e.g. https://auth.example.com/.well-known/openid-configuration',
      },
      oidc_admin_group: { label: 'Admin group', help: 'Identity provider group that grants admin role' },
    },
  },
  llm_primary: {
    title: 'LLM — Primary',
    fields: {
      llm_provider: { label: 'Provider', help: 'gemini, openai, or ollama' },
      llm_model: { label: 'Model', help: 'Model name, e.g. gemini-2.5-flash' },
      llm_api_key: { label: 'API key', help: 'Provider API key', type: 'password' },
      llm_base_url: { label: 'Base URL', help: 'Only needed for Ollama (e.g. http://localhost:11434)' },
    },
  },
  llm_classify: {
    title: 'LLM — Classification (optional)',
    fields: {
      llm_classify_provider: { label: 'Provider', help: 'Leave empty to use primary LLM' },
      llm_classify_model: { label: 'Model', help: 'Override model for content classification' },
      llm_classify_api_key: { label: 'API key', help: 'Override API key', type: 'password' },
      llm_classify_base_url: { label: 'Base URL', help: 'Override base URL' },
    },
  },
  llm_scoring: {
    title: 'LLM — Scoring (optional)',
    fields: {
      llm_scoring_provider: { label: 'Provider', help: 'Leave empty to use classification or primary LLM' },
      llm_scoring_model: { label: 'Model', help: 'Use a cheap/fast model for interest scoring' },
      llm_scoring_api_key: { label: 'API key', help: 'Override API key', type: 'password' },
      llm_scoring_base_url: { label: 'Base URL', help: 'Override base URL' },
    },
  },
  freshrss: {
    title: 'FreshRSS',
    fields: {
      freshrss_base_url: { label: 'URL', help: 'Base URL of your FreshRSS instance' },
      freshrss_username: { label: 'Username', help: 'FreshRSS API username' },
      freshrss_api_pass: { label: 'API password', help: 'FreshRSS API password', type: 'password' },
    },
  },
  processing: {
    title: 'Processing',
    fields: {
      feed_poll_interval_minutes: { label: 'Poll interval', help: 'Minutes between feed checks', type: 'number' },
      max_concurrent_articles: { label: 'Concurrent articles', help: 'Max articles processed simultaneously', type: 'number' },
      max_article_words: { label: 'Max article words', help: 'Articles longer than this are truncated', type: 'number' },
      daily_token_budget: { label: 'Daily token budget', help: 'Max LLM tokens per day across all tasks', type: 'number' },
      max_retries: { label: 'Max retries', help: 'Retry count for failed LLM calls', type: 'number' },
      backlog_order: { label: 'Backlog order', help: 'newest_first or oldest_first' },
      max_articles_per_cycle: { label: 'Articles per cycle', help: 'Max articles processed per poll cycle', type: 'number' },
    },
  },
  interest: {
    title: 'Interest Model',
    fields: {
      confidence_threshold: { label: 'Confidence threshold', help: 'Score above this appears in "Likely" tier (0-1)', type: 'number' },
      surprise_surface_pct: { label: 'Surprise surface %', help: 'Fraction of below-threshold items shown as "Discover"', type: 'number' },
      scoring_mode: { label: 'Scoring mode', help: 'formula, llm, or hybrid' },
      profile_synthesis_threshold: { label: 'Synthesis threshold', help: 'Feedback count needed before auto-synthesis', type: 'number' },
      profile_max_words: { label: 'Max profile words', help: 'Profile text truncated to this length for prompts', type: 'number' },
      scoring_batch_size: { label: 'Scoring batch size', help: 'Sections scored per LLM call', type: 'number' },
    },
  },
  decay: {
    title: 'Interest Decay',
    fields: {
      interest_decay_rate: { label: 'Decay rate', help: 'Weight reduction per decay cycle (0-1)', type: 'number' },
      interest_decay_after_days: { label: 'Decay after days', help: 'Days without reinforcement before decay starts', type: 'number' },
    },
  },
  output: {
    title: 'RSS Output',
    fields: {
      rss_feed_api_key: { label: 'Feed API key', help: 'API key for authenticated RSS feed access', type: 'password' },
    },
  },
}

// Group settings by category for display
const configGroups = computed(() => {
  const groups: { title: string; fields: { key: string; label: string; help: string; type: string }[] }[] = []
  const assigned = new Set<string>()

  for (const [, group] of Object.entries(CONFIG_META)) {
    const fields: { key: string; label: string; help: string; type: string }[] = []
    for (const [key, meta] of Object.entries(group.fields)) {
      if (key in settings.value) {
        fields.push({
          key,
          label: meta.label,
          help: meta.help,
          type: meta.type || (key.includes('key') || key.includes('pass') || key.includes('secret') ? 'password' : 'text'),
        })
        assigned.add(key)
      }
    }
    if (fields.length) {
      groups.push({ title: group.title, fields })
    }
  }

  // Any unrecognized keys go in an "Other" group
  const other: { key: string; label: string; help: string; type: string }[] = []
  for (const key of Object.keys(settings.value)) {
    if (!assigned.has(key)) {
      other.push({
        key,
        label: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        help: '',
        type: key.includes('key') || key.includes('pass') || key.includes('secret') ? 'password' : 'text',
      })
    }
  }
  if (other.length) {
    groups.push({ title: 'Other', fields: other })
  }

  return groups
})

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
      <div
        v-for="group in configGroups"
        :key="group.title"
        class="config-group"
      >
        <h3 class="config-group-title">{{ group.title }}</h3>
        <div
          v-for="field in group.fields"
          :key="field.key"
          class="field"
        >
          <label
            :for="`config-${field.key}`"
            class="field-label"
          >{{ field.label }}</label>
          <input
            :id="`config-${field.key}`"
            v-model="settings[field.key]"
            class="field-input"
            :type="field.type"
          >
          <span
            v-if="field.help"
            class="field-help"
          >{{ field.help }}</span>
        </div>
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
  margin-bottom: 1.5rem;
}

.config-group-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0 0 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--pq-border);
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
