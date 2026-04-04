<script setup lang="ts">
import type { ToastType } from '@/composables/useToast'

defineProps<{
  type: ToastType
  message: string
}>()

defineEmits<{
  dismiss: []
}>()
</script>

<template>
  <div
    class="toast"
    :class="`toast--${type}`"
    role="alert"
  >
    <span class="toast-message">{{ message }}</span>
    <button
      class="toast-close"
      aria-label="Dismiss"
      @click="$emit('dismiss')"
    >
      &times;
    </button>
  </div>
</template>

<style scoped>
.toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 1rem;
  border-radius: var(--pq-radius);
  font-size: 0.875rem;
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  animation: toast-in 0.2s ease-out;
}

.toast--success {
  background: var(--pq-success);
}
.toast--error {
  background: var(--pq-danger);
}
.toast--info {
  background: var(--pq-accent);
}

.toast-message {
  flex: 1;
}

.toast-close {
  background: none;
  border: none;
  color: inherit;
  font-size: 1.125rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  opacity: 0.8;
}
.toast-close:hover {
  opacity: 1;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateY(0.5rem);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
