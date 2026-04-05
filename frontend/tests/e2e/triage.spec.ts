import { test, expect } from '@playwright/test'

// Helper: login and navigate to triage
async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.fill('input[name="username"]', 'testuser')
  await page.fill('input[name="password"]', 'testpass')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/')
}

test.describe('Triage View', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('shows triage header with layout toggle', async ({ page }) => {
    await expect(page.locator('.triage-title')).toContainText('Triage')
    await expect(page.locator('.layout-toggle')).toBeVisible()
  })

  test('layout toggle switches between modes', async ({ page }) => {
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

  test('empty state when no sections', async ({ page }) => {
    // Test DB has feeds but no articles/sections
    await expect(page.locator('.empty-state')).toBeVisible()
    await expect(page.locator('.empty-message')).toContainText('No sections')
  })
})
