<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <h2 class="not-found-title">Page not found</h2>
    <p class="not-found-text">The page you're looking for doesn't exist or has been moved.</p>
    <button
      class="not-found-btn"
      @click="router.push('/')"
    >
      Back to Triage
    </button>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  text-align: center;
}

.not-found-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0 0 0.5rem;
}

.not-found-text {
  font-size: 0.875rem;
  color: var(--pq-muted);
  margin: 0 0 1.5rem;
}

.not-found-btn {
  padding: 0.5rem 1rem;
  background: var(--pq-accent);
  color: #fff;
  border: none;
  border-radius: var(--pq-radius);
  font-size: 0.8125rem;
  cursor: pointer;
}

.not-found-btn:hover {
  opacity: 0.9;
}
</style>
