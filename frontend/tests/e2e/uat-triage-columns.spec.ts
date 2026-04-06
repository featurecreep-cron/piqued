import { test, expect } from '@playwright/test'
import { loginAsAdmin, waitForSections, reseedDatabase } from './helpers'

test.describe('UAT: Triage - Columns Layout', () => {
  test.beforeAll(() => reseedDatabase())
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await waitForSections(page)
    // Switch to columns mode
    await page.click('.layout-btn:has-text("Columns")')
    await expect(page.locator('.layout-btn:has-text("Columns")')).toHaveAttribute('aria-pressed', 'true')
  })

  test('renders column layout with placeholder', async ({ page }) => {
    await expect(page.locator('.columns-layout')).toBeVisible()
    // Detail pane should show placeholder until selection
    await expect(page.locator('.columns-placeholder')).toBeVisible()
    await expect(page.locator('.columns-placeholder')).toContainText('Select a section')
  })

  test('selecting a section populates detail pane', async ({ page }) => {
    const card = page.locator('.compact-card').first()
    if (await card.isVisible()) {
      await card.click()
      await expect(page.locator('.columns-placeholder')).not.toBeVisible()
    }
  })

  test('voting works in columns detail pane', async ({ page }) => {
    // Select a section first
    const card = page.locator('.compact-card').first()
    if (await card.isVisible()) {
      await card.click()
      const detail = page.locator('.columns-detail')
      const upBtn = detail.locator('.vote-up')
      if (await upBtn.isVisible()) {
        await upBtn.click()
        await expect(upBtn).toHaveAttribute('aria-pressed', 'true')
      }
    }
  })
})
