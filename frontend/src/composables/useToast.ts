/**
 * Toast notification system.
 *
 * Usage:
 *   const toast = useToast()
 *   toast.success('Saved')
 *   toast.error('Something went wrong')
 *   toast.info('Processing...')
 */

import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  type: ToastType
  message: string
}

const AUTO_DISMISS_MS = 4000
let nextId = 0

const toasts = ref<Toast[]>([])

function add(type: ToastType, message: string) {
  const id = nextId++
  toasts.value.push({ id, type, message })

  // Error toasts require manual dismiss; success/info auto-dismiss
  if (type !== 'error') {
    setTimeout(() => {
      dismiss(id)
    }, AUTO_DISMISS_MS)
  }
}

function dismiss(id: number) {
  const idx = toasts.value.findIndex((t) => t.id === id)
  if (idx !== -1) {
    toasts.value.splice(idx, 1)
  }
}

export function useToast() {
  return {
    toasts,
    dismiss,
    success(message: string) {
      add('success', message)
    },
    error(message: string) {
      add('error', message)
    },
    info(message: string) {
      add('info', message)
    },
  }
}
