import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const djangoTarget = env.VITE_DJANGO_BACKEND_URL || 'http://localhost:8001'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: djangoTarget,
          changeOrigin: true
        },
        '/ws': {
          target: djangoTarget,
          changeOrigin: true,
          ws: true
        }
      }
    }
  }
})
