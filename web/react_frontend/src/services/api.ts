import { api, getChatWebSocketUrl } from '../config/api'

export interface ChatRequest {
  query: string
  thread_id?: string
  uploaded_file_path?: string
}

export interface ChatUploadRequest {
  thread_id: string
  filename: string
  file_content: string
  user_id?: string
}

export interface ChatUploadResponse {
  thread_id: string
  filename: string
  file_path: string
  status: string
  message: string
  next_steps?: string
}

export interface ChatResponse {
  response: string
  thread_id: string
  agent_type?: string
  celery_task_id?: string
  download_url?: string
  references?: any[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  agent_type?: string
  celery_task_id?: string
  download_url?: string
  references?: any[]
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  user_id?: string
  thread_id?: string
  status: string
  summary?: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationDetail {
  conversation: Conversation
  messages: Message[]
}

export interface SkillItem {
  name: string
  description: string
  category: string
  tags: string[]
  enabled: boolean
  version?: string
  fallback_to_rag?: boolean
}

export interface SkillStats {
  total_skills: number
  enabled_skills: number
  disabled_skills: number
  categories: Record<string, number>
  skills?: Array<{ name: string; category: string; enabled: boolean }>
}

export const chatApi = {
  sendMessage: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chat/', data)
    return response.data
  },
  uploadFile: async (data: ChatUploadRequest): Promise<ChatUploadResponse> => {
    const response = await api.post<ChatUploadResponse>('/chat/upload/', data)
    return response.data
  },
  getHealth: async () => {
    const response = await api.get('/health/')
    return response.data
  },
  getTaskStatus: async (taskId: string) => {
    const response = await api.get(`/tasks/${taskId}/`)
    return response.data
  }
}

export const conversationApi = {
  createConversation: async (data: { title?: string; user_id?: string } = {}): Promise<Conversation> => {
    const response = await api.post<Conversation>('/conversations/', data)
    return response.data
  },
  getConversations: async (params: { user_id?: string; limit?: number; offset?: number } = {}): Promise<Conversation[]> => {
    const response = await api.get<Conversation[]>('/conversations/', { params })
    return response.data
  },
  getConversation: async (id: string): Promise<ConversationDetail> => {
    const response = await api.get<ConversationDetail>(`/conversations/${id}/`)
    return response.data
  },
  updateConversation: async (id: string, data: { title?: string; status?: string; summary?: string }): Promise<Conversation> => {
    const response = await api.put<Conversation>(`/conversations/${id}/`, data)
    return response.data
  },
  deleteConversation: async (id: string): Promise<void> => {
    await api.delete(`/conversations/${id}/`)
  },
  addMessage: async (conversationId: string, data: {
    role: string
    content: string
    agent_type?: string
    celery_task_id?: string
    download_url?: string
    references?: any[]
  }): Promise<Message> => {
    const response = await api.post<Message>(`/conversations/${conversationId}/messages/`, data)
    return response.data
  },
  summarizeConversation: async (conversationId: string): Promise<{ conversation_id: string; title: string; summary: string }> => {
    const response = await api.post(`/conversations/${conversationId}/summarize/`)
    return response.data
  }
}

export const authApi = {
  login: async (username: string, password: string) => {
    const response = await api.post('/auth/login/', { username, password })
    return response.data as { access: string; refresh: string; user: { id: number; username: string; email: string } }
  }
}

export const skillApi = {
  list: async (): Promise<SkillItem[]> => {
    const response = await api.get<SkillItem[]>('/skills/')
    return response.data
  },
  getStats: async (): Promise<SkillStats> => {
    const response = await api.get<SkillStats>('/skills/stats/')
    return response.data
  },
  create: async (data: Record<string, unknown>) => {
    const response = await api.post('/skills/', data)
    return response.data
  },
  toggle: async (name: string, enabled: boolean) => {
    const response = await api.patch(`/skills/${name}/toggle/`, { enabled })
    return response.data
  },
  reload: async (name: string) => {
    const response = await api.post(`/skills/${name}/reload/`)
    return response.data
  },
  getContent: async (name: string): Promise<{ name: string; content: string }> => {
    const response = await api.get<{ name: string; content: string }>(`/skills/${name}/content/`)
    return response.data
  },
  saveContent: async (name: string, content: string) => {
    const response = await api.put(`/skills/${name}/content/`, { content })
    return response.data
  },
  listFiles: async (name: string): Promise<{ files: Record<string, string[]> }> => {
    const response = await api.get<{ files: Record<string, string[]> }>(`/skills/${name}/files/`)
    return response.data
  },
  uploadFile: async (
    name: string,
    data: { folder: string; filename: string; file_content: string }
  ) => {
    const response = await api.post(`/skills/${name}/files/`, data)
    return response.data
  },
  delete: async (name: string) => {
    const response = await api.delete(`/skills/${name}/`)
    return response.data
  },
}

export const wsApi = {
  connectChat: (threadId?: string): WebSocket => {
    return new WebSocket(getChatWebSocketUrl(threadId))
  }
}
