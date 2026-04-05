<script setup lang="ts">
import { onMounted } from 'vue'
import { useContentStore } from '@/stores/content'
import { useLayout } from '@/composables/useLayout'
import DateNav from '@/components/sections/DateNav.vue'
import RiverLayout from '@/components/triage/RiverLayout.vue'
import ReaderLayout from '@/components/triage/ReaderLayout.vue'
import ColumnsLayout from '@/components/triage/ColumnsLayout.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const content = useContentStore()
const layout = useLayout()

onMounted(() => {
  if (!content.sections.length) {
    content.loadSections()
  }
})

function handleDateSelect(date: string) {
  content.loadSections(date)
}
</script>

<template>
  <div
    class="triage-view"
    :class="{ 'triage-view--fullwidth': layout.isReader.value || layout.isColumns.value }"
  >
    <div class="triage-header">
      <h2 class="triage-title">Triage</h2>
      <div class="triage-controls">
        <div class="layout-toggle">
          <button
            class="layout-btn"
            :class="{ active: layout.isRiver.value }"
            :aria-pressed="layout.isRiver.value"
            @click="layout.setMode('river')"
          >
            River
          </button>
          <button
            class="layout-btn"
            :class="{ active: layout.isReader.value }"
            :aria-pressed="layout.isReader.value"
            @click="layout.setMode('reader')"
          >
            Reader
          </button>
          <button
            class="layout-btn"
            :class="{ active: layout.isColumns.value }"
            :aria-pressed="layout.isColumns.value"
            @click="layout.setMode('columns')"
          >
            Columns
          </button>
        </div>
        <DateNav
          v-if="content.date"
          :current="content.date"
          :available="content.datesAvailable"
          @select="handleDateSelect"
        />
      </div>
    </div>

    <LoadingSpinner
      v-if="content.loading"
      message="Loading sections..."
    />

    <div
      v-else-if="content.error"
      class="triage-error"
      role="alert"
    >
      <p>{{ content.error }}</p>
      <button @click="content.loadSections()">Retry</button>
    </div>

    <EmptyState
      v-else-if="!content.sections.length"
      message="No sections for this date."
    />

    <RiverLayout v-else-if="layout.isRiver.value" />
    <ReaderLayout v-else-if="layout.isReader.value" />
    <ColumnsLayout v-else-if="layout.isColumns.value" />
  </div>
</template>

<style scoped>
.triage-view {
  max-width: 48rem;
  margin: 0 auto;
}

.triage-view--fullwidth {
  max-width: none;
  margin: 0;
  padding: 0;
}

.triage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.triage-view--fullwidth .triage-header {
  padding: 0 0.75rem;
  margin-bottom: 0.5rem;
}

.triage-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
}

.triage-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.layout-toggle {
  display: flex;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  overflow: hidden;
}

.layout-btn {
  background: none;
  border: none;
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  color: var(--pq-muted);
  cursor: pointer;
}

.layout-btn:not(:last-child) {
  border-right: 1px solid var(--pq-border);
}

.layout-btn:hover {
  background: var(--pq-card-bg);
}

.layout-btn.active {
  background: color-mix(in srgb, var(--pq-accent) 12%, transparent);
  color: var(--pq-accent);
  font-weight: 500;
}

.triage-error {
  text-align: center;
  padding: 2rem;
  color: var(--pq-danger);
}

.triage-error button {
  margin-top: 0.5rem;
  padding: 0.375rem 1rem;
  background: var(--pq-accent);
  color: #fff;
  border: none;
  border-radius: var(--pq-radius);
  cursor: pointer;
  font-size: 0.8125rem;
}
</style>
