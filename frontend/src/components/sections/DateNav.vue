<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  current: string
  available: string[]
}>()

const emit = defineEmits<{
  select: [date: string]
}>()

const currentIndex = computed(() => props.available.indexOf(props.current))

const canPrev = computed(() => currentIndex.value < props.available.length - 1)
const canNext = computed(() => currentIndex.value > 0)

function prev() {
  if (canPrev.value) {
    emit('select', props.available[currentIndex.value + 1])
  }
}

function next() {
  if (canNext.value) {
    emit('select', props.available[currentIndex.value - 1])
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = today.getTime() - d.getTime()
  const days = Math.round(diff / (1000 * 60 * 60 * 24))
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="date-nav">
    <button
      class="date-btn"
      :disabled="!canPrev"
      aria-label="Previous date"
      @click="prev"
    >
      &larr;
    </button>
    <span class="date-label">{{ formatDate(current) }}</span>
    <button
      class="date-btn"
      :disabled="!canNext"
      aria-label="Next date"
      @click="next"
    >
      &rarr;
    </button>
  </div>
</template>

<style scoped>
.date-nav {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.date-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--pq-text);
  min-width: 8rem;
  text-align: center;
}

.date-btn {
  background: none;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  color: var(--pq-muted);
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  line-height: 1;
}

.date-btn:hover:not(:disabled) {
  color: var(--pq-text);
  border-color: var(--pq-muted);
}

.date-btn:disabled {
  opacity: 0.3;
  cursor: default;
}
</style>
