<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useFeedback } from '@/composables/useFeedback'
import type { SectionItem, FeedItem, FeedList } from '@/types/api'
import type { BootstrapStatusResponse, BootstrapIngestResult, BootstrapCompleteResult } from '@/types/api'
import SectionCard from '@/components/sections/SectionCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const api = useApi()
const router = useRouter()
const feedback = useFeedback()

type Step = 'loading' | 'pick-feeds' | 'ingesting' | 'react' | 'scoring' | 'done'

const step = ref<Step>('loading')
const error = ref('')
const feeds = ref<FeedItem[]>([])
const selectedFeedIds = ref<number[]>([])
const samples = ref<SectionItem[]>([])
const reactions = ref<Record<number, 1 | -1>>({})
const reactionReasons = ref<Record<number, string>>({})

const selectedCount = computed(() => selectedFeedIds.value.length)
const canPickFeeds = computed(() => selectedCount.value >= 3 && selectedCount.value <= 5)
const reactedCount = computed(() => Object.keys(reactions.value).length)
const canComplete = computed(() => reactedCount.value >= 3)

onMounted(async () => {
  try {
    const status = await api.get<BootstrapStatusResponse>('/bootstrap/status')
    if (status.bootstrap_complete) {
      router.replace('/')
      return
    }

    // If content already exists (e.g. pipeline already ran), skip to sampling
    if (status.has_sections) {
      await loadSamples()
      return
    }

    // Load feeds for calibration selection
    const feedData = await api.get<FeedList>('/feeds')
    feeds.value = feedData.feeds.filter(f => f.active)

    if (feeds.value.length === 0) {
      // No active feeds — shouldn't happen if onboarding redirected here
      router.replace('/onboarding')
      return
    }

    step.value = 'pick-feeds'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load'
    step.value = 'pick-feeds'
  }
})

function toggleFeed(feedId: number) {
  const idx = selectedFeedIds.value.indexOf(feedId)
  if (idx >= 0) {
    selectedFeedIds.value.splice(idx, 1)
  } else {
    selectedFeedIds.value.push(feedId)
  }
}

async function startIngest() {
  step.value = 'ingesting'
  error.value = ''
  try {
    const result = await api.post<BootstrapIngestResult>('/bootstrap/ingest', {
      feed_ids: selectedFeedIds.value,
    })
    if (result.section_count === 0) {
      error.value = 'No content found in those feeds. Try selecting different ones.'
      step.value = 'pick-feeds'
      return
    }
    await loadSamples()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Ingestion failed'
    step.value = 'pick-feeds'
  }
}

async function loadSamples() {
  try {
    samples.value = await api.get<SectionItem[]>('/bootstrap/sample')
    if (samples.value.length === 0) {
      error.value = 'No content available to sample. The pipeline may need to run first.'
      step.value = 'pick-feeds'
      return
    }
    step.value = 'react'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load samples'
    step.value = 'pick-feeds'
  }
}

async function handleVote(sectionId: number, rating: 1 | -1) {
  reactions.value[sectionId] = rating
  const reason = reactionReasons.value[sectionId] || undefined
  await feedback.vote(sectionId, rating)
  if (reason) {
    // Submit with reason via direct API call
    await api.post('/feedback', {
      section_id: sectionId,
      rating,
      reason,
    })
  }
}

async function completeBootstrap() {
  step.value = 'scoring'
  error.value = ''
  try {
    await api.post<BootstrapCompleteResult>('/bootstrap/complete')
    step.value = 'done'
    // Brief pause so user sees success state
    setTimeout(() => router.replace('/'), 1500)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Scoring failed'
    step.value = 'react'
  }
}
</script>

