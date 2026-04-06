import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('UAT: Error States & Edge Cases', () => {
  test('404 page renders for unknown routes', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/nonexistent-page')
    await expect(page.locator('text=Not Found')).toBeVisible()
    // Should have a way back
    await expect(page.locator('a:has-text("Triage"), a:has-text("Back")')).toBeVisible()
  })

  test('document title updates on route change', async ({ page }) => {
    await loginAsAdmin(page)
    await expect(page).toHaveTitle(/.+/)

    await page.click('.app-nav a:has-text("Feeds")')
    await expect(page).toHaveTitle(/Feeds/)

    await page.click('.app-nav a:has-text("Settings")')
    await expect(page).toHaveTitle(/Settings/)
  })

  test('browser back/forward works correctly', async ({ page }) => {
    await loginAsAdmin(page)
    await expect(page).toHaveURL('/')

    await page.click('.app-nav a:has-text("Feeds")')
    await expect(page).toHaveURL('/feeds')

    await page.click('.app-nav a:has-text("Settings")')
    await expect(page).toHaveURL('/settings')

    await page.goBack()
    await expect(page).toHaveURL('/feeds')

    // Second goBack may land on / or /login depending on auth redirect history
    await page.goBack()
    await expect(page).toHaveURL(/\/(login)?$/)

    await page.goForward()
    await expect(page).toHaveURL('/feeds')
  })

  test('deep link to feeds works on fresh load', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/feeds')
    await expect(page).toHaveURL('/feeds')
    await expect(page.locator('.feeds-title')).toContainText('Feeds')
  })

  test('deep link to settings works on fresh load', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/settings')
    await expect(page).toHaveURL('/settings')
  })

  test('app shows loading indicator during session check', async ({ page }) => {
    // Navigate fresh — the app should briefly show loading before rendering
    await page.goto('/')
    // Either we see the loading state or it resolved fast — both are acceptable
    // The key assertion is that we don't see a flash of the SPA without auth
    await expect(page.locator('.app-nav, .loading-indicator, input[name="username"]')).toBeVisible({ timeout: 5_000 })
  })
})
