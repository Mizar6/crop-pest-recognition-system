import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: '127.0.0.1',
    port: 5176,
    watch: { usePolling: true, interval: 400 },
    proxy: {
      '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:8001', changeOrigin: true }
    }
  }
})
