<script setup lang="ts">
import type { FeedItem } from '@/types/api'

defineProps<{
  feed: FeedItem
  isAdmin: boolean
}>()

const emit = defineEmits<{
  toggle: [feedId: number]
  navigate: [feedId: number]
}>()

function qualityColor(quality: string): string {
  switch (quality) {
    case 'high':
      return 'var(--pq-success)'
    case 'medium':
      return 'var(--pq-warning)'
    case 'low':
      return 'var(--pq-danger)'
    default:
      return 'var(--pq-muted)'
  }
}
</script>

<template>
  <div
    class="feed-card"
    :class="{ inactive: !feed.active }"
  >
    <div
      class="feed-main"
      @click="emit('navigate', feed.id)"
    >
      <h3 class="feed-title">{{ feed.title }}</h3>
      <div class="feed-meta">
        <span class="feed-category">{{ feed.category }}</span>
        <span class="feed-articles">{{ feed.article_count }} articles</span>
        <span
          class="feed-quality"
          :style="{ color: qualityColor(feed.content_quality) }"
        >{{ feed.content_quality }}</span>
      </div>
    </div>
    <button
      v-if="isAdmin"
      class="feed-toggle"
      :class="{ active: feed.active }"
      :aria-label="feed.active ? 'Disable feed' : 'Enable feed'"
      @click="emit('toggle', feed.id)"
    >
      {{ feed.active ? 'On' : 'Off' }}
    </button>
  </div>
</template>

<style scoped>
.feed-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: var(--pq-bg);
}

.feed-card.inactive {
  opacity: 0.5;
}

.feed-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.feed-main:hover .feed-title {
  color: var(--pq-accent);
}

.feed-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--pq-muted);
  margin-top: 0.125rem;
}

.feed-toggle {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: none;
  font-size: 0.75rem;
  color: var(--pq-muted);
  cursor: pointer;
  flex-shrink: 0;
}

.feed-toggle.active {
  color: var(--pq-success);
  border-color: var(--pq-success);
}
</style>
