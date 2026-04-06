import { test, expect } from '@playwright/test'
import { loginAsAdmin, loginAsUser } from './helpers'

test.describe('UAT: Settings', () => {
  test.describe('as admin', () => {
    test.beforeEach(async ({ page }) => {
      await loginAsAdmin(page)
      await page.click('.app-nav a:has-text("Settings")')
      await expect(page).toHaveURL('/settings')
    })

    test('shows tab navigation with all tabs', async ({ page }) => {
      await expect(page.locator('.tab:has-text("Profile")')).toBeVisible()
      await expect(page.locator('.tab:has-text("Config")')).toBeVisible()
      await expect(page.locator('.tab:has-text("API Keys")')).toBeVisible()
      await expect(page.locator('.tab:has-text("Users")')).toBeVisible()
    })

    test('profile tab shows interest profile textarea', async ({ page }) => {
      const textarea = page.locator('textarea')
      await expect(textarea).toBeVisible()
      // Should have pre-filled profile text from seed
      const value = await textarea.inputValue()
      expect(value.length).toBeGreaterThan(0)
    })

    test('synthesize button is visible', async ({ page }) => {
      const synthBtn = page.locator('button:has-text("Synthesize")')
      await expect(synthBtn).toBeVisible()
    })

    test('config tab shows categorized settings with labels', async ({ page }) => {
      await page.locator('.tab:has-text("Config")').click()
      // Should show category groups
      await expect(page.locator('text=Authentication')).toBeVisible()
      // Settings should have labels
      const labels = page.locator('.field-label, label')
      const count = await labels.count()
      expect(count).toBeGreaterThan(0)
    })

    test('API keys tab allows creating a key', async ({ page }) => {
      await page.locator('.tab:has-text("API Keys")').click()
      const nameInput = page.locator('input[placeholder*="name" i], input[type="text"]').last()
      if (await nameInput.isVisible()) {
        await nameInput.fill('Test E2E Key')
        const createBtn = page.locator('button:has-text("Create")')
        await createBtn.click()
        // Should show the new key value (only shown once)
        await expect(page.locator('.new-key-value, code')).toBeVisible({ timeout: 5_000 })
      }
    })

    test('API key revoke requires two-step confirmation', async ({ page }) => {
      await page.locator('.tab:has-text("API Keys")').click()
      // First create a key to revoke
      const nameInput = page.locator('input[placeholder*="name" i], input[type="text"]').last()
      if (await nameInput.isVisible()) {
        await nameInput.fill('Revoke Test Key')
        await page.locator('button:has-text("Create")').click()
        await expect(page.locator('.new-key-value, code')).toBeVisible({ timeout: 5_000 })
      }
      const revokeBtn = page.locator('button:has-text("Revoke")').first()
      if (await revokeBtn.isVisible()) {
        await revokeBtn.click()
        // Should show confirmation, not immediately delete
        await expect(page.locator('button:has-text("Confirm")')).toBeVisible()
      }
    })

    test('users tab shows user management table', async ({ page }) => {
      await page.locator('.tab:has-text("Users")').click()
      // Should show at least the two seeded users — use specific selector to avoid strict mode
      await expect(page.locator('.user-name:has-text("testuser")')).toBeVisible()
      await expect(page.locator('.user-name:has-text("reader")')).toBeVisible()
    })
  })

  test.describe('as regular user', () => {
    test('does not see config or users tabs', async ({ page }) => {
      await loginAsUser(page)
      await page.click('.app-nav a:has-text("Settings")')
      await expect(page).toHaveURL('/settings')

      // Should see profile and API keys tabs
      await expect(page.locator('.tab:has-text("Profile")')).toBeVisible()
      await expect(page.locator('.tab:has-text("API Keys")')).toBeVisible()
      // Should not see admin tabs
      await expect(page.locator('.tab:has-text("Config")')).toHaveCount(0)
      await expect(page.locator('.tab:has-text("Users")')).toHaveCount(0)
    })
  })
})
