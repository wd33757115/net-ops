import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const djangoTarget = env.VITE_DJANGO_BACKEND_URL || 'http://localhost:8001'

  return {
    plugins: [
      react({ fastRefresh: false }),
      {
        name: 'strip-crossorigin-for-embedded-browser',
        transformIndexHtml(html) {
          return html.replace(/\s+crossorigin/g, '')
        },
      },
    ],
    optimizeDeps: {
      needsInterop: ['react', 'react-dom', 'react-dom/client'],
    },
    server: {
      port: 3000,
      strictPort: true,
      host: '0.0.0.0',
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
    },
    preview: {
      port: 3000,
      strictPort: true,
      host: '0.0.0.0',
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
