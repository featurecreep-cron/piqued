<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useContentStore } from '@/stores/content'
import { useFeedback } from '@/composables/useFeedback'
import type { SectionItem } from '@/types/api'
import NavTree from './NavTree.vue'
import ArticleGroup from './ArticleGroup.vue'
import ArticleDetail from '@/components/sections/ArticleDetail.vue'

const content = useContentStore()
const feedback = useFeedback()

const activeFilter = ref<{ type: string; value: string }>({ type: 'triage', value: 'all' })
const selectedSectionId = ref<number | null>(null)
const navCollapsed = ref(false)

const filteredSections = computed<SectionItem[]>(() => {
  const f = activeFilter.value
  switch (f.type) {
    case 'triage':
      if (f.value === 'likely') return content.aboveSections
      if (f.value === 'discover') return content.surpriseSections
      if (f.value === 'below') return content.belowSections
      return content.sections
    case 'tag':
      return content.sections.filter((s) => s.topic_tags.includes(f.value))
    case 'feed':
      return content.sections.filter((s) => s.feed_title === f.value)
    default:
      return content.sections
  }
})

// Group sections by article
const articleGroups = computed(() => {
  const groups = new Map<number, { title: string; url: string | null; feed: string; sections: SectionItem[] }>()
  for (const section of filteredSections.value) {
    let group = groups.get(section.article_id)
    if (!group) {
      group = {
        title: section.article_title,
        url: section.article_url,
        feed: section.feed_title,
        sections: [],
      }
      groups.set(section.article_id, group)
    }
    group.sections.push(section)
  }
  return [...groups.values()]
})

const selectedSection = computed<SectionItem | null>(() => {
  if (!selectedSectionId.value) return null
  return content.sections.find((s) => s.id === selectedSectionId.value) ?? null
})

// Auto-select first section only on initial load, not on user filter changes
const initialized = ref(false)
watch(filteredSections, (sections) => {
  if (!initialized.value && sections.length) {
    selectedSectionId.value = sections[0].id
    initialized.value = true
  } else if (selectedSectionId.value && !sections.find((s) => s.id === selectedSectionId.value)) {
    // Current selection not in filtered list — clear it
    selectedSectionId.value = null
  }
}, { immediate: true })

function handleFilter(type: string, value: string) {
  activeFilter.value = { type, value }
}

function handleSelect(sectionId: number) {
  selectedSectionId.value = sectionId
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
  <div
    class="reader"
    :class="{ 'nav-collapsed': navCollapsed }"
  >
    <aside
      v-if="!navCollapsed"
      class="reader-nav"
    >
      <NavTree
        :active-filter="activeFilter"
        @filter="handleFilter"
      />
    </aside>

    <div class="reader-list">
      <div class="list-header">
        <button
          class="collapse-btn"
          :aria-label="navCollapsed ? 'Show navigation' : 'Hide navigation'"
          @click="navCollapsed = !navCollapsed"
        >
          {{ navCollapsed ? '&#9656;' : '&#9666;' }}
        </button>
        <span class="list-count">{{ filteredSections.length }} sections</span>
      </div>
      <div class="list-body">
        <ArticleGroup
          v-for="group in articleGroups"
          :key="group.title"
          :article-title="group.title"
          :article-url="group.url"
          :feed-title="group.feed"
          :sections="group.sections"
          :threshold="content.threshold"
          :surprise-ids="content.surpriseSectionIds"
          :selected-id="selectedSectionId"
          :focused-id="content.focusedSection?.id ?? null"
          @select="handleSelect"
        />
      </div>
    </div>

    <div class="reader-detail">
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
        class="detail-empty"
      >
        <p>Select a section to view details</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader {
  display: grid;
  grid-template-columns: 12rem 1fr 1fr;
  height: calc(100vh - 4rem);
  gap: 0;
}

.reader.nav-collapsed {
  grid-template-columns: 0 1fr 1fr;
}

.reader-nav {
  border-right: 1px solid var(--pq-border);
  overflow: hidden;
}

.reader-list {
  border-right: 1px solid var(--pq-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--pq-border);
  flex-shrink: 0;
}

.collapse-btn {
  background: none;
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  color: var(--pq-muted);
  padding: 0.125rem 0.375rem;
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1;
}

.collapse-btn:hover {
  color: var(--pq-text);
}

.list-count {
  font-size: 0.75rem;
  color: var(--pq-muted);
}

.list-body {
  flex: 1;
  overflow-y: auto;
}

.reader-detail {
  overflow: hidden;
}

.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--pq-muted);
  font-size: 0.875rem;
}
</style>
