<script setup lang="ts">
import type { SectionItem } from '@/types/api'
import ConfidenceBadge from './ConfidenceBadge.vue'

defineProps<{
  section: SectionItem
  threshold: number
  isSurprise: boolean
  focused: boolean
  selected: boolean
}>()

defineEmits<{
  select: [sectionId: number]
}>()
</script>

<template>
  <div
    class="compact-card"
    :class="{ focused, selected }"
    tabindex="0"
    @click="$emit('select', section.id)"
    @keydown.enter="$emit('select', section.id)"
  >
    <div class="compact-main">
      <span class="compact-heading">{{ section.heading || section.article_title }}</span>
      <span class="compact-feed">{{ section.feed_title }}</span>
    </div>
    <ConfidenceBadge
      :score="section.score"
      :threshold="threshold"
      :is-surprise="isSurprise"
    />
  </div>
</template>

<style scoped>
.compact-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--pq-border);
  cursor: pointer;
  transition: background 0.1s;
}

.compact-card:hover {
  background: var(--pq-card-bg);
}

.compact-card.focused {
  background: color-mix(in srgb, var(--pq-accent) 8%, transparent);
}

.compact-card.selected {
  background: color-mix(in srgb, var(--pq-accent) 12%, transparent);
  border-left: 2px solid var(--pq-accent);
  padding-left: calc(0.75rem - 2px);
}

.compact-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.compact-heading {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--pq-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-feed {
  font-size: 0.6875rem;
  color: var(--pq-muted);
}
</style>
