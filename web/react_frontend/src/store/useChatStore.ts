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
  detailLoaded?: boolean
}

interface ChatStore {
  currentConversationId: string | null
  conversations: Conversation[]
  uploadedFile: { name: string; path: string } | null
  loading: boolean
  detailLoadingId: string | null
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

const detailInflight = new Map<string, Promise<void>>()

export const useChatStore = create<ChatStore>((set, get) => ({
  currentConversationId: null,
  conversations: [],
  uploadedFile: null,
  loading: false,
  detailLoadingId: null,
  error: null,
  setCurrentConversation: (id: string) => set({ currentConversationId: id }),
  addMessage: (message: Message) => set(state => {
    const convId = state.currentConversationId
    if (!convId) return state
    return {
      conversations: state.conversations.map(conv =>
        conv.id === convId
          ? { ...conv, messages: [...conv.messages, message], detailLoaded: true }
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
        messageCount: 0,
        detailLoaded: true,
      }
      set(state => ({
        conversations: [conversation, ...state.conversations],
        currentConversationId: conversation.id
      }))
    } catch (error) {
      console.error('Failed to create conversation:', error)
      const newId = `conv-${Date.now()}`
      const newConv: Conversation = {
        id: newId,
        title: '新对话',
        messages: [],
        detailLoaded: true,
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
    if (get().loading) return
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
        messageCount: c.message_count,
        detailLoaded: (c.message_count ?? 0) === 0,
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
    const existing = get().conversations.find(c => c.id === id)
    if (existing?.detailLoaded) return
    if ((existing?.messageCount ?? 0) === 0) {
      set(state => ({
        conversations: state.conversations.map(conv =>
          conv.id === id ? { ...conv, detailLoaded: true } : conv
        ),
      }))
      return
    }
    const inflight = detailInflight.get(id)
    if (inflight) return inflight

    const task = (async () => {
      set({ detailLoadingId: id, error: null })
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
              ? { ...conv, messages, title: data.conversation.title, detailLoaded: true }
              : conv
          ),
        }))
      } catch (error) {
        console.error('Failed to load conversation detail:', error)
        set(state => ({
          error: '加载对话详情失败',
          conversations: state.conversations.map(conv =>
            conv.id === id ? { ...conv, detailLoaded: true } : conv
          ),
        }))
      } finally {
        detailInflight.delete(id)
        set(state => ({
          detailLoadingId: state.detailLoadingId === id ? null : state.detailLoadingId
        }))
      }
    })()

    detailInflight.set(id, task)
    return task
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
