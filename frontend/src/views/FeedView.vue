<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi, ApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { FeedDetail } from '@/types/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const api = useApi()
const toast = useToast()

const feed = ref<FeedDetail | null>(null)
const loading = ref(false)

async function loadFeed() {
  loading.value = true
  try {
    feed.value = await api.get<FeedDetail>(`/feeds/${route.params.id}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      toast.error('Feed not found')
      router.push('/feeds')
    } else {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to load feed')
    }
  } finally {
    loading.value = false
  }
}

function navigateToArticle(articleId: number) {
  router.push(`/article/${articleId}`)
}

function statusColor(status: string): string {
  switch (status) {
    case 'complete':
      return 'var(--pq-success)'
    case 'pending':
      return 'var(--pq-warning)'
    case 'failed':
      return 'var(--pq-danger)'
    default:
      return 'var(--pq-muted)'
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

onMounted(loadFeed)
</script>

<template>
  <div class="feed-view">
    <LoadingSpinner
      v-if="loading"
      message="Loading feed..."
    />

    <template v-else-if="feed">
      <div class="feed-header">
        <button
          class="back-btn"
          aria-label="Back to feeds"
          @click="router.push('/feeds')"
        >
          &larr; Feeds
        </button>
        <div class="feed-info">
          <h2 class="feed-title">{{ feed.feed.title }}</h2>
          <div class="feed-meta">
            <span>{{ feed.feed.category }}</span>
            <span>{{ feed.feed.content_quality }} quality</span>
            <span :style="{ color: feed.feed.active ? 'var(--pq-success)' : 'var(--pq-muted)' }">
              {{ feed.feed.active ? 'Active' : 'Inactive' }}
            </span>
          </div>
        </div>
      </div>

      <EmptyState
        v-if="!feed.articles.length"
        message="No articles from this feed."
      />

      <div
        v-else
        class="articles-list"
      >
        <div
          v-for="article in feed.articles"
          :key="article.id"
          class="article-row"
          @click="navigateToArticle(article.id)"
        >
          <div class="article-main">
            <span class="article-title">{{ article.title }}</span>
            <span class="article-date">{{ formatDate(article.published_at) }}</span>
          </div>
          <div class="article-info">
            <span
              class="article-status"
              :style="{ color: statusColor(article.status) }"
            >{{ article.status }}</span>
            <span class="article-sections">{{ article.section_count }} sections</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.feed-view {
  max-width: 48rem;
  margin: 0 auto;
}

.feed-header {
  margin-bottom: 1.25rem;
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

.feed-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
}

.feed-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.8125rem;
  color: var(--pq-muted);
  margin-top: 0.25rem;
}

.article-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--pq-border);
  cursor: pointer;
}

.article-row:hover .article-title {
  color: var(--pq-accent);
}

.article-main {
  flex: 1;
  min-width: 0;
}

.article-title {
  display: block;
  font-size: 0.875rem;
  color: var(--pq-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.article-date {
  display: block;
  font-size: 0.75rem;
  color: var(--pq-muted);
}

.article-info {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  flex-shrink: 0;
  margin-left: 1rem;
}

.article-sections {
  color: var(--pq-muted);
}
</style>
