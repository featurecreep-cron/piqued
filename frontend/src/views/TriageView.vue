<script setup lang="ts">
import { onMounted } from 'vue'
import { useContentStore } from '@/stores/content'
import DateNav from '@/components/sections/DateNav.vue'
import RiverLayout from '@/components/triage/RiverLayout.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const content = useContentStore()

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
  <div class="triage-view">
    <div class="triage-header">
      <h2 class="triage-title">Triage</h2>
      <DateNav
        v-if="content.date"
        :current="content.date"
        :available="content.datesAvailable"
        @select="handleDateSelect"
      />
    </div>

    <LoadingSpinner
      v-if="content.loading"
      message="Loading sections..."
    />

    <div
      v-else-if="content.error"
      class="triage-error"
    >
      <p>{{ content.error }}</p>
      <button @click="content.loadSections()">Retry</button>
    </div>

    <EmptyState
      v-else-if="!content.sections.length"
      message="No sections for this date."
    />

    <RiverLayout v-else />
  </div>
</template>

<style scoped>
.triage-view {
  max-width: 48rem;
  margin: 0 auto;
}

.triage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.triage-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--pq-text);
  margin: 0;
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
