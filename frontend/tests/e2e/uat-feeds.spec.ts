import { test, expect } from '@playwright/test'
import { loginAsAdmin, loginAsUser, reseedDatabase } from './helpers'

async function navigateToFeeds(page: import('@playwright/test').Page) {
  await page.click('.app-nav a:has-text("Feeds")')
  await expect(page).toHaveURL('/feeds')
  // Wait for feeds to load
  await expect(page.locator('.loading-spinner')).not.toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.feeds-grid, .empty-state')).toBeVisible({ timeout: 10_000 })
}

test.describe('UAT: Feeds Management', () => {
  test.beforeAll(() => reseedDatabase())

  test.describe('as admin', () => {
    test.beforeEach(async ({ page }) => {
      await loginAsAdmin(page)
      await navigateToFeeds(page)
    })

    test('shows feed count and category groups', async ({ page }) => {
      await expect(page.locator('.feeds-count')).toContainText('3 feeds')
      const categories = page.locator('.category-title')
      const count = await categories.count()
      expect(count).toBeGreaterThan(0)
    })

    test('feed cards show title and meta', async ({ page }) => {
      const card = page.locator('.feed-card').first()
      await expect(card.locator('.feed-title')).toBeVisible()
      await expect(card.locator('.feed-meta')).toBeVisible()
    })

    test('admin sees toggle button on feed cards', async ({ page }) => {
      const toggleBtns = page.locator('.feed-toggle')
      const count = await toggleBtns.count()
      expect(count).toBeGreaterThan(0)
    })

    test('inactive feed card is visually dimmed', async ({ page }) => {
      const inactiveCard = page.locator('.feed-card.inactive')
      await expect(inactiveCard).toBeVisible()
    })

    test('toggling a feed changes its state', async ({ page }) => {
      // Find the first feed card's toggle button
      const firstCard = page.locator('.feed-card').first()
      const toggleBtn = firstCard.locator('.feed-toggle')
      if (await toggleBtn.isVisible()) {
        const textBefore = await toggleBtn.textContent()
        await toggleBtn.click()
        // The button text should change
        if (textBefore?.includes('On')) {
          await expect(toggleBtn).toContainText('Off')
        } else {
          await expect(toggleBtn).toContainText('On')
        }
      }
    })

    test('admin sees sync button', async ({ page }) => {
      await expect(page.locator('.sync-btn')).toBeVisible()
    })

    test('clicking a feed navigates to feed detail', async ({ page }) => {
      await page.locator('.feed-main').first().click()
      await expect(page).toHaveURL(/\/feed\/\d+/)
    })
  })

  test.describe('as regular user', () => {
    test('does not see toggle buttons or sync button', async ({ page }) => {
      await loginAsUser(page)
      await navigateToFeeds(page)

      await expect(page.locator('.feed-toggle')).toHaveCount(0)
      await expect(page.locator('.sync-btn')).toHaveCount(0)
    })
  })
})
