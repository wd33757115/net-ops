// SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
// SPDX-License-Identifier: Apache-2.0

import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const harmonyFontDist = path.resolve(__dirname, 'node_modules/harmonyos-sans-sc-webfont-splitted/dist')

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
    resolve: {
      alias: {
        '@harmony-font-regular.css': path.join(harmonyFontDist, 'Regular.css'),
        '@harmony-font-medium.css': path.join(harmonyFontDist, 'Medium.css'),
        '@harmony-font-semibold.css': path.join(harmonyFontDist, 'Semibold.css'),
      },
    },
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
