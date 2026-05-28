import React from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from 'react-query'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import '@harmony-font-regular.css'
import '@harmony-font-medium.css'
import '@harmony-font-semibold.css'
import './styles/fonts.css'
import './index.css'

const queryClient = new QueryClient()

const fontFamily =
  "'PingFang SC', 'HarmonyOS Sans SC', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            fontFamily,
          },
        }}
      >
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
