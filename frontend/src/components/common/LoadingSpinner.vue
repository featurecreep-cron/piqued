<script setup lang="ts">
defineProps<{
  message?: string
}>()
</script>

<template>
  <div
    class="loading"
    role="status"
    aria-live="polite"
  >
    <div
      class="spinner"
      aria-hidden="true"
    />
    <p
      v-if="message"
      class="loading-message"
    >
      {{ message }}
    </p>
  </div>
</template>

<style scoped>
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
}

.spinner {
  width: 1.5rem;
  height: 1.5rem;
  border: 2px solid var(--pq-border);
  border-top-color: var(--pq-accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.loading-message {
  font-size: 0.8125rem;
  color: var(--pq-muted);
  margin: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
