import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const rootDir = resolve(__dirname, '..')
const dbPath = '/tmp/piqued_e2e.db'

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:8400',
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  globalSetup: './tests/e2e/global-setup.ts',
  webServer: {
    command: `PIQUED_DATABASE_PATH=${dbPath} PIQUED_SESSION_SECRET=e2e-test-secret PYTHONPATH=${rootDir} conda run -n piqued python -m uvicorn piqued.main:app --host 127.0.0.1 --port 8400`,
    cwd: rootDir,
    port: 8400,
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
