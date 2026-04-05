<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi, ApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import type { FeedList, FeedItem, SyncResult } from '@/types/api'
import FeedCard from '@/components/feeds/FeedCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const api = useApi()
const toast = useToast()
const auth = useAuthStore()
const router = useRouter()

const feeds = ref<FeedItem[]>([])
const categories = ref<Record<string, number[]>>({})
const loading = ref(false)
const syncing = ref(false)
const error = ref<string | null>(null)

const grouped = computed(() => {
  const groups: Record<string, FeedItem[]> = {}
  for (const [cat, ids] of Object.entries(categories.value)) {
    groups[cat] = ids.map((id) => feeds.value.find((f) => f.id === id)).filter(Boolean) as FeedItem[]
  }
  return groups
})

async function loadFeeds() {
  loading.value = true
  error.value = null
  try {
    const data = await api.get<FeedList>('/feeds')
    feeds.value = data.feeds
    categories.value = data.categories
  } catch (err) {
    error.value = err instanceof ApiError ? err.detail : 'Failed to load feeds'
  } finally {
    loading.value = false
  }
}

async function toggleFeed(feedId: number) {
  try {
    const updated = await api.post<FeedItem>(`/feeds/${feedId}/toggle`)
    const idx = feeds.value.findIndex((f) => f.id === feedId)
    if (idx !== -1) feeds.value[idx] = updated
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Toggle failed')
  }
}

async function syncFeeds() {
  syncing.value = true
  try {
    const result = await api.post<SyncResult>('/feeds/sync')
    toast.success(`Synced: ${result.added} new of ${result.total} total`)
    if (result.added > 0) await loadFeeds()
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Sync failed')
  } finally {
    syncing.value = false
  }
}

function navigateToFeed(feedId: number) {
  router.push(`/feed/${feedId}`)
}

onMounted(loadFeeds)
</script>

<template>
  <div class="feeds-view">
    <div class="feeds-header">
      <h2 class="feeds-title">Feeds</h2>
      <div class="feeds-actions">
        <span class="feeds-count">{{ feeds.length }} feeds</span>
        <button
          v-if="auth.isAdmin"
          class="sync-btn"
          :disabled="syncing"
          @click="syncFeeds"
        >
          {{ syncing ? 'Syncing...' : 'Sync feeds' }}
        </button>
      </div>
    </div>

    <LoadingSpinner
      v-if="loading"
      message="Loading feeds..."
    />

    <div
      v-else-if="error"
      class="error-state"
      role="alert"
    >
      <p class="error-message">{{ error }}</p>
      <button
        class="sync-btn"
        @click="loadFeeds"
      >
        Retry
      </button>
    </div>

    <EmptyState
      v-else-if="!feeds.length"
      :message="auth.isAdmin ? 'No feeds configured. Use Sync to import from FreshRSS.' : 'No feeds configured. Contact your admin to import feeds.'"
    />

    <div
      v-else
      class="feeds-grid"
    >
      <div
        v-for="(catFeeds, category) in grouped"
        :key="category"
        class="feeds-category"
      >
        <h3 class="category-title">{{ category }}</h3>
        <div class="category-feeds">
          <FeedCard
            v-for="feed in catFeeds"
            :key="feed.id"
            :feed="feed"
            :is-admin="auth.isAdmin"
            @toggle="toggleFeed"
            @navigate="navigateToFeed"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.feeds-view {
  max-width: 56rem;
  margin: 0 auto;
}

.feeds-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.feeds-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
}

.feeds-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.feeds-count {
  font-size: 0.8125rem;
  color: var(--pq-muted);
}

.sync-btn {
  padding: 0.375rem 0.75rem;
  background: var(--pq-accent);
  color: #fff;
  border: none;
  border-radius: var(--pq-radius);
  font-size: 0.8125rem;
  cursor: pointer;
}

.sync-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.feeds-category {
  margin-bottom: 1.5rem;
}

.category-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  margin: 0 0 0.5rem;
  padding-bottom: 0.375rem;
  border-bottom: 1px solid var(--pq-border);
}

.category-feeds {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
  gap: 0.5rem;
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem 1rem;
  text-align: center;
}

.error-message {
  font-size: 0.875rem;
  color: var(--pq-danger);
  margin: 0;
}
</style>
