<script setup lang="ts">
defineProps<{
  message: string
}>()
</script>

<template>
  <div
    class="empty-state"
    role="status"
  >
    <p class="empty-message">{{ message }}</p>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem;
}

.empty-message {
  font-size: 0.875rem;
  color: var(--pq-muted);
  margin: 0;
}
</style>
