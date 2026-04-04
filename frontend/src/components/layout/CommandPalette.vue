<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useCommandPalette } from '@/composables/useCommandPalette'

const router = useRouter()
const palette = useCommandPalette(router)
const inputRef = ref<HTMLInputElement | null>(null)
const selectedIndex = ref(0)

// Focus input when palette opens
watch(
  () => palette.visible.value,
  async (vis) => {
    if (vis) {
      selectedIndex.value = 0
      await nextTick()
      inputRef.value?.focus()
    }
  },
)

// Reset selection when query changes
watch(
  () => palette.query.value,
  () => {
    selectedIndex.value = 0
  },
)

function handleKeydown(e: KeyboardEvent) {
  const items = palette.filtered.value

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = Math.min(selectedIndex.value + 1, items.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const item = items[selectedIndex.value]
    if (item) palette.execute(item)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    palette.close()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="palette.visible.value"
      class="palette-backdrop"
      @click="palette.close()"
    >
      <div
        class="palette-panel"
        @click.stop
        @keydown="handleKeydown"
      >
        <input
          ref="inputRef"
          v-model="palette.query.value"
          class="palette-input"
          type="text"
          placeholder="Type a command..."
          aria-label="Command palette"
        >
        <div class="palette-results">
          <div
            v-for="(cmd, idx) in palette.filtered.value"
            :key="cmd.id"
            class="palette-item"
            :class="{ selected: idx === selectedIndex }"
            @click="palette.execute(cmd)"
            @mouseenter="selectedIndex = idx"
          >
            <span class="palette-category">{{ cmd.category }}</span>
            <span class="palette-label">{{ cmd.label }}</span>
          </div>
          <div
            v-if="!palette.filtered.value.length"
            class="palette-empty"
          >
            No matching commands
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.palette-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 20vh;
  z-index: 9500;
}

.palette-panel {
  background: var(--pq-bg);
  border: 1px solid var(--pq-border);
  border-radius: calc(var(--pq-radius) * 2);
  width: 32rem;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}

.palette-input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: none;
  border-bottom: 1px solid var(--pq-border);
  background: var(--pq-bg);
  color: var(--pq-text);
  font-size: 0.9375rem;
  font-family: var(--pq-font-sans);
  outline: none;
}

.palette-input::placeholder {
  color: var(--pq-muted);
}

.palette-results {
  max-height: 20rem;
  overflow-y: auto;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  cursor: pointer;
}

.palette-item:hover,
.palette-item.selected {
  background: var(--pq-card-bg);
}

.palette-item.selected {
  background: color-mix(in srgb, var(--pq-accent) 10%, transparent);
}

.palette-category {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  min-width: 4rem;
}

.palette-label {
  font-size: 0.8125rem;
  color: var(--pq-text);
}

.palette-empty {
  padding: 1.5rem 1rem;
  text-align: center;
  font-size: 0.8125rem;
  color: var(--pq-muted);
}
</style>
