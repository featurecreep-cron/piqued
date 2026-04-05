import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('redirects unauthenticated user to login', async ({ page }) => {
    await page.goto('/')
    // Should redirect to /login
    await expect(page).toHaveURL(/\/login/)
  })

  test('login with valid credentials', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'testpass')
    await page.click('button[type="submit"]')

    // Should redirect to the SPA
    await expect(page).toHaveURL('/')
    // Should show the username in the toolbar
    await expect(page.locator('.toolbar-user')).toContainText('testuser')
  })

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'wrongpass')
    await page.click('button[type="submit"]')

    // Should stay on login page
    await expect(page).toHaveURL(/\/login/)
  })
})
