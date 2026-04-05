/**
 * Keyboard navigation composable.
 *
 * Global bindings: ?, Escape
 * River mode: j/k (navigate), u/d (vote), Enter (expand), o (open)
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { useContentStore } from '@/stores/content'
import { useFeedback } from '@/composables/useFeedback'
import { useLayout } from '@/composables/useLayout'
import { togglePalette } from '@/composables/useCommandPalette'

export function useKeyboard() {
  const helpVisible = ref(false)

  function isInputFocused(): boolean {
    const el = document.activeElement
    if (!el) return false
    const tag = el.tagName.toLowerCase()
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
    if ((el as HTMLElement).isContentEditable) return true
    return false
  }

  function handleKeydown(e: KeyboardEvent) {
    // Cmd+K works even when input is focused
    if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      togglePalette()
      return
    }

    if (isInputFocused()) return

    // Global bindings
    if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      helpVisible.value = !helpVisible.value
      return
    }

    if (e.key === 'Escape') {
      if (helpVisible.value) {
        helpVisible.value = false
        e.preventDefault()
      }
      return
    }

    // Skip mode bindings if help overlay is open
    if (helpVisible.value) return

    const content = useContentStore()
    const feedback = useFeedback()
    const layout = useLayout()

    // Layout cycling
    if (e.key === 'v' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      layout.cycle()
      return
    }

    switch (e.key) {
      case 'j':
        e.preventDefault()
        content.focusNext()
        scrollFocusedIntoView()
        break
      case 'k':
        e.preventDefault()
        content.focusPrev()
        scrollFocusedIntoView()
        break
      case 'Enter': {
        e.preventDefault()
        const section = content.focusedSection
        if (section) {
          // In reader/columns, select the focused section into the detail pane
          // by dispatching a custom event that layouts can listen for
          window.dispatchEvent(new CustomEvent('piqued:select-focused', { detail: { sectionId: section.id } }))
        }
        break
      }
      case 'u': {
        e.preventDefault()
        const section = content.focusedSection
        if (section) feedback.vote(section.id, 1)
        break
      }
      case 'd': {
        e.preventDefault()
        const section = content.focusedSection
        if (section) feedback.vote(section.id, -1)
        break
      }
      case 'o': {
        e.preventDefault()
        const section = content.focusedSection
        if (section?.article_url) {
          window.open(section.article_url, '_blank', 'noopener')
          feedback.clickThrough(section.id)
        }
        break
      }
    }
  }

  function scrollFocusedIntoView() {
    requestAnimationFrame(() => {
      const el = document.querySelector('.section-card.focused, .compact-card.focused')
      el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    helpVisible,
  }
}
