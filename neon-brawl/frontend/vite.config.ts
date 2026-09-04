import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy: { '/ws': { target: 'ws://127.0.0.1:8080', ws: true }, '/health': 'http://127.0.0.1:8080', '/config': 'http://127.0.0.1:8080' } }
})
