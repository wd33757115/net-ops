import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  agentType?: string
  celeryTaskId?: string
  downloadUrl?: string
  references?: any[]
  createdAt?: string
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  status?: string
  summary?: string
  createdAt?: string
  updatedAt?: string
  messageCount?: number
}

interface ChatStore {
  currentConversationId: string | null
  conversations: Conversation[]
  uploadedFile: { name: string; path: string } | null
  loading: boolean
  error: string | null
  setCurrentConversation: (id: string) => void
  addMessage: (message: Message) => void
  createNewConversation: () => void
  setUploadedFile: (file: { name: string; path: string } | null) => void
  loadConversations: () => Promise<void>
  loadConversationDetail: (id: string) => Promise<void>
  updateConversationTitle: (id: string, title: string) => void
  deleteConversation: (id: string) => void
}

export const useChatStore = create<ChatStore>((set, get) => ({
  currentConversationId: null,
  conversations: [],
  uploadedFile: null,
  loading: false,
  error: null,
  setCurrentConversation: (id: string) => set({ currentConversationId: id }),
  addMessage: (message: Message) => set(state => {
    const convId = state.currentConversationId
    if (!convId) return state
    return {
      conversations: state.conversations.map(conv => 
        conv.id === convId
          ? { ...conv, messages: [...conv.messages, message] }
          : conv
      )
    }
  }),
  createNewConversation: async () => {
    set({ loading: true, error: null })
    try {
      const { conversationApi } = await import('../services/api')
      const newConv = await conversationApi.createConversation({ title: '新对话' })
      const conversation: Conversation = {
        id: newConv.id,
        title: newConv.title,
        messages: [],
        status: newConv.status,
        summary: newConv.summary,
        createdAt: newConv.created_at,
        updatedAt: newConv.updated_at,
        messageCount: 0
      }
      set(state => ({
        conversations: [conversation, ...state.conversations],
        currentConversationId: conversation.id
      }))
    } catch (error) {
      console.error('Failed to create conversation:', error)
      // 如果后端不可用，回退到本地创建
      const newId = `conv-${Date.now()}`
      const newConv: Conversation = {
        id: newId,
        title: '新对话',
        messages: []
      }
      set(state => ({
        conversations: [...state.conversations, newConv],
        currentConversationId: newId
      }))
    } finally {
      set({ loading: false })
    }
  },
  setUploadedFile: (file) => set({ uploadedFile: file }),
  loadConversations: async () => {
    set({ loading: true, error: null })
    try {
      const { conversationApi } = await import('../services/api')
      const data = await conversationApi.getConversations()
      const conversations: Conversation[] = data.map(c => ({
        id: c.id,
        title: c.title,
        messages: [],
        status: c.status,
        summary: c.summary,
        createdAt: c.created_at,
        updatedAt: c.updated_at,
        messageCount: c.message_count
      }))
      set({ conversations })
      if (conversations.length > 0 && !get().currentConversationId) {
        set({ currentConversationId: conversations[0].id })
      }
    } catch (error) {
      console.error('Failed to load conversations:', error)
      set({ error: '加载对话列表失败' })
    } finally {
      set({ loading: false })
    }
  },
  loadConversationDetail: async (id: string) => {
    set({ loading: true, error: null })
    try {
      const { conversationApi } = await import('../services/api')
      const data = await conversationApi.getConversation(id)
      const messages: Message[] = data.messages.map(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        agentType: m.agent_type,
        celeryTaskId: m.celery_task_id,
        downloadUrl: m.download_url,
        references: m.references,
        createdAt: m.created_at
      }))
      set(state => ({
        conversations: state.conversations.map(conv =>
          conv.id === id
            ? { ...conv, messages, title: data.conversation.title }
            : conv
        ),
        currentConversationId: id
      }))
    } catch (error) {
      console.error('Failed to load conversation detail:', error)
      set({ error: '加载对话详情失败' })
    } finally {
      set({ loading: false })
    }
  },
  updateConversationTitle: (id: string, title: string) => set(state => ({
    conversations: state.conversations.map(conv =>
      conv.id === id ? { ...conv, title } : conv
    )
  })),
  deleteConversation: (id: string) => set(state => ({
    conversations: state.conversations.filter(conv => conv.id !== id),
    currentConversationId: state.currentConversationId === id 
      ? state.conversations.find(c => c.id !== id)?.id || null 
      : state.currentConversationId
  }))
}))
