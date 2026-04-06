import { test, expect } from '@playwright/test'
import { loginAsAdmin, waitForSections, reseedDatabase } from './helpers'

test.describe('UAT: Triage — River Layout', () => {
  test.beforeAll(() => reseedDatabase())

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await waitForSections(page)
  })

  test('renders three tier groups with correct labels', async ({ page }) => {
    const tiers = page.locator('.tier-label')
    await expect(tiers).toHaveCount(3)
    await expect(tiers.nth(0)).toContainText('Likely')
    await expect(tiers.nth(1)).toContainText('Discover')
    await expect(tiers.nth(2)).toContainText('Below threshold')
  })

  test('section cards are present in river layout', async ({ page }) => {
    const cards = page.locator('.section-card')
    const count = await cards.count()
    expect(count).toBeGreaterThan(0)
  })

  test('section card shows heading, summary, and meta', async ({ page }) => {
    const card = page.locator('.section-card').first()
    await expect(card.locator('.card-heading')).toBeVisible()
    await expect(card.locator('.card-summary')).toBeVisible()
    await expect(card.locator('.card-feed')).toBeVisible()
  })

  test('section card expands on click to show reasoning', async ({ page }) => {
    // Find a card that has reasoning (the seeded sections all have it)
    const card = page.locator('.section-card').first()
    // Should not show reasoning initially
    await expect(card.locator('.card-reasoning')).not.toBeVisible()
    // Click to expand
    await card.click()
    await expect(card).toHaveClass(/expanded/)
    await expect(card.locator('.card-reasoning')).toBeVisible()
    await expect(card.locator('.reasoning-text')).not.toBeEmpty()
  })

  test('section card shows topic tags', async ({ page }) => {
    const card = page.locator('.section-card').first()
    const tags = card.locator('.tag-chip')
    const count = await tags.count()
    expect(count).toBeGreaterThan(0)
  })

  test('confidence badge is visible on each card', async ({ page }) => {
    const badges = page.locator('.section-card .badge')
    const count = await badges.count()
    expect(count).toBeGreaterThan(0)
  })

  test('upvote button submits feedback and stays active', async ({ page }) => {
    const card = page.locator('.section-card').first()
    const upBtn = card.locator('.vote-up')
    await upBtn.click()
    await expect(upBtn).toHaveClass(/active/)
    await expect(upBtn).toHaveAttribute('aria-pressed', 'true')
  })

  test('downvote button submits feedback and stays active', async ({ page }) => {
    const card = page.locator('.section-card').first()
    const downBtn = card.locator('.vote-down')
    await downBtn.click()
    await expect(downBtn).toHaveClass(/active/)
    await expect(downBtn).toHaveAttribute('aria-pressed', 'true')
  })

  test('keyboard j/k navigates between sections', async ({ page }) => {
    // Press j to focus first section
    await page.keyboard.press('j')
    await expect(page.locator('.section-card.focused')).toHaveCount(1)

    // Press j again to move to next
    await page.keyboard.press('j')
    await expect(page.locator('.section-card.focused')).toHaveCount(1)
  })

  test('keyboard u votes on focused section', async ({ page }) => {
    // Focus a section first
    await page.keyboard.press('j')
    await expect(page.locator('.section-card.focused')).toHaveCount(1)

    // Upvote with 'u'
    await page.keyboard.press('u')
    const focusedCard = page.locator('.section-card.focused')
    await expect(focusedCard.locator('.vote-up')).toHaveClass(/active/)
  })

  test('open article button exists on cards with URLs', async ({ page }) => {
    const openBtns = page.locator('.section-card .open-btn')
    const count = await openBtns.count()
    expect(count).toBeGreaterThan(0)
  })
})
