import { test, expect } from '@playwright/test'
import { loginAsAdmin, waitForSections } from './helpers'

test.describe('UAT: Date Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await waitForSections(page)
  })

  test('date nav shows current date label', async ({ page }) => {
    const dateLabel = page.locator('.date-label')
    await expect(dateLabel).toBeVisible()
    // Should show a date string (format varies — "Today" or "Mon, Apr 6" etc.)
    const text = await dateLabel.textContent()
    expect(text?.trim().length).toBeGreaterThan(0)
  })

  test('previous date button navigates to a different date', async ({ page }) => {
    const prevBtn = page.locator('.date-btn[aria-label="Previous date"]')
    await expect(prevBtn).toBeEnabled()
    const dateLabel = page.locator('.date-label')
    const initialText = await dateLabel.textContent()
    await prevBtn.click()
    // Date label should change
    await expect(dateLabel).not.toContainText(initialText!)
  })

  test('next date button is disabled on most recent date', async ({ page }) => {
    const nextBtn = page.locator('.date-btn[aria-label="Next date"]')
    await expect(nextBtn).toBeDisabled()
  })

  test('navigating back then forward returns to original date', async ({ page }) => {
    const prevBtn = page.locator('.date-btn[aria-label="Previous date"]')
    const nextBtn = page.locator('.date-btn[aria-label="Next date"]')
    const dateLabel = page.locator('.date-label')

    const initialText = await dateLabel.textContent()

    await prevBtn.click()
    await expect(dateLabel).not.toContainText(initialText!)

    await nextBtn.click()
    await expect(dateLabel).toContainText(initialText!)
  })
})
