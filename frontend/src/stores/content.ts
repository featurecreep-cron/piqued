import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi, ApiError } from '@/composables/useApi'
import type { SectionList, SectionItem } from '@/types/api'

export const useContentStore = defineStore('content', () => {
  const sections = ref<SectionItem[]>([])
  const date = ref('')
  const datesAvailable = ref<string[]>([])
  const threshold = ref(0)
  const surpriseSectionIds = ref<number[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const focusedIndex = ref(0)

  const api = useApi()

  const aboveSections = computed(() =>
    sections.value.filter((s) => s.score >= threshold.value),
  )

  const belowSections = computed(() =>
    sections.value.filter((s) => s.score < threshold.value && !surpriseSectionIds.value.includes(s.id)),
  )

  const surpriseSections = computed(() =>
    sections.value.filter((s) => surpriseSectionIds.value.includes(s.id) && s.score < threshold.value),
  )

  // Display order: above → surprise → below (matches river visual order).
  // Reader/columns filter from this list; focus traversal follows this order.
  const displayOrder = computed(() => [
    ...aboveSections.value,
    ...surpriseSections.value,
    ...belowSections.value,
  ])

  const focusedSection = computed(() => displayOrder.value[focusedIndex.value] ?? null)

  async function loadSections(targetDate?: string) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = {}
      if (targetDate) params.date = targetDate
      const data = await api.get<SectionList>('/sections', params)
      sections.value = data.sections
      date.value = data.date
      datesAvailable.value = data.dates_available
      threshold.value = data.threshold
      surpriseSectionIds.value = data.surprise_section_ids
      focusedIndex.value = 0
    } catch (err) {
      if (err instanceof ApiError) {
        error.value = err.detail
      } else {
        error.value = 'Failed to load sections'
      }
    } finally {
      loading.value = false
    }
  }

  function focusNext() {
    if (focusedIndex.value < displayOrder.value.length - 1) {
      focusedIndex.value++
    }
  }

  function focusPrev() {
    if (focusedIndex.value > 0) {
      focusedIndex.value--
    }
  }

  function focusByIndex(index: number) {
    if (index >= 0 && index < displayOrder.value.length) {
      focusedIndex.value = index
    }
  }

  function focusBySectionId(sectionId: number) {
    const idx = displayOrder.value.findIndex((s) => s.id === sectionId)
    if (idx !== -1) focusedIndex.value = idx
  }

  function $reset() {
    sections.value = []
    date.value = ''
    datesAvailable.value = []
    threshold.value = 0
    surpriseSectionIds.value = []
    loading.value = false
    error.value = null
    focusedIndex.value = 0
  }

  return {
    sections,
    date,
    datesAvailable,
    threshold,
    surpriseSectionIds,
    loading,
    error,
    focusedIndex,
    aboveSections,
    belowSections,
    surpriseSections,
    displayOrder,
    focusedSection,
    loadSections,
    focusNext,
    focusPrev,
    focusByIndex,
    focusBySectionId,
    $reset,
  }
})
