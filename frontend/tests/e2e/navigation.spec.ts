import { test, expect } from '@playwright/test'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.fill('input[name="username"]', 'testuser')
  await page.fill('input[name="password"]', 'testpass')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/')
}

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
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
    // Should show 2 test feeds from seed data
    await expect(page.locator('.feeds-count')).toContainText('2 feeds')
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
    // Get initial theme
    const html = page.locator('html')
    const initialTheme = await html.getAttribute('data-theme')

    // Click theme toggle
    await page.click('.toolbar-btn:first-child')

    // Theme should have changed
    const newTheme = await html.getAttribute('data-theme')
    expect(newTheme).not.toBe(initialTheme)

    // Toggle back
    await page.click('.toolbar-btn:first-child')
    const restoredTheme = await html.getAttribute('data-theme')
    expect(restoredTheme).toBe(initialTheme)
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
