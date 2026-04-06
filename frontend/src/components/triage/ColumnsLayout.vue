<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useContentStore } from '@/stores/content'
import { useFeedback } from '@/composables/useFeedback'
import type { SectionItem } from '@/types/api'
import type { ColumnDef } from './ColumnConfig.vue'
import TriageColumn from './TriageColumn.vue'
import ColumnConfig from './ColumnConfig.vue'
import ArticleDetail from '@/components/sections/ArticleDetail.vue'

const content = useContentStore()
const feedback = useFeedback()

const STORAGE_KEY = 'pq-columns'

function loadColumns(): ColumnDef[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return JSON.parse(stored)
  } catch {
    // ignore
  }
  return [
    { type: 'tier', value: 'likely', label: 'Likely' },
    { type: 'tier', value: 'discover', label: 'Discover' },
  ]
}

function saveColumns(cols: ColumnDef[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cols))
}

const columns = ref<ColumnDef[]>(loadColumns())
const activeColumnIndex = ref(0)
const configVisible = ref(false)
const selectedSectionId = ref<number | null>(null)

function sectionsForColumn(col: ColumnDef): SectionItem[] {
  switch (col.type) {
    case 'tier':
      if (col.value === 'likely') return content.aboveSections
      if (col.value === 'discover') return content.surpriseSections
      return content.belowSections
    case 'tag':
      return content.sections.filter((s) => s.topic_tags.includes(col.value))
    case 'feed':
      return content.sections.filter((s) => s.feed_title === col.value)
    default:
      return []
  }
}

const selectedSection = computed<SectionItem | null>(() => {
  if (!selectedSectionId.value) return null
  return content.sections.find((s) => s.id === selectedSectionId.value) ?? null
})

function handleSelect(sectionId: number) {
  selectedSectionId.value = sectionId
}

function addColumn(col: ColumnDef) {
  if (columns.value.length >= 5) return
  columns.value.push(col)
  saveColumns(columns.value)
}

function removeColumn(index: number) {
  columns.value.splice(index, 1)
  if (activeColumnIndex.value >= columns.value.length) {
    activeColumnIndex.value = Math.max(0, columns.value.length - 1)
  }
  saveColumns(columns.value)
}

function moveColumn(payload: { index: number; direction: -1 | 1 }) {
  const { index, direction } = payload
  const target = index + direction
  if (target < 0 || target >= columns.value.length) return
  const [moved] = columns.value.splice(index, 1)
  columns.value.splice(target, 0, moved)
  if (activeColumnIndex.value === index) activeColumnIndex.value = target
  else if (activeColumnIndex.value === target) activeColumnIndex.value = index
  saveColumns(columns.value)
}

async function handleVote(sectionId: number, rating: 1 | -1) {
  await feedback.vote(sectionId, rating)
}

async function handleDownweight(tag: string) {
  await feedback.downweight(tag)
}

async function handleClickThrough(sectionId: number) {
  await feedback.clickThrough(sectionId)
}

function onSelectFocused(e: Event) {
  const sectionId = (e as CustomEvent).detail?.sectionId
  if (sectionId) handleSelect(sectionId)
}

onMounted(() => window.addEventListener('piqued:select-focused', onSelectFocused))
onUnmounted(() => window.removeEventListener('piqued:select-focused', onSelectFocused))
</script>

<template>
  <div class="columns-layout">
    <div class="columns-toolbar">
      <button
        class="config-btn"
        @click="configVisible = true"
      >
        Configure columns
      </button>
    </div>
    <div class="columns-container">
      <div class="columns-scroll">
        <TriageColumn
          v-for="(col, idx) in columns"
          :key="`${col.type}-${col.value}`"
          :title="col.label"
          :sections="sectionsForColumn(col)"
          :threshold="content.threshold"
          :surprise-ids="content.surpriseSectionIds"
          :focused-id="content.focusedSection?.id ?? null"
          :selected-id="selectedSectionId"
          :active="idx === activeColumnIndex"
          @select="handleSelect"
        />
        <div
          v-if="!columns.length"
          class="columns-empty"
        >
          <p>No columns configured.</p>
          <button @click="configVisible = true">Add columns</button>
        </div>
      </div>
      <div class="columns-detail">
        <ArticleDetail
          v-if="selectedSection"
          :section="selectedSection"
          :threshold="content.threshold"
          :is-surprise="content.surpriseSectionIds.includes(selectedSection.id)"
          @vote="handleVote"
          @downweight="handleDownweight"
          @click-through="handleClickThrough"
        />
        <div
          v-else
          class="columns-placeholder"
        >
          <p>Select a section to read</p>
        </div>
      </div>
    </div>
    <ColumnConfig
      v-if="configVisible"
      :columns="columns"
      @add="addColumn"
      @remove="removeColumn"
      @move="moveColumn"
      @close="configVisible = false"
    />
  </div>
</template>

<style scoped>
.columns-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 4rem);
}

.columns-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 0.375rem 0.75rem;
  border-bottom: 1px solid var(--pq-border);
  flex-shrink: 0;
}

.config-btn {
  background: none;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  color: var(--pq-muted);
  font-size: 0.75rem;
  padding: 0.25rem 0.625rem;
  cursor: pointer;
}

.config-btn:hover {
  color: var(--pq-text);
  border-color: var(--pq-muted);
}

.columns-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.columns-scroll {
  display: flex;
  flex: 1;
  overflow-x: auto;
}

.columns-detail {
  width: 22rem;
  flex-shrink: 0;
  border-left: 1px solid var(--pq-border);
  overflow: hidden;
}

.columns-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--pq-muted);
  font-size: 0.875rem;
}

.columns-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--pq-muted);
  font-size: 0.875rem;
  gap: 0.5rem;
}

.columns-empty button {
  background: var(--pq-accent);
  color: #fff;
  border: none;
  border-radius: var(--pq-radius);
  padding: 0.375rem 1rem;
  font-size: 0.8125rem;
  cursor: pointer;
}
</style>
