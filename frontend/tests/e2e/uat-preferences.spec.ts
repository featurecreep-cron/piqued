import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('UAT: User Preferences Persistence', () => {
  test('theme persists across page reload', async ({ page }) => {
    await loginAsAdmin(page)
    const html = page.locator('html')
    const initialTheme = await html.getAttribute('data-theme')

    // Toggle theme
    await page.click('.toolbar-btn[aria-label*="theme"]')
    const newTheme = await html.getAttribute('data-theme')
    expect(newTheme).not.toBe(initialTheme)

    // Reload and check persistence
    await page.reload()
    await expect(page.locator('.triage-title')).toBeVisible()
    const reloadedTheme = await html.getAttribute('data-theme')
    expect(reloadedTheme).toBe(newTheme)

    // Clean up: restore original theme
    if (reloadedTheme !== initialTheme) {
      await page.click('.toolbar-btn[aria-label*="theme"]')
    }
  })

  test('layout mode persists across page reload', async ({ page }) => {
    await loginAsAdmin(page)
    await expect(page.locator('.section-card')).toHaveCount(
      await page.locator('.section-card').count(),
    )

    // Switch to reader mode
    await page.click('.layout-btn:has-text("Reader")')
    await expect(page.locator('.layout-btn:has-text("Reader")')).toHaveAttribute('aria-pressed', 'true')

    // Reload and check persistence
    await page.reload()
    await expect(page.locator('.layout-btn:has-text("Reader")')).toHaveAttribute('aria-pressed', 'true')

    // Clean up: restore river
    await page.click('.layout-btn:has-text("River")')
  })
})
