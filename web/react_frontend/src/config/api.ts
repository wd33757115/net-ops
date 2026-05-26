import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'

/** Django BFF 前缀，开发环境走 Vite 代理，生产环境由 Django 同源提供 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export const TOKEN_KEY = 'access_token'

export interface BffEnvelope<T = unknown> {
  success: boolean
  data: T
  error: string | null
}

export function isBffEnvelope(value: unknown): value is BffEnvelope {
  return (
    !!value &&
    typeof value === 'object' &&
    'success' in value &&
    'data' in value &&
    'error' in value
  )
}

export function saveAccessToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem('access')
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => {
    if (isBffEnvelope(response.data)) {
      if (!response.data.success) {
        return Promise.reject(new Error(response.data.error || 'Request failed'))
      }
      response.data = response.data.data
    }
    return response
  },
  (error: AxiosError<BffEnvelope | { error?: string; detail?: string }>) => {
    const status = error.response?.status
    const payload = error.response?.data
    const serverMessage =
      (isBffEnvelope(payload) ? payload.error : null) ||
      (payload && 'error' in payload ? payload.error : undefined) ||
      (payload && 'detail' in payload ? String(payload.detail) : undefined) ||
      error.message

    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('access')
      message.error('登录已过期，请重新登录')
    } else if (status === 403) {
      message.error('没有权限执行此操作')
    } else if (status && status >= 500) {
      message.error(`服务器错误: ${serverMessage}`)
    }

    return Promise.reject(error)
  }
)

/** WebSocket 连接地址，统一经 Django（8001）代理 */
export function getChatWebSocketUrl(threadId?: string): string {
  const wsBase = import.meta.env.VITE_WS_BASE_URL
  if (wsBase) {
    let url = wsBase
    if (threadId) {
      url += `${url.includes('?') ? '&' : '?'}thread_id=${encodeURIComponent(threadId)}`
    }
    return url
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  let url = `${protocol}//${window.location.host}/ws/v1/chat`
  if (threadId) {
    url += `?thread_id=${encodeURIComponent(threadId)}`
  }
  return url
}
