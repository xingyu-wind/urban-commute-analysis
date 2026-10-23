import vue from '@vitejs/plugin-vue'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import { apiProxy, backendTarget } from './config/proxy.ts'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'DEV_')
  return {
    plugins: [vue()],
    preview: {
      host: '127.0.0.1', strictPort: true,
      proxy: apiProxy(backendTarget(process.env.DEV_BACKEND_URL ?? env.DEV_BACKEND_URL)),
    },
    server: {
      host: '127.0.0.1', port: 5173, strictPort: true,
      proxy: apiProxy(backendTarget(process.env.DEV_BACKEND_URL ?? env.DEV_BACKEND_URL)),
    },
    test: { environment: 'jsdom', include: ['tests/**/*.test.ts'], restoreMocks: true },
  }
})
