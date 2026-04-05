/**
 * Focus trap composable for modal dialogs.
 *
 * Usage:
 *   const panelRef = ref<HTMLElement | null>(null)
 *   useFocusTrap(panelRef, onClose)
 *   <div ref="panelRef">...</div>
 *
 * Traps Tab/Shift+Tab within the element, focuses first interactive
 * element on mount, and handles Escape to close.
 */

import { type Ref, onMounted, onUnmounted, nextTick } from 'vue'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useFocusTrap(trapRef: Ref<HTMLElement | null>, onClose: () => void) {
  let previouslyFocused: HTMLElement | null = null

  function getFocusableElements(): HTMLElement[] {
    if (!trapRef.value) return []
    return Array.from(trapRef.value.querySelectorAll<HTMLElement>(FOCUSABLE))
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
      return
    }

    if (e.key !== 'Tab') return

    const focusable = getFocusableElements()
    if (!focusable.length) return

    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault()
        last.focus()
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }

  onMounted(async () => {
    previouslyFocused = document.activeElement as HTMLElement
    await nextTick()
    const focusable = getFocusableElements()
    if (focusable.length) focusable[0].focus()
    document.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
    previouslyFocused?.focus()
  })
}