<template>
  <div class="bootstrap-view">
    <div class="bootstrap-container">
      <header class="bootstrap-header">
        <h1 class="bootstrap-title">Get Started</h1>
        <p class="bootstrap-subtitle">
          Let's figure out what you care about. This takes about a minute.
        </p>
      </header>

      <!-- Step indicator -->
      <div class="step-indicator">
        <div
          class="step-dot"
          :class="{ active: step === 'pick-feeds' || step === 'ingesting' }"
        />
        <div class="step-line" />
        <div
          class="step-dot"
          :class="{ active: step === 'react' }"
        />
        <div class="step-line" />
        <div
          class="step-dot"
          :class="{ active: step === 'scoring' || step === 'done' }"
        />
      </div>

      <!-- Loading -->
      <LoadingSpinner
        v-if="step === 'loading'"
        message="Checking your setup..."
      />

      <!-- Step 1: Pick calibration feeds -->
      <div
        v-if="step === 'pick-feeds'"
        class="step-content"
      >
        <h2 class="step-title">Pick 3-5 feeds for calibration</h2>
        <p class="step-description">
          Which feeds do you have the strongest opinions about?
          Those help us learn fastest.
        </p>

        <div
          v-if="error"
          class="error-banner"
        >
          {{ error }}
        </div>

        <div class="feed-grid">
          <button
            v-for="feed in feeds"
            :key="feed.id"
            class="feed-chip"
            :class="{ selected: selectedFeedIds.includes(feed.id) }"
            @click="toggleFeed(feed.id)"
          >
            <span class="feed-chip-title">{{ feed.title }}</span>
            <span class="feed-chip-category">{{ feed.category }}</span>
          </button>
        </div>

        <div class="step-actions">
          <span class="selection-count">{{ selectedCount }} selected</span>
          <button
            class="btn-primary"
            :disabled="!canPickFeeds"
            @click="startIngest"
          >
            Analyze these feeds
          </button>
        </div>
      </div>

      <!-- Step 1b: Ingesting -->
      <LoadingSpinner
        v-if="step === 'ingesting'"
        message="Analyzing your feeds..."
      />

      <!-- Step 2: React to samples -->
      <div
        v-if="step === 'react'"
        class="step-content"
      >
        <h2 class="step-title">What do you think?</h2>
        <p class="step-description">
          Vote on these sections so we can build your interest profile.
          {{ reactedCount }}/{{ samples.length }} rated
          <template v-if="reactedCount < 3">
            ({{ 3 - reactedCount }} more needed)
          </template>
        </p>

        <div class="sample-cards">
          <div
            v-for="section in samples"
            :key="section.id"
            class="sample-card-wrapper"
          >
            <SectionCard
              :section="section"
              :threshold="0.5"
              :is-surprise="false"
              :focused="false"
              @vote="handleVote"
            />
            <div class="reason-row">
              <input
                v-model="reactionReasons[section.id]"
                class="reason-input"
                type="text"
                placeholder="Why? (optional)"
                @click.stop
              >
              <span
                v-if="reactions[section.id]"
                class="voted-indicator"
                :class="reactions[section.id] === 1 ? 'voted-up' : 'voted-down'"
              >
                {{ reactions[section.id] === 1 ? 'Liked' : 'Disliked' }}
              </span>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <button
            class="btn-primary"
            :disabled="!canComplete"
            @click="completeBootstrap"
          >
            Build my profile
          </button>
        </div>
      </div>

      <!-- Step 3: Scoring -->
      <LoadingSpinner
        v-if="step === 'scoring'"
        message="Building your profile..."
      />

      <!-- Done -->
      <div
        v-if="step === 'done'"
        class="step-content done-state"
      >
        <h2 class="step-title">You're all set</h2>
        <p class="step-description">Redirecting to your triage view...</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bootstrap-view {
  max-width: 42rem;
  margin: 0 auto;
  padding: 2rem 1rem;
}

.bootstrap-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.bootstrap-header {
  text-align: center;
}

.bootstrap-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--pq-text);
  margin: 0 0 0.5rem;
}

.bootstrap-subtitle {
  font-size: 0.875rem;
  color: var(--pq-muted);
  margin: 0;
}

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
}

.step-dot {
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 50%;
  background: var(--pq-border);
  transition: background 0.2s;
}

.step-dot.active {
  background: var(--pq-accent);
}

.step-line {
  width: 3rem;
  height: 2px;
  background: var(--pq-border);
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.step-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
}

.step-description {
  font-size: 0.8125rem;
  color: var(--pq-muted);
  margin: 0;
  line-height: 1.5;
}

.error-banner {
  padding: 0.75rem 1rem;
  background: color-mix(in srgb, var(--pq-danger) 10%, transparent);
  border: 1px solid var(--pq-danger);
  border-radius: var(--pq-radius);
  color: var(--pq-danger);
  font-size: 0.8125rem;
}

.feed-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.feed-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.125rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--pq-border);
  border-radius: calc(var(--pq-radius) * 1.5);
  background: var(--pq-bg);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.feed-chip:hover {
  border-color: var(--pq-muted);
}

.feed-chip.selected {
  border-color: var(--pq-accent);
  background: color-mix(in srgb, var(--pq-accent) 8%, var(--pq-bg));
}

.feed-chip-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--pq-text);
}

.feed-chip-category {
  font-size: 0.6875rem;
  color: var(--pq-muted);
}

.step-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 1rem;
  padding-top: 0.5rem;
}

.selection-count {
  font-size: 0.8125rem;
  color: var(--pq-muted);
}

.btn-primary {
  padding: 0.5rem 1.25rem;
  border: none;
  border-radius: var(--pq-radius);
  background: var(--pq-accent);
  color: #fff;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary:not(:disabled):hover {
  opacity: 0.9;
}

.sample-cards {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.sample-card-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.reason-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.25rem;
}

.reason-input {
  flex: 1;
  padding: 0.375rem 0.5rem;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  background: var(--pq-bg);
  color: var(--pq-text);
  font-size: 0.75rem;
}

.reason-input::placeholder {
  color: var(--pq-muted);
}

.voted-indicator {
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.voted-up {
  color: var(--pq-success);
}

.voted-down {
  color: var(--pq-danger);
}

.done-state {
  text-align: center;
  padding: 2rem 0;
}
</style>
