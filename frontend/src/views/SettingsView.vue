<script setup lang="ts">
import { ref, onMounted } from 'vue'
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

// Config state (admin)
const settings = ref<Record<string, string>>({})
const savingConfig = ref(false)

// API keys state
const apiKeys = ref<ApiKeyItem[]>([])
const newKeyName = ref('')
const createdKey = ref<string | null>(null)

// Users state (admin)
const users = ref<UserInfo[]>([])
const newUsername = ref('')
const newPassword = ref('')
const newRole = ref('user')

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
  try {
    await api.put('/profile', { profile_text: profileText.value })
    toast.success('Profile saved')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Save failed')
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

async function revokeKey(keyId: number) {
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

async function changeRole(userId: number, role: string) {
  try {
    await api.put(`/users/${userId}/role`, { role })
    await loadUsers()
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Role change failed')
  }
}

onMounted(async () => {
  loading.value = true
  await loadProfile()
  await loadKeys()
  if (auth.isAdmin) {
    await loadConfig()
    await loadUsers()
  }
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
        <label class="field-label">Interest profile</label>
        <textarea
          v-model="profileText"
          class="field-textarea"
          rows="6"
          placeholder="Describe your interests..."
        />
      </div>
      <div class="field-row">
        <span class="field-info">v{{ profileVersion }} &middot; {{ pendingFeedback }} pending feedback</span>
        <div class="field-actions">
          <button
            class="btn"
            :disabled="synthesizing"
            @click="synthesize"
          >
            {{ synthesizing ? 'Synthesizing...' : 'Synthesize' }}
          </button>
          <button
            class="btn btn--primary"
            @click="saveProfile"
          >
            Save profile
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
        <input
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
        <code class="key-created-value">{{ createdKey }}</code>
      </div>
      <div class="keys-list">
        <div
          v-for="key in apiKeys"
          :key="key.id"
          class="key-row"
        >
          <div class="key-info">
            <span class="key-name">{{ key.name || 'Unnamed' }}</span>
            <span class="key-date">Created {{ key.created_at }}</span>
          </div>
          <button
            class="btn btn--danger"
            @click="revokeKey(key.id)"
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
        v-for="(_value, key) in settings"
        :key="key"
        class="field"
      >
        <label class="field-label">{{ key }}</label>
        <input
          v-model="settings[key]"
          class="field-input"
          :type="key.includes('key') || key.includes('pass') ? 'password' : 'text'"
        >
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
        <input
          v-model="newUsername"
          class="field-input"
          type="text"
          placeholder="Username"
        >
        <input
          v-model="newPassword"
          class="field-input"
          type="password"
          placeholder="Password"
        >
        <select
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
          <select
            :value="user.role"
            class="field-select field-select--small"
            @change="changeRole(user.id, ($event.target as HTMLSelectElement).value)"
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
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
  outline: none;
  border-color: var(--pq-accent);
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
.user-create .field-input {
  flex: 1;
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

.key-created-value {
  font-family: var(--pq-font-mono);
  font-size: 0.8125rem;
  color: var(--pq-text);
  word-break: break-all;
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
</style>
