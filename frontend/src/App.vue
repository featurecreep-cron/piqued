<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header class="app-header">
      <h1 class="app-title">Piqued</h1>
      <nav class="app-nav">
        <RouterLink to="/">Triage</RouterLink>
        <RouterLink to="/feeds">Feeds</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
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

.app-main {
  flex: 1;
  padding: 1.5rem;
}
</style>
