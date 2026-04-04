<script setup lang="ts">
import { computed } from 'vue'
import type { SectionItem } from '@/types/api'
import ConfidenceBadge from './ConfidenceBadge.vue'
import TagChip from './TagChip.vue'
import FeedbackPanel from './FeedbackPanel.vue'

const props = defineProps<{
  section: SectionItem
  threshold: number
  isSurprise: boolean
}>()

const emit = defineEmits<{
  vote: [sectionId: number, rating: 1 | -1]
  downweight: [tag: string]
  clickThrough: [sectionId: number]
}>()

const flags = computed(() => {
  const f: string[] = []
  if (props.section.has_humor) f.push('humor')
  if (props.section.has_surprise_data) f.push('surprise data')
  if (props.section.has_actionable_advice) f.push('actionable')
  return f
})

function openArticle() {
  if (props.section.article_url) {
    window.open(props.section.article_url, '_blank', 'noopener')
    emit('clickThrough', props.section.id)
  }
}
</script>

<template>
  <div class="article-detail">
    <div class="detail-header">
      <div class="detail-meta">
        <span class="detail-feed">{{ section.feed_title }}</span>
        <ConfidenceBadge
          :score="section.score"
          :threshold="threshold"
          :is-surprise="isSurprise"
        />
      </div>
      <h2 class="detail-article-title">{{ section.article_title }}</h2>
      <h3
        v-if="section.heading && section.heading !== section.article_title"
        class="detail-heading"
      >
        {{ section.heading }}
      </h3>
    </div>

    <div class="detail-body">
      <p class="detail-summary">{{ section.summary }}</p>

      <div
        v-if="section.topic_tags.length || flags.length"
        class="detail-tags"
      >
        <TagChip
          v-for="tag in section.topic_tags"
          :key="tag"
          :tag="tag"
          @downweight="emit('downweight', $event)"
        />
        <span
          v-for="flag in flags"
          :key="flag"
          class="detail-flag"
        >{{ flag }}</span>
      </div>

      <div
        v-if="section.reasoning"
        class="detail-reasoning"
      >
        <p class="reasoning-label">Reasoning</p>
        <p class="reasoning-text">{{ section.reasoning }}</p>
      </div>
    </div>

    <div class="detail-actions">
      <FeedbackPanel
        :section-id="section.id"
        @vote="(r: 1 | -1) => emit('vote', section.id, r)"
      />
      <button
        v-if="section.article_url"
        class="open-btn"
        @click="openArticle"
      >
        Open article &rarr;
      </button>
    </div>
  </div>
</template>

<style scoped>
.article-detail {
  padding: 1.25rem;
  height: 100%;
  overflow-y: auto;
}

.detail-header {
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--pq-border);
}

.detail-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.detail-feed {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--pq-muted);
}

.detail-article-title {
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
  line-height: 1.3;
}

.detail-heading {
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--pq-muted);
  margin: 0.25rem 0 0;
}

.detail-body {
  margin-bottom: 1rem;
}

.detail-summary {
  font-size: 0.875rem;
  color: var(--pq-text);
  line-height: 1.6;
  margin: 0 0 0.75rem;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.75rem;
}

.detail-flag {
  display: inline-block;
  padding: 0.0625rem 0.375rem;
  background: color-mix(in srgb, var(--pq-accent) 10%, transparent);
  border-radius: var(--pq-radius);
  font-size: 0.6875rem;
  color: var(--pq-accent);
}

.detail-reasoning {
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

.detail-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.75rem;
  border-top: 1px solid var(--pq-border);
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
