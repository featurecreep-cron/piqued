<script setup lang="ts">
import { ref, computed } from 'vue'
import type { SectionItem } from '@/types/api'
import SectionCardCompact from '@/components/sections/SectionCardCompact.vue'

const props = defineProps<{
  articleTitle: string
  articleUrl: string | null
  feedTitle: string
  sections: SectionItem[]
  threshold: number
  surpriseIds: number[]
  selectedId: number | null
  focusedId: number | null
}>()

const emit = defineEmits<{
  select: [sectionId: number]
}>()

const collapsed = ref(false)
const isMulti = computed(() => props.sections.length > 1)
const sectionCount = computed(() => `${props.sections.length}`)
</script>

<template>
  <div class="article-group">
    <div
      class="group-header"
      :class="{ collapsible: isMulti }"
      @click="isMulti && (collapsed = !collapsed)"
    >
      <span
        v-if="isMulti"
        class="group-caret"
      >{{ collapsed ? '&#9656;' : '&#9662;' }}</span>
      <div class="group-title-area">
        <span class="group-title">{{ articleTitle }}</span>
        <span class="group-meta">
          {{ feedTitle }}
          <span v-if="isMulti"> &middot; {{ sectionCount }} sections</span>
        </span>
      </div>
    </div>
    <div
      v-if="!collapsed"
      class="group-sections"
    >
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
    </div>
  </div>
</template>

<style scoped>
.article-group {
  border-bottom: 1px solid var(--pq-border);
}

.group-header {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
  padding: 0.5rem 0.75rem;
}

.group-header.collapsible {
  cursor: pointer;
}

.group-header.collapsible:hover {
  background: var(--pq-card-bg);
}

.group-caret {
  font-size: 0.6875rem;
  color: var(--pq-muted);
  line-height: 1.4;
  flex-shrink: 0;
  width: 0.75rem;
}

.group-title-area {
  flex: 1;
  min-width: 0;
}

.group-title {
  display: block;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--pq-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-meta {
  display: block;
  font-size: 0.6875rem;
  color: var(--pq-muted);
}
</style>
