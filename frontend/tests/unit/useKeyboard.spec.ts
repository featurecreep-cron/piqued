import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { useKeyboard } from '@/composables/useKeyboard'

// Wrapper component to test the composable lifecycle
const TestComponent = defineComponent({
  setup() {
    const { helpVisible } = useKeyboard()
    return { helpVisible }
  },
  template: '<div>{{ helpVisible }}</div>',
})

describe('useKeyboard', () => {
  it('? key toggles help visibility', async () => {
    const wrapper = mount(TestComponent)
    expect(wrapper.vm.helpVisible).toBe(false)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await nextTick()
    expect(wrapper.vm.helpVisible).toBe(true)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await nextTick()
    expect(wrapper.vm.helpVisible).toBe(false)

    wrapper.unmount()
  })

  it('Escape closes help', async () => {
    const wrapper = mount(TestComponent)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await nextTick()
    expect(wrapper.vm.helpVisible).toBe(true)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await nextTick()
    expect(wrapper.vm.helpVisible).toBe(false)

    wrapper.unmount()
  })

  it('ignores keys when input is focused', async () => {
    const wrapper = mount(TestComponent)
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await nextTick()
    expect(wrapper.vm.helpVisible).toBe(false)

    document.body.removeChild(input)
    wrapper.unmount()
  })
})
