import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import App from '@/App.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', component: { template: '<div>Home</div>' } }],
})

describe('App', () => {
  it('renders the app title', async () => {
    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('.app-title').text()).toBe('Piqued')
  })

  it('renders navigation links', async () => {
    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })

    const links = wrapper.findAll('.app-nav a')
    expect(links.length).toBe(3)
    expect(links[0].text()).toBe('Triage')
    expect(links[1].text()).toBe('Feeds')
    expect(links[2].text()).toBe('Settings')
  })
})
