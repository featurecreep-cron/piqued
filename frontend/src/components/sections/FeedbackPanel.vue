<script setup lang="ts">
import { computed } from 'vue'
import { useFeedback } from '@/composables/useFeedback'

const props = defineProps<{
  sectionId: number
}>()

const emit = defineEmits<{
  vote: [rating: 1 | -1]
}>()

const feedback = useFeedback()

const voted = computed(() => feedback.getVote(props.sectionId))

function handleVote(rating: 1 | -1) {
  emit('vote', rating)
}
</script>

<template>
  <div class="feedback-panel">
    <button
      class="vote-btn vote-up"
      :class="{ active: voted === 1 }"
      :aria-pressed="voted === 1"
      aria-label="Upvote"
      @click="handleVote(1)"
    >
      &uarr;
    </button>
    <button
      class="vote-btn vote-down"
      :class="{ active: voted === -1 }"
      :aria-pressed="voted === -1"
      aria-label="Downvote"
      @click="handleVote(-1)"
    >
      &darr;
    </button>
  </div>
</template>

<style scoped>
.feedback-panel {
  display: flex;
  gap: 0.25rem;
}

.vote-btn {
  background: none;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  color: var(--pq-muted);
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  line-height: 1;
  transition: all 0.15s;
}

.vote-btn:hover {
  border-color: var(--pq-muted);
}

.vote-up:hover,
.vote-up.active {
  color: var(--pq-success);
  border-color: var(--pq-success);
}

.vote-down:hover,
.vote-down.active {
  color: var(--pq-danger);
  border-color: var(--pq-danger);
}
</style>
