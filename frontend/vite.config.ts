import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8400',
      '/login': 'http://localhost:8400',
      '/logout': 'http://localhost:8400',
      '/auth': 'http://localhost:8400',
      '/setup': 'http://localhost:8400',
      '/onboarding': 'http://localhost:8400',
      '/health': 'http://localhost:8400',
      '/legacy': 'http://localhost:8400',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
