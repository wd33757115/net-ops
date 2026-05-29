import { api, getChatWebSocketUrl, type AuthSession } from '../config/api'

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

export type ServiceCheckStatus = 'ok' | 'degraded' | 'down' | 'skipped'

export interface ServiceCheck {
  id: string
  name: string
  status: ServiceCheckStatus
  message: string
  latency_ms?: number | null
  detail?: Record<string, unknown> | null
}

export interface DiagnosticsResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  summary: string
  checks: ServiceCheck[]
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

export interface KnowledgeDocument {
  id: string
  file_name: string
  relative_path: string
  size_bytes: number
  updated_at: string
  doc_type: string
  category: string
  indexed: boolean
  chunk_count: number
}

export interface KnowledgeStats {
  document_count: number
  indexed_document_count: number
  indexed_chunks: number
  kb_path: string
  vector_store: string
  collection: string
  supported_extensions?: string[]
}

export interface KnowledgeReindexResponse {
  success: boolean
  document_count?: number
  chunk_count?: number
  message?: string
}

export interface KnowledgeDocumentPreview {
  success: boolean
  id: string
  file_name: string
  relative_path: string
  size_bytes: number
  preview_type: 'text' | 'extracted' | 'binary'
  content_type: string
  content: string
  download_base64?: string
  truncated?: boolean
  message?: string
}

