/**
 * Command palette logic.
 *
 * Cmd+K opens the palette. Type to filter commands.
 * Commands: switch layout, jump to date, navigate to views.
 *
 * The visible/query state is module-level so it can be toggled from
 * useKeyboard without needing Vue injection context. The router-dependent
 * commands are only built when called from within a component setup.
 */

import { ref, computed } from 'vue'
import type { Router } from 'vue-router'
import { useContentStore } from '@/stores/content'
import { useLayout } from '@/composables/useLayout'

export interface PaletteCommand {
  id: string
  label: string
  category: string
  action: () => void
}

const visible = ref(false)
const query = ref('')

/**
 * Toggle/open/close the palette without needing injection context.
 * Safe to call from keyboard handlers outside component setup.
 */
export function togglePalette() {
  if (visible.value) {
    visible.value = false
    query.value = ''
  } else {
    visible.value = true
    query.value = ''
  }
}

/**
 * Full command palette composable. Must be called from component setup
 * (needs router injection).
 */
export function useCommandPalette(router: Router) {
  const content = useContentStore()
  const layout = useLayout()

  const commands = computed<PaletteCommand[]>(() => {
    const cmds: PaletteCommand[] = [
      // Navigation
      { id: 'nav-triage', label: 'Go to Triage', category: 'Navigate', action: () => router.push('/') },
      { id: 'nav-feeds', label: 'Go to Feeds', category: 'Navigate', action: () => router.push('/feeds') },
      { id: 'nav-settings', label: 'Go to Settings', category: 'Navigate', action: () => router.push('/settings') },
      { id: 'nav-log', label: 'Go to Log', category: 'Navigate', action: () => router.push('/log') },

      // Layout
      { id: 'layout-river', label: 'Switch to River layout', category: 'Layout', action: () => layout.setMode('river') },
      { id: 'layout-reader', label: 'Switch to Reader layout', category: 'Layout', action: () => layout.setMode('reader') },
      { id: 'layout-columns', label: 'Switch to Columns layout', category: 'Layout', action: () => layout.setMode('columns') },
    ]

    // Date navigation
    for (const d of content.datesAvailable) {
      cmds.push({
        id: `date-${d}`,
        label: `Jump to ${d}`,
        category: 'Date',
        action: () => content.loadSections(d),
      })
    }

    return cmds
  })

  const filtered = computed(() => {
    if (!query.value) return commands.value
    const q = query.value.toLowerCase()
    return commands.value.filter(
      (c) => c.label.toLowerCase().includes(q) || c.category.toLowerCase().includes(q),
    )
  })

  function open() {
    visible.value = true
    query.value = ''
  }

  function close() {
    visible.value = false
    query.value = ''
  }

  function execute(cmd: PaletteCommand) {
    cmd.action()
    close()
  }

  return {
    visible,
    query,
    filtered,
    open,
    close,
    execute,
  }
}
