import { test, expect } from '@playwright/test'
import { loginAsAdmin, waitForSections, reseedDatabase } from './helpers'

test.describe('Triage View', () => {
  test.beforeAll(() => reseedDatabase())
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('shows triage header with layout toggle', async ({ page }) => {
    await expect(page.locator('.triage-title')).toContainText('Triage')
    await expect(page.locator('.layout-toggle')).toBeVisible()
  })

  test('layout toggle switches between modes', async ({ page }) => {
    await waitForSections(page)

    // Default is river
    const riverBtn = page.locator('.layout-btn', { hasText: 'River' })
    await expect(riverBtn).toHaveAttribute('aria-pressed', 'true')

    // Switch to reader
    const readerBtn = page.locator('.layout-btn', { hasText: 'Reader' })
    await readerBtn.click()
    await expect(readerBtn).toHaveAttribute('aria-pressed', 'true')
    await expect(riverBtn).toHaveAttribute('aria-pressed', 'false')

    // Switch to columns
    const columnsBtn = page.locator('.layout-btn', { hasText: 'Columns' })
    await columnsBtn.click()
    await expect(columnsBtn).toHaveAttribute('aria-pressed', 'true')
  })

  test('sections load and display in river mode', async ({ page }) => {
    // Ensure river mode (previous test may have switched layout)
    const riverBtn = page.locator('.layout-btn', { hasText: 'River' })
    await riverBtn.click()
    await waitForSections(page)
    // Should have section cards (not empty state)
    const cards = page.locator('.section-card')
    const count = await cards.count()
    expect(count).toBeGreaterThan(0)
  })
})
