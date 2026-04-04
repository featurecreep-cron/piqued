<script setup lang="ts">
import { useToast } from '@/composables/useToast'
import Toast from './Toast.vue'

const { toasts, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="toasts.length"
      class="toast-container"
      aria-live="polite"
    >
      <Toast
        v-for="t in toasts"
        :key="t.id"
        :type="t.type"
        :message="t.message"
        @dismiss="dismiss(t.id)"
      />
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  z-index: 9999;
  max-width: 24rem;
}
</style>
