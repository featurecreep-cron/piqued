<script setup lang="ts">
import { computed } from 'vue'
import { useContentStore } from '@/stores/content'

const content = useContentStore()

const emit = defineEmits<{
  filter: [type: string, value: string]
}>()

const props = defineProps<{
  activeFilter: { type: string; value: string }
}>()

const allTags = computed(() => {
  const tags = new Set<string>()
  for (const s of content.sections) {
    for (const t of s.topic_tags) {
      tags.add(t)
    }
  }
  return [...tags].sort()
})

const allFeeds = computed(() => {
  const feeds = new Map<string, number>()
  for (const s of content.sections) {
    feeds.set(s.feed_title, (feeds.get(s.feed_title) ?? 0) + 1)
  }
  return [...feeds.entries()].sort((a, b) => b[1] - a[1])
})

function isActive(type: string, value: string): boolean {
  return props.activeFilter.type === type && props.activeFilter.value === value
}
</script>

<template>
  <nav class="nav-tree">
    <div class="nav-group">
      <h4 class="nav-group-title">Triage</h4>
      <button
        class="nav-item"
        :class="{ active: isActive('triage', 'all') }"
        @click="emit('filter', 'triage', 'all')"
      >
        All sections
        <span class="nav-count">{{ content.sections.length }}</span>
      </button>
      <button
        class="nav-item"
        :class="{ active: isActive('triage', 'likely') }"
        @click="emit('filter', 'triage', 'likely')"
      >
        Likely
        <span class="nav-count">{{ content.aboveSections.length }}</span>
      </button>
      <button
        class="nav-item"
        :class="{ active: isActive('triage', 'discover') }"
        @click="emit('filter', 'triage', 'discover')"
      >
        Discover
        <span class="nav-count">{{ content.surpriseSections.length }}</span>
      </button>
    </div>

    <div
      v-if="allTags.length"
      class="nav-group"
    >
      <h4 class="nav-group-title">Topics</h4>
      <button
        v-for="tag in allTags"
        :key="tag"
        class="nav-item"
        :class="{ active: isActive('tag', tag) }"
        @click="emit('filter', 'tag', tag)"
      >
        {{ tag }}
      </button>
    </div>

    <div
      v-if="allFeeds.length"
      class="nav-group"
    >
      <h4 class="nav-group-title">Feeds</h4>
      <button
        v-for="[feed, count] in allFeeds"
        :key="feed"
        class="nav-item"
        :class="{ active: isActive('feed', feed) }"
        @click="emit('filter', 'feed', feed)"
      >
        {{ feed }}
        <span class="nav-count">{{ count }}</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.nav-tree {
  padding: 0.5rem 0;
  overflow-y: auto;
  height: 100%;
}

.nav-group {
  margin-bottom: 0.75rem;
}

.nav-group-title {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  padding: 0.25rem 0.75rem;
  margin: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.375rem 0.75rem;
  background: none;
  border: none;
  text-align: left;
  font-size: 0.8125rem;
  color: var(--pq-text);
  cursor: pointer;
  border-radius: var(--pq-radius);
  margin: 0 0.25rem;
  width: calc(100% - 0.5rem);
}

.nav-item:hover {
  background: var(--pq-card-bg);
}

.nav-item.active {
  background: color-mix(in srgb, var(--pq-accent) 12%, transparent);
  color: var(--pq-accent);
  font-weight: 500;
}

.nav-count {
  font-size: 0.6875rem;
  color: var(--pq-muted);
  min-width: 1.5rem;
  text-align: right;
}
</style>
