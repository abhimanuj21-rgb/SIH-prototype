import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api -> FastAPI on :8000 so the frontend can use
// same-origin relative URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,
    strictPort: true,
    proxy: {
      '/api': {
        // override to run a second dev stack side by side (e.g. :8001)
        target: process.env.API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
