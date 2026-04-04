<script setup lang="ts">
import { RouterView } from 'vue-router'
import ToastContainer from '@/components/layout/ToastContainer.vue'
import KeyboardHelp from '@/components/layout/KeyboardHelp.vue'
import { useTheme } from '@/composables/useTheme'
import { useKeyboard } from '@/composables/useKeyboard'
import { useAuthStore } from '@/stores/auth'

const { theme, toggle: toggleTheme } = useTheme()
const { helpVisible } = useKeyboard()
const auth = useAuthStore()
</script>

<template>
  <div class="app">
    <header class="app-header">
      <h1 class="app-title">Piqued</h1>
      <nav class="app-nav">
        <RouterLink to="/">Triage</RouterLink>
        <RouterLink to="/feeds">Feeds</RouterLink>
        <RouterLink to="/log">Log</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
      </nav>
      <div class="app-toolbar">
        <button
          class="toolbar-btn"
          :aria-label="`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`"
          @click="toggleTheme"
        >
          {{ theme === 'light' ? '&#9790;' : '&#9728;' }}
        </button>
        <button
          class="toolbar-btn"
          aria-label="Keyboard shortcuts"
          @click="helpVisible = true"
        >
          ?
        </button>
        <span
          v-if="auth.isAuthenticated"
          class="toolbar-user"
        >{{ auth.username }}</span>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
    <ToastContainer />
    <KeyboardHelp
      v-if="helpVisible"
      @close="helpVisible = false"
    />
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--pq-border);
  background: var(--pq-bg);
}

.app-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
  color: var(--pq-text);
}

.app-nav {
  display: flex;
  gap: 1rem;
  flex: 1;
}

.app-nav a {
  color: var(--pq-muted);
  text-decoration: none;
  font-size: 0.875rem;
}

.app-nav a:hover,
.app-nav a.router-link-active {
  color: var(--pq-accent);
}

.app-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toolbar-btn {
  background: none;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  color: var(--pq-muted);
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  line-height: 1;
}
.toolbar-btn:hover {
  color: var(--pq-text);
  border-color: var(--pq-muted);
}

.toolbar-user {
  font-size: 0.8rem;
  color: var(--pq-muted);
  margin-left: 0.25rem;
}

.app-main {
  flex: 1;
  padding: 1.5rem;
}
</style>
