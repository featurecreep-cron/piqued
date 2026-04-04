<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi, ApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { ProcessingLogList, ProcessingLogEntry } from '@/types/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const api = useApi()
const toast = useToast()

const entries = ref<ProcessingLogEntry[]>([])
const loading = ref(false)
const total = ref(0)
const limit = 50
const offset = ref(0)

const hasMore = () => offset.value + limit < total.value

async function loadLog(append = false) {
  loading.value = true
  try {
    const data = await api.get<ProcessingLogList>('/log', {
      limit,
      offset: offset.value,
    })
    if (append) {
      entries.value.push(...data.entries)
    } else {
      entries.value = data.entries
    }
    total.value = data.total
  } catch (err) {
    toast.error(err instanceof ApiError ? err.detail : 'Failed to load log')
  } finally {
    loading.value = false
  }
}

function loadMore() {
  offset.value += limit
  loadLog(true)
}

function statusClass(status: string): string {
  switch (status) {
    case 'ok':
    case 'success':
      return 'status--ok'
    case 'error':
    case 'failed':
      return 'status--error'
    case 'skipped':
      return 'status--skipped'
    default:
      return ''
  }
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`

  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`

  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function navigateToArticle(articleId: number | null) {
  if (articleId) router.push(`/article/${articleId}`)
}

onMounted(() => loadLog())
</script>

<template>
  <div class="log-view">
    <div class="log-header">
      <h2 class="log-title">Processing Log</h2>
      <span class="log-count">{{ total }} entries</span>
    </div>

    <LoadingSpinner
      v-if="loading && !entries.length"
      message="Loading log..."
    />

    <div
      v-else
      class="log-table-wrap"
    >
      <table class="log-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Stage</th>
            <th>Status</th>
            <th>Article</th>
            <th>Detail</th>
            <th class="col-num">Tokens</th>
            <th class="col-num">Duration</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.id"
          >
            <td class="cell-time">{{ formatTime(entry.created_at) }}</td>
            <td class="cell-stage">{{ entry.stage }}</td>
            <td>
              <span
                class="status-badge"
                :class="statusClass(entry.status)"
              >{{ entry.status }}</span>
            </td>
            <td class="cell-article">
              <button
                v-if="entry.article_id"
                class="article-link"
                @click="navigateToArticle(entry.article_id)"
              >
                {{ entry.article_title || `#${entry.article_id}` }}
              </button>
              <span
                v-else
                class="cell-muted"
              >&mdash;</span>
            </td>
            <td class="cell-detail">{{ entry.detail || '' }}</td>
            <td class="col-num">{{ entry.tokens_used ?? '' }}</td>
            <td class="col-num">{{ entry.duration_ms != null ? `${entry.duration_ms}ms` : '' }}</td>
          </tr>
        </tbody>
      </table>

      <p
        v-if="!entries.length"
        class="empty-text"
      >
        No log entries.
      </p>

      <div
        v-if="hasMore()"
        class="load-more"
      >
        <button
          class="btn"
          :disabled="loading"
          @click="loadMore"
        >
          {{ loading ? 'Loading...' : 'Load more' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-view {
  max-width: 56rem;
  margin: 0 auto;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.log-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
}

.log-count {
  font-size: 0.8125rem;
  color: var(--pq-muted);
}

.log-table-wrap {
  overflow-x: auto;
}

.log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.log-table th {
  text-align: left;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  padding: 0.5rem 0.5rem;
  border-bottom: 1px solid var(--pq-border);
}

.log-table td {
  padding: 0.375rem 0.5rem;
  border-bottom: 1px solid var(--pq-border);
  color: var(--pq-text);
  vertical-align: top;
}

.col-num {
  text-align: right;
}

.cell-time {
  white-space: nowrap;
  color: var(--pq-muted);
  font-size: 0.75rem;
}

.cell-stage {
  font-family: var(--pq-font-mono);
  font-size: 0.75rem;
}

.cell-detail {
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
  color: var(--pq-muted);
}

.cell-muted {
  color: var(--pq-muted);
}

.cell-article {
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  border-radius: var(--pq-radius);
  font-size: 0.6875rem;
  font-weight: 500;
}

.status--ok {
  color: var(--pq-success);
  background: color-mix(in srgb, var(--pq-success) 10%, transparent);
}

.status--error {
  color: var(--pq-danger);
  background: color-mix(in srgb, var(--pq-danger) 10%, transparent);
}

.status--skipped {
  color: var(--pq-muted);
  background: color-mix(in srgb, var(--pq-muted) 10%, transparent);
}

.article-link {
  background: none;
  border: none;
  color: var(--pq-accent);
  font-size: 0.8125rem;
  cursor: pointer;
  padding: 0;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  display: block;
}

.article-link:hover {
  text-decoration: underline;
}

.empty-text {
  font-size: 0.8125rem;
  color: var(--pq-muted);
  padding: 1rem 0;
  text-align: center;
}

.load-more {
  text-align: center;
  padding: 1rem 0;
}

.btn {
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: none;
  color: var(--pq-text);
  font-size: 0.8125rem;
  cursor: pointer;
}

.btn:hover {
  border-color: var(--pq-muted);
}

.btn:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
