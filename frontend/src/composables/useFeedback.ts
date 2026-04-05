/**
 * Feedback composable with optimistic updates.
 *
 * Vote/downweight/click-through update the UI immediately,
 * then fire the API call. On failure, revert and show toast.
 */

import { reactive } from 'vue'
import { useApi, ApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { FeedbackResult } from '@/types/api'

const api = useApi()

// Module-level vote tracking — survives component remounts
const votes = reactive<Record<number, 1 | -1>>({})

export function useFeedback() {
  const toast = useToast()

  async function vote(sectionId: number, rating: 1 | -1): Promise<boolean> {
    // Optimistic update — show vote immediately
    votes[sectionId] = rating
    try {
      await api.post<FeedbackResult>('/feedback', {
        section_id: sectionId,
        rating,
      })
      return true
    } catch (err) {
      // Rollback on failure
      delete votes[sectionId]
      const detail = err instanceof ApiError ? err.detail : 'Vote failed'
      toast.error(detail)
      return false
    }
  }

  function getVote(sectionId: number): 1 | -1 | null {
    return votes[sectionId] ?? null
  }

  async function clickThrough(sectionId: number): Promise<boolean> {
    try {
      await api.post('/click-through', { section_id: sectionId })
      return true
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Click-through failed'
      toast.error(detail)
      return false
    }
  }

  async function downweight(tag: string): Promise<boolean> {
    try {
      await api.post('/downweight', { tag })
      toast.success(`Downweighted "${tag}"`)
      return true
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Downweight failed'
      toast.error(detail)
      return false
    }
  }

  return { vote, getVote, votes, clickThrough, downweight }
}
