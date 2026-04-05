import { execSync } from 'child_process'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default function globalSetup() {
  const rootDir = resolve(__dirname, '..', '..', '..')
  const frontendDir = resolve(rootDir, 'frontend')
  const dbPath = '/tmp/piqued_e2e.db'

  // Build the frontend if not already built
  const distDir = resolve(frontendDir, 'dist')
  if (!fs.existsSync(resolve(distDir, 'index.html'))) {
    execSync('npm run build', { cwd: frontendDir, stdio: 'inherit' })
  }

  // Symlink dist to where the backend expects it
  const spaDir = resolve(rootDir, 'piqued', 'web', 'spa')
  if (fs.existsSync(spaDir)) {
    fs.rmSync(spaDir, { recursive: true })
  }
  fs.symlinkSync(distDir, spaDir)

  // Seed the database
  execSync(`PIQUED_DATABASE_PATH=${dbPath} PYTHONPATH=${rootDir} conda run -n piqued python scripts/seed_e2e.py`, {
    cwd: rootDir,
    stdio: 'inherit',
  })
}
