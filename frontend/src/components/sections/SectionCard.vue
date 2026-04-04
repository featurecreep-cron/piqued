<script setup lang="ts">
import { ref, computed } from 'vue'
import type { SectionItem } from '@/types/api'
import ConfidenceBadge from './ConfidenceBadge.vue'
import TagChip from './TagChip.vue'
import FeedbackPanel from './FeedbackPanel.vue'

const props = defineProps<{
  section: SectionItem
  threshold: number
  isSurprise: boolean
  focused: boolean
}>()

const emit = defineEmits<{
  vote: [sectionId: number, rating: 1 | -1]
  downweight: [tag: string]
  clickThrough: [sectionId: number]
}>()

const expanded = ref(false)

function toggle() {
  expanded.value = !expanded.value
}

function openArticle() {
  if (props.section.article_url) {
    window.open(props.section.article_url, '_blank', 'noopener')
    emit('clickThrough', props.section.id)
  }
}

const flags = computed(() => {
  const f: string[] = []
  if (props.section.has_humor) f.push('humor')
  if (props.section.has_surprise_data) f.push('surprise data')
  if (props.section.has_actionable_advice) f.push('actionable')
  return f
})
</script>

<template>
  <article
    class="section-card"
    :class="{ focused, expanded }"
    tabindex="0"
    @click="toggle"
    @keydown.enter="toggle"
  >
    <div class="card-header">
      <div class="card-meta">
        <span class="card-feed">{{ section.feed_title }}</span>
        <span class="card-article">{{ section.article_title }}</span>
      </div>
      <ConfidenceBadge
        :score="section.score"
        :threshold="threshold"
        :is-surprise="isSurprise"
      />
    </div>

    <h3 class="card-heading">{{ section.heading || section.article_title }}</h3>

    <p class="card-summary">{{ section.summary }}</p>

    <div class="card-tags">
      <TagChip
        v-for="tag in section.topic_tags"
        :key="tag"
        :tag="tag"
        @downweight="emit('downweight', $event)"
      />
      <span
        v-for="flag in flags"
        :key="flag"
        class="card-flag"
      >{{ flag }}</span>
    </div>

    <div
      v-if="expanded && section.reasoning"
      class="card-reasoning"
    >
      <p class="reasoning-label">Reasoning</p>
      <p class="reasoning-text">{{ section.reasoning }}</p>
    </div>

    <div class="card-actions">
      <FeedbackPanel
        :section-id="section.id"
        @vote="(r: 1 | -1) => emit('vote', section.id, r)"
      />
      <button
        v-if="section.article_url"
        class="open-btn"
        aria-label="Open article"
        @click.stop="openArticle"
      >
        Open &rarr;
      </button>
    </div>
  </article>
</template>

<style scoped>
.section-card {
  border: 1px solid var(--pq-border);
  border-radius: calc(var(--pq-radius) * 1.5);
  padding: 1rem;
  background: var(--pq-bg);
  cursor: pointer;
  transition: border-color 0.15s;
  outline: none;
}

.section-card:hover {
  border-color: var(--pq-muted);
}

.section-card.focused {
  border-color: var(--pq-accent);
  box-shadow: 0 0 0 1px var(--pq-accent);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.375rem;
}

.card-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--pq-muted);
  min-width: 0;
}

.card-feed {
  font-weight: 600;
  flex-shrink: 0;
}

.card-article {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-heading {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0 0 0.375rem;
  line-height: 1.3;
}

.card-summary {
  font-size: 0.8125rem;
  color: var(--pq-muted);
  line-height: 1.5;
  margin: 0 0 0.5rem;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.card-flag {
  display: inline-block;
  padding: 0.0625rem 0.375rem;
  background: color-mix(in srgb, var(--pq-accent) 10%, transparent);
  border-radius: var(--pq-radius);
  font-size: 0.6875rem;
  color: var(--pq-accent);
}

.card-reasoning {
  margin: 0.5rem 0;
  padding: 0.75rem;
  background: var(--pq-card-bg);
  border-radius: var(--pq-radius);
}

.reasoning-label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  margin: 0 0 0.25rem;
}

.reasoning-text {
  font-size: 0.8125rem;
  color: var(--pq-text);
  line-height: 1.5;
  margin: 0;
}

.card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.open-btn {
  background: none;
  border: none;
  color: var(--pq-accent);
  font-size: 0.8125rem;
  cursor: pointer;
  padding: 0.25rem 0;
}

.open-btn:hover {
  text-decoration: underline;
}
</style>
