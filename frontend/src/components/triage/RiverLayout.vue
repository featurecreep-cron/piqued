<script setup lang="ts">
import { useContentStore } from '@/stores/content'
import { useFeedback } from '@/composables/useFeedback'
import SectionCard from '@/components/sections/SectionCard.vue'

const content = useContentStore()
const feedback = useFeedback()

async function handleVote(sectionId: number, rating: 1 | -1) {
  await feedback.vote(sectionId, rating)
}

async function handleDownweight(tag: string) {
  await feedback.downweight(tag)
}

async function handleClickThrough(sectionId: number) {
  await feedback.clickThrough(sectionId)
}
</script>

<template>
  <div class="river">
    <div
      v-if="content.aboveSections.length"
      class="river-tier"
    >
      <h3 class="tier-label">Likely</h3>
      <SectionCard
        v-for="section in content.aboveSections"
        :key="section.id"
        :section="section"
        :threshold="content.threshold"
        :is-surprise="content.surpriseSectionIds.includes(section.id)"
        :focused="content.focusedSection?.id === section.id"
        @vote="handleVote"
        @downweight="handleDownweight"
        @click-through="handleClickThrough"
      />
    </div>

    <div
      v-if="content.surpriseSections.length"
      class="river-tier"
    >
      <h3 class="tier-label">Discover</h3>
      <SectionCard
        v-for="section in content.surpriseSections"
        :key="section.id"
        :section="section"
        :threshold="content.threshold"
        :is-surprise="true"
        :focused="content.focusedSection?.id === section.id"
        @vote="handleVote"
        @downweight="handleDownweight"
        @click-through="handleClickThrough"
      />
    </div>

    <div
      v-if="content.belowSections.length"
      class="river-tier"
    >
      <h3 class="tier-label">Below threshold</h3>
      <SectionCard
        v-for="section in content.belowSections"
        :key="section.id"
        :section="section"
        :threshold="content.threshold"
        :is-surprise="false"
        :focused="content.focusedSection?.id === section.id"
        @vote="handleVote"
        @downweight="handleDownweight"
        @click-through="handleClickThrough"
      />
    </div>
  </div>
</template>

<style scoped>
.river {
  max-width: 48rem;
  margin: 0 auto;
}

.river-tier {
  margin-bottom: 1.5rem;
}

.river-tier > :deep(.section-card) {
  margin-bottom: 0.75rem;
}

.tier-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  margin: 0 0 0.5rem;
  padding-bottom: 0.375rem;
  border-bottom: 1px solid var(--pq-border);
}
</style>