export interface KnowledgeUploadRequest {
  filename: string
  file_content: string
  folder?: string
  relative_path?: string
  auto_reindex?: boolean
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
  getDiagnostics: async (): Promise<DiagnosticsResponse> => {
    const response = await api.get<DiagnosticsResponse>('/health/diagnostics/')
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

export interface AuthUser {
  id: number
  username: string
  email: string
  role: string
  thread_id?: string
}

export interface ManagedUser {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
  last_login: string | null
  date_joined: string | null
}

export const authApi = {
  login: async (username: string, password: string) => {
    const response = await api.post('/auth/login/', { username, password })
    return response.data as AuthSession & { user: AuthUser }
  },
  refresh: async (refresh: string) => {
    const response = await api.post('/auth/refresh/', { refresh })
    return response.data as { access: string; refresh?: string }
  },
  logout: async () => {
    const refresh = localStorage.getItem('refresh_token')
    await api.post('/auth/logout/', refresh ? { refresh } : {})
  },
  changePassword: async (old_password: string, new_password: string) => {
    const response = await api.post('/auth/change-password/', { old_password, new_password })
    return response.data as { message: string }
  },
  me: async () => {
    const response = await api.get('/auth/me/')
    return response.data as AuthUser
  },
}

export const userAdminApi = {
  list: async (): Promise<ManagedUser[]> => {
    const response = await api.get<ManagedUser[]>('/auth/users/')
    return response.data
  },
  create: async (data: { username: string; password: string; role: string; email?: string }) => {
    const response = await api.post<ManagedUser>('/auth/users/', data)
    return response.data
  },
  update: async (
    id: number,
    data: Partial<Pick<ManagedUser, 'email' | 'role' | 'is_active'>>
  ) => {
    const response = await api.patch<ManagedUser>(`/auth/users/${id}/`, data)
    return response.data
  },
  resetPassword: async (id: number, new_password: string) => {
    const response = await api.post(`/auth/users/${id}/reset-password/`, { new_password })
    return response.data as { message: string }
  },
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

export const knowledgeApi = {
  listDocuments: async (): Promise<KnowledgeDocument[]> => {
    const response = await api.get<KnowledgeDocument[]>('/knowledge/documents/')
    return response.data
  },
  getStats: async (): Promise<KnowledgeStats> => {
    const response = await api.get<KnowledgeStats>('/knowledge/stats/')
    return response.data
  },
  reindex: async (): Promise<KnowledgeReindexResponse> => {
    const response = await api.post<KnowledgeReindexResponse>('/knowledge/reindex/')
    return response.data
  },
  getPreview: async (relativePath: string): Promise<KnowledgeDocumentPreview> => {
    const path = encodeKnowledgePath(relativePath)
    const response = await api.get<KnowledgeDocumentPreview>(`/knowledge/documents/${path}/content/`)
    return response.data
  },
  upload: async (data: KnowledgeUploadRequest) => {
    const response = await api.post('/knowledge/documents/', data)
    return response.data
  },
  delete: async (relativePath: string, autoReindex = true) => {
    const path = encodeKnowledgePath(relativePath)
    const response = await api.delete(`/knowledge/documents/${path}/`, {
      params: { auto_reindex: autoReindex },
    })
    return response.data
  },
}

function encodeKnowledgePath(relativePath: string): string {
  return relativePath.split('/').map(encodeURIComponent).join('/')
}

export interface StorageFolder {
  id: string
  name: string
  parent_id: string | null
  visibility: string
  team_id: string | null
  owner_id: string | null
  created_at?: string
  updated_at?: string
}

export interface StorageFile {
  id: string
  name: string
  folder_id: string | null
  visibility: string
  team_id: string | null
  owner_id: string | null
  content_type: string | null
  size_bytes: number
  created_at?: string
  updated_at?: string
}

export interface StorageListResult {
  folder: StorageFolder | null
  folders: StorageFolder[]
  files: StorageFile[]
  breadcrumb: StorageFolder[]
}

export interface StorageTeam {
  id: string
  name: string
  description: string | null
  role: string | null
  member_count: number
}

export interface StorageTeamMember {
  id: string
  user_id: string
  role: string
  created_at?: string
}

export interface UploadInitResult {
  file_id: string
  object_key: string
  upload_url: string
  expires_in: number
}

export const storageApi = {
  listTeams: async (): Promise<StorageTeam[]> => {
    const response = await api.get<StorageTeam[]>('/storage/teams/')
    return response.data
  },
  createTeam: async (data: { name: string; description?: string }) => {
    const response = await api.post('/storage/teams/', data)
    return response.data
  },
  deleteTeam: async (teamId: string) => {
    const response = await api.delete(`/storage/teams/${teamId}/`)
    return response.data
  },
  listTeamMembers: async (teamId: string): Promise<StorageTeamMember[]> => {
    const response = await api.get<StorageTeamMember[]>(`/storage/teams/${teamId}/members/`)
    return response.data
  },
  addTeamMember: async (teamId: string, data: { user_id: string; role?: string }) => {
    const response = await api.post(`/storage/teams/${teamId}/members/`, data)
    return response.data
  },
  removeTeamMember: async (teamId: string, userId: string) => {
    const response = await api.delete(`/storage/teams/${teamId}/members/${userId}/`)
    return response.data
  },
  updateTeamMemberRole: async (teamId: string, userId: string, role: string) => {
    const response = await api.patch(`/storage/teams/${teamId}/members/${userId}/`, { role })
    return response.data
  },
  list: async (params: { folder_id?: string; visibility?: string; team_id?: string }): Promise<StorageListResult> => {
    const response = await api.get<StorageListResult>('/storage/list/', { params })
    return response.data
  },
  folderTree: async (params: { visibility?: string; team_id?: string }) => {
    const response = await api.get('/storage/folders/tree/', { params })
    return response.data
  },
  createFolder: async (data: {
    name: string
    parent_id?: string | null
    visibility?: string
    team_id?: string | null
  }) => {
    const response = await api.post('/storage/folders/', data)
    return response.data
  },
  deleteFolder: async (folderId: string) => {
    const response = await api.delete(`/storage/folders/${folderId}/`)
    return response.data
  },
  renameFolder: async (folderId: string, name: string) => {
    const response = await api.patch(`/storage/folders/${folderId}/`, { name })
    return response.data
  },
  moveFolder: async (folderId: string, targetFolderId: string) => {
    const response = await api.post(`/storage/folders/${folderId}/move/`, { target_folder_id: targetFolderId })
    return response.data
  },
  uploadInit: async (data: {
    filename: string
    folder_id?: string | null
    visibility?: string
    team_id?: string | null
    content_type?: string
    size_bytes?: number
  }): Promise<UploadInitResult> => {
    const response = await api.post<UploadInitResult>('/storage/upload/init/', data)
    return response.data
  },
  uploadComplete: async (data: { file_id: string; size_bytes?: number }) => {
    const response = await api.post('/storage/upload/complete/', data)
    return response.data
  },
  download: async (fileId: string): Promise<{ download_url: string; filename: string }> => {
    const response = await api.get<{ download_url: string; filename: string }>(`/storage/files/${fileId}/download/`)
    return response.data
  },
  deleteFile: async (fileId: string) => {
    const response = await api.delete(`/storage/files/${fileId}/`)
    return response.data
  },
  renameFile: async (fileId: string, name: string) => {
    const response = await api.patch(`/storage/files/${fileId}/`, { name })
    return response.data
  },
  moveFile: async (fileId: string, targetFolderId: string) => {
    const response = await api.post(`/storage/files/${fileId}/move/`, { target_folder_id: targetFolderId })
    return response.data
  },
  share: async (data: { file_id: string; team_id: string; target_folder_id?: string }) => {
    const response = await api.post('/storage/share/', data)
    return response.data
  },
  shareFolder: async (data: { folder_id: string; team_id: string; target_folder_id?: string }) => {
    const response = await api.post('/storage/share/folder/', data)
    return response.data
  },
}

export const wsApi = {
  connectChat: (threadId?: string): WebSocket => {
    return new WebSocket(getChatWebSocketUrl(threadId))
  }
}
