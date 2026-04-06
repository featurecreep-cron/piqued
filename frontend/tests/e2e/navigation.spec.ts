import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('nav links are visible', async ({ page }) => {
    await expect(page.locator('.app-nav a', { hasText: 'Triage' })).toBeVisible()
    await expect(page.locator('.app-nav a', { hasText: 'Feeds' })).toBeVisible()
    await expect(page.locator('.app-nav a', { hasText: 'Log' })).toBeVisible()
    await expect(page.locator('.app-nav a', { hasText: 'Settings' })).toBeVisible()
  })

  test('navigate to feeds page', async ({ page }) => {
    await page.click('.app-nav a:has-text("Feeds")')
    await expect(page).toHaveURL('/feeds')
    await expect(page.locator('.feeds-title')).toContainText('Feeds')
    await expect(page.locator('.feeds-count')).toContainText('3 feeds')
  })

  test('navigate to log page', async ({ page }) => {
    await page.click('.app-nav a:has-text("Log")')
    await expect(page).toHaveURL('/log')
  })

  test('navigate to settings page', async ({ page }) => {
    await page.click('.app-nav a:has-text("Settings")')
    await expect(page).toHaveURL('/settings')
  })

  test('theme toggle switches dark/light', async ({ page }) => {
    const html = page.locator('html')
    const initialTheme = await html.getAttribute('data-theme')
    const themeBtn = page.locator('.toolbar-btn[aria-label*="theme"]')

    await themeBtn.click()
    const newTheme = await html.getAttribute('data-theme')
    expect(newTheme).not.toBe(initialTheme)

    // Toggle again — should change to a third state or cycle
    await themeBtn.click()
    const thirdTheme = await html.getAttribute('data-theme')
    expect(thirdTheme).not.toBe(newTheme)
  })

  test('keyboard help overlay opens with ?', async ({ page }) => {
    await page.keyboard.press('?')
    await expect(page.locator('.help-panel')).toBeVisible()
    await expect(page.locator('.help-title')).toContainText('Keyboard shortcuts')

    // Close with Escape
    await page.keyboard.press('Escape')
    await expect(page.locator('.help-panel')).not.toBeVisible()
  })

  test('logout redirects to login', async ({ page }) => {
    await page.click('.toolbar-btn--logout')
    await expect(page).toHaveURL(/\/logout|\/login/)
  })
})
