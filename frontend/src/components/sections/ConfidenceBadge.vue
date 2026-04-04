<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
  threshold: number
  isSurprise?: boolean
}>()

const tier = computed(() => {
  if (props.isSurprise) return 'discover'
  if (props.score >= props.threshold) return 'likely'
  if (props.score >= props.threshold * 0.7) return 'maybe'
  return 'skip'
})

const label = computed(() => {
  const labels: Record<string, string> = {
    likely: 'Likely',
    maybe: 'Maybe',
    skip: 'Skip',
    discover: 'Discover',
  }
  return labels[tier.value]
})

const pct = computed(() => Math.round(props.score * 100))
</script>

<template>
  <span
    class="badge"
    :class="`badge--${tier}`"
  >{{ label }} {{ pct }}%</span>
</template>

<style scoped>
.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: var(--pq-radius);
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}

.badge--likely {
  background: color-mix(in srgb, var(--pq-success) 15%, transparent);
  color: var(--pq-success);
}

.badge--maybe {
  background: color-mix(in srgb, var(--pq-warning) 15%, transparent);
  color: var(--pq-warning);
}

.badge--skip {
  background: color-mix(in srgb, var(--pq-muted) 15%, transparent);
  color: var(--pq-muted);
}

.badge--discover {
  background: color-mix(in srgb, var(--pq-discover) 15%, transparent);
  color: var(--pq-discover);
}
</style>
