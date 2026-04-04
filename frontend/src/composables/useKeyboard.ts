/**
 * Keyboard navigation composable.
 *
 * Step 3: global bindings only (?, Escape).
 * Step 4+: mode-aware bindings (river, reader, columns).
 */

import { ref, onMounted, onUnmounted } from 'vue'

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
    if (isInputFocused()) return

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
    }
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
