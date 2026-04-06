import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { execSync } from 'child_process'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const rootDir = resolve(__dirname, '..', '..', '..')
const dbPath = '/tmp/piqued_e2e.db'

/** Re-seed the E2E database to ensure clean state */
export function reseedDatabase() {
  execSync(
    `PIQUED_DATABASE_PATH=${dbPath} PYTHONPATH=${rootDir} conda run -n piqued python scripts/seed_e2e.py`,
    { cwd: rootDir, stdio: 'pipe' },
  )
}

export async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.fill('input[name="username"]', 'testuser')
  await page.fill('input[name="password"]', 'testpass')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/')
}

export async function loginAsUser(page: Page) {
  await page.goto('/login')
  await page.fill('input[name="username"]', 'reader')
  await page.fill('input[name="password"]', 'userpass')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/')
}

/** Wait for triage sections to load (spinner gone, content visible) */
export async function waitForSections(page: Page) {
  await expect(page.locator('.loading-spinner')).not.toBeVisible({ timeout: 10_000 })
  // Wait for either section cards or empty state to appear
  await page
    .locator('.section-card, .compact-card, .empty-state, .river-tier, .tier-empty')
    .first()
    .waitFor({ state: 'visible', timeout: 10_000 })
}
