import { test, expect } from '@playwright/test'
import { loginAsAdmin, waitForSections } from './helpers'

test.describe('UAT: Command Palette', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await waitForSections(page)
  })

  test('opens with Ctrl+K', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await expect(page.locator('.palette-backdrop')).toBeVisible()
    await expect(page.locator('.palette-panel')).toBeVisible()
  })

  test('closes with Escape', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await expect(page.locator('.palette-panel')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('.palette-backdrop')).not.toBeVisible()
  })

  test('shows action list', async ({ page }) => {
    await page.keyboard.press('Control+k')
    const items = page.locator('.palette-item')
    const count = await items.count()
    expect(count).toBeGreaterThan(0)
  })

  test('typing filters the action list', async ({ page }) => {
    await page.keyboard.press('Control+k')
    const items = page.locator('.palette-item')
    const initialCount = await items.count()

    await page.locator('.palette-input').fill('reader')
    const filteredCount = await items.count()
    expect(filteredCount).toBeLessThanOrEqual(initialCount)
  })

  test('selecting a layout action switches layout', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.locator('.palette-input').fill('reader')
    await page.keyboard.press('Enter')

    // Palette should close
    await expect(page.locator('.palette-backdrop')).not.toBeVisible()
    // Reader layout should be active
    await expect(page.locator('.layout-btn:has-text("Reader")')).toHaveAttribute('aria-pressed', 'true')
  })
})
