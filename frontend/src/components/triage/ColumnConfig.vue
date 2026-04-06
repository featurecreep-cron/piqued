<script setup lang="ts">
import { ref, computed } from 'vue'
import { useContentStore } from '@/stores/content'
import { useFocusTrap } from '@/composables/useFocusTrap'
import { humanizeTag } from '@/utils/tags'

export interface ColumnDef {
  type: 'tier' | 'tag' | 'feed'
  value: string
  label: string
}

const props = defineProps<{
  columns: ColumnDef[]
}>()

const emit = defineEmits<{
  add: [col: ColumnDef]
  remove: [index: number]
  move: [payload: { index: number; direction: -1 | 1 }]
  close: []
}>()

const panelRef = ref<HTMLElement | null>(null)
useFocusTrap(panelRef, () => emit('close'))
const content = useContentStore()

const availableTags = computed(() => {
  const tags = new Set<string>()
  for (const s of content.sections) {
    for (const t of s.topic_tags) tags.add(t)
  }
  const active = new Set(props.columns.filter((c) => c.type === 'tag').map((c) => c.value))
  return [...tags].filter((t) => !active.has(t)).sort()
})

const availableFeeds = computed(() => {
  const feeds = new Set<string>()
  for (const s of content.sections) feeds.add(s.feed_title)
  const active = new Set(props.columns.filter((c) => c.type === 'feed').map((c) => c.value))
  return [...feeds].filter((f) => !active.has(f)).sort()
})

const availableTiers = computed(() => {
  const tiers: ColumnDef[] = [
    { type: 'tier', value: 'likely', label: 'Likely' },
    { type: 'tier', value: 'discover', label: 'Discover' },
    { type: 'tier', value: 'below', label: 'Below threshold' },
  ]
  const active = new Set(props.columns.filter((c) => c.type === 'tier').map((c) => c.value))
  return tiers.filter((t) => !active.has(t.value))
})
</script>

<template>
  <Teleport to="body">
    <div
      class="config-backdrop"
      role="presentation"
      @click="emit('close')"
    >
      <div
        ref="panelRef"
        class="config-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="column-config-title"
        @click.stop
      >
        <div class="config-header">
          <h3
            id="column-config-title"
            class="config-title"
          >
            Configure columns
          </h3>
          <button
            class="config-close"
            aria-label="Close"
            @click="emit('close')"
          >
            &times;
          </button>
        </div>

        <div class="config-current">
          <h4 class="config-section-title">Active columns</h4>
          <div
            v-for="(col, idx) in columns"
            :key="`${col.type}-${col.value}`"
            class="config-item"
          >
            <span class="config-label">{{ col.label }}</span>
            <div class="config-item-actions">
              <button
                class="config-move"
                :aria-label="`Move ${col.label} left`"
                :disabled="idx === 0"
                @click="emit('move', { index: idx, direction: -1 })"
              >
                &uarr;
              </button>
              <button
                class="config-move"
                :aria-label="`Move ${col.label} right`"
                :disabled="idx === columns.length - 1"
                @click="emit('move', { index: idx, direction: 1 })"
              >
                &darr;
              </button>
              <button
                class="config-remove"
                :aria-label="`Remove ${col.label} column`"
                @click="emit('remove', idx)"
              >
                &times;
              </button>
            </div>
          </div>
          <p
            v-if="!columns.length"
            class="config-empty"
          >
            No columns configured.
          </p>
        </div>

        <div
          v-if="availableTiers.length"
          class="config-add-group"
        >
          <h4 class="config-section-title">Tiers</h4>
          <button
            v-for="tier in availableTiers"
            :key="tier.value"
            class="config-add-btn"
            @click="emit('add', tier)"
          >
            + {{ tier.label }}
          </button>
        </div>

        <div
          v-if="availableTags.length"
          class="config-add-group"
        >
          <h4 class="config-section-title">Topics</h4>
          <button
            v-for="tag in availableTags"
            :key="tag"
            class="config-add-btn"
            @click="emit('add', { type: 'tag', value: tag, label: humanizeTag(tag) })"
          >
            + {{ humanizeTag(tag) }}
          </button>
        </div>

        <div
          v-if="availableFeeds.length"
          class="config-add-group"
        >
          <h4 class="config-section-title">Feeds</h4>
          <button
            v-for="feed in availableFeeds"
            :key="feed"
            class="config-add-btn"
            @click="emit('add', { type: 'feed', value: feed, label: feed })"
          >
            + {{ feed }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.config-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
}

.config-panel {
  background: var(--pq-bg);
  border: 1px solid var(--pq-border);
  border-radius: calc(var(--pq-radius) * 2);
  padding: 1.25rem;
  min-width: 18rem;
  max-width: 24rem;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.config-title {
  font-size: 0.9375rem;
  font-weight: 600;
  margin: 0;
  color: var(--pq-text);
}

.config-close {
  background: none;
  border: none;
  color: var(--pq-muted);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.config-section-title {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  margin: 0.5rem 0 0.25rem;
}

.config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.375rem 0;
  border-bottom: 1px solid var(--pq-border);
}

.config-label {
  font-size: 0.8125rem;
  color: var(--pq-text);
}

.config-item-actions {
  display: flex;
  align-items: center;
  gap: 0.125rem;
}

.config-move {
  background: none;
  border: none;
  color: var(--pq-muted);
  cursor: pointer;
  font-size: 0.875rem;
  padding: 0 0.25rem;
  line-height: 1;
}

.config-move:hover:not(:disabled) {
  color: var(--pq-text);
}

.config-move:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.config-remove {
  background: none;
  border: none;
  color: var(--pq-muted);
  cursor: pointer;
  font-size: 1rem;
  padding: 0 0.25rem;
}

.config-remove:hover {
  color: var(--pq-danger);
}

.config-empty {
  font-size: 0.8125rem;
  color: var(--pq-muted);
  padding: 0.5rem 0;
  margin: 0;
}

.config-add-group {
  margin-top: 0.5rem;
}

.config-add-btn {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  padding: 0.25rem 0;
  font-size: 0.8125rem;
  color: var(--pq-accent);
  cursor: pointer;
}

.config-add-btn:hover {
  text-decoration: underline;
}
</style>
