<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi, ApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useFeedback } from '@/composables/useFeedback'
import type { ArticleDetail } from '@/types/api'
import ConfidenceBadge from '@/components/sections/ConfidenceBadge.vue'
import TagChip from '@/components/sections/TagChip.vue'
import FeedbackPanel from '@/components/sections/FeedbackPanel.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const route = useRoute()
const router = useRouter()
const api = useApi()
const toast = useToast()
const feedback = useFeedback()

const article = ref<ArticleDetail | null>(null)
const loading = ref(false)
const processing = ref(false)

// Default threshold — article view doesn't have the triage context
const threshold = 0.7

async function loadArticle() {
  loading.value = true
  try {
    article.value = await api.get<ArticleDetail>(`/articles/${route.params.id}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      toast.error('Article not found')
      router.push('/')
    } else {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to load article')
    }
  } finally {
    loading.value = false
  }
}

async function processNow() {
  processing.value = true
  try {
    const result = await api.post<{ ok: boolean; result: string }>(`/articles/${route.params.id}/process`)
    if (result.ok) {
      toast.success('Processing complete')
      await loadArticle()
    } else {
      toast.info(`Result: ${result.result}`)
    }
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Processing failed')
  } finally {
    processing.value = false
  }
}

async function handleVote(sectionId: number, rating: 1 | -1) {
  await feedback.vote(sectionId, rating)
}

async function handleDownweight(tag: string) {
  await feedback.downweight(tag)
}

function openArticle() {
  if (article.value?.url) {
    window.open(article.value.url, '_blank', 'noopener')
  }
}

onMounted(loadArticle)
</script>

<template>
  <div class="article-view">
    <LoadingSpinner
      v-if="loading"
      message="Loading article..."
    />

    <template v-else-if="article">
      <div class="article-header">
        <button
          class="back-btn"
          @click="router.push('/')"
        >
          &larr; Triage
        </button>
        <h2 class="article-title">{{ article.title }}</h2>
        <div class="article-meta">
          <span>{{ article.feed_title }}</span>
          <span>{{ article.status }}</span>
          <span>{{ article.sections.length }} sections</span>
        </div>
        <div class="article-actions">
          <button
            v-if="article.url"
            class="action-btn"
            @click="openArticle"
          >
            Open original &rarr;
          </button>
          <button
            class="action-btn action-btn--primary"
            :disabled="processing"
            @click="processNow"
          >
            {{ processing ? 'Processing...' : 'Process now' }}
          </button>
        </div>
      </div>

      <div class="sections-list">
        <div
          v-for="section in article.sections"
          :key="section.id"
          class="section-block"
        >
          <div class="section-header">
            <h3 class="section-heading">{{ section.heading || 'Untitled section' }}</h3>
            <ConfidenceBadge
              :score="section.score"
              :threshold="threshold"
              :is-surprise="section.is_surprise"
            />
          </div>

          <p class="section-summary">{{ section.summary }}</p>

          <div
            v-if="section.topic_tags.length"
            class="section-tags"
          >
            <TagChip
              v-for="tag in section.topic_tags"
              :key="tag"
              :tag="tag"
              @downweight="handleDownweight"
            />
          </div>

          <div
            v-if="section.reasoning"
            class="section-reasoning"
          >
            <p class="reasoning-label">Reasoning</p>
            <p class="reasoning-text">{{ section.reasoning }}</p>
          </div>

          <div class="section-actions">
            <FeedbackPanel
              :section-id="section.id"
              @vote="(r: 1 | -1) => handleVote(section.id, r)"
            />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.article-view {
  max-width: 48rem;
  margin: 0 auto;
}

.article-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--pq-border);
}

.back-btn {
  background: none;
  border: none;
  color: var(--pq-accent);
  font-size: 0.8125rem;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.5rem;
}

.back-btn:hover {
  text-decoration: underline;
}

.article-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
  line-height: 1.3;
}

.article-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.8125rem;
  color: var(--pq-muted);
  margin-top: 0.375rem;
}

.article-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.action-btn {
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: none;
  color: var(--pq-text);
  font-size: 0.8125rem;
  cursor: pointer;
}

.action-btn:hover {
  border-color: var(--pq-muted);
}

.action-btn--primary {
  background: var(--pq-accent);
  color: #fff;
  border-color: var(--pq-accent);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.section-block {
  padding: 1rem 0;
  border-bottom: 1px solid var(--pq-border);
}

.section-block:last-child {
  border-bottom: none;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.375rem;
}

.section-heading {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
}

.section-summary {
  font-size: 0.875rem;
  color: var(--pq-text);
  line-height: 1.6;
  margin: 0 0 0.5rem;
}

.section-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.section-reasoning {
  padding: 0.75rem;
  background: var(--pq-card-bg);
  border-radius: var(--pq-radius);
  margin-bottom: 0.5rem;
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

.section-actions {
  margin-top: 0.5rem;
}
</style>
