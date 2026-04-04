<script setup lang="ts">
import type { SectionItem } from '@/types/api'
import SectionCardCompact from '@/components/sections/SectionCardCompact.vue'

defineProps<{
  title: string
  sections: SectionItem[]
  threshold: number
  surpriseIds: number[]
  focusedId: number | null
  selectedId: number | null
  active: boolean
}>()

const emit = defineEmits<{
  select: [sectionId: number]
}>()
</script>

<template>
  <div
    class="column"
    :class="{ active }"
  >
    <div class="column-header">
      <span class="column-title">{{ title }}</span>
      <span class="column-count">{{ sections.length }}</span>
    </div>
    <div class="column-body">
      <SectionCardCompact
        v-for="section in sections"
        :key="section.id"
        :section="section"
        :threshold="threshold"
        :is-surprise="surpriseIds.includes(section.id)"
        :focused="focusedId === section.id"
        :selected="selectedId === section.id"
        @select="emit('select', $event)"
      />
      <div
        v-if="!sections.length"
        class="column-empty"
      >
        No sections
      </div>
    </div>
  </div>
</template>

<style scoped>
.column {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--pq-border);
  min-width: 14rem;
  max-width: 20rem;
  flex: 1;
}

.column:last-child {
  border-right: none;
}

.column.active {
  box-shadow: inset 0 2px 0 var(--pq-accent);
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--pq-border);
  flex-shrink: 0;
}

.column-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-text);
}

.column-count {
  font-size: 0.6875rem;
  color: var(--pq-muted);
}

.column-body {
  flex: 1;
  overflow-y: auto;
}

.column-empty {
  padding: 1.5rem 0.75rem;
  text-align: center;
  font-size: 0.8125rem;
  color: var(--pq-muted);
}
</style>
