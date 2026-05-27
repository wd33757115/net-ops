import React, { useState, useRef, useEffect } from 'react'
import { Layout, Typography, Spin, message, Drawer, Button } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import { useMutation } from 'react-query'
import ConversationSidebar from '../components/ConversationSidebar'
import ConversationPanel from '../components/ConversationPanel'
import ChatMessage from '../components/ChatMessage'
import InputArea from '../components/InputArea'
import { useChatStore } from '../store/useChatStore'
import { chatApi, ChatResponse, conversationApi } from '../services/api'
import { useIsMobile } from '../hooks/useIsMobile'

const { Header, Content } = Layout
const { Title, Text } = Typography

const ChatPage: React.FC = () => {
  const isMobile = useIsMobile()
  const [convDrawerOpen, setConvDrawerOpen] = useState(false)
  const [threadId, setThreadId] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)

  const {
    currentConversationId,
    conversations,
    addMessage,
    uploadedFile,
    loadConversationDetail,
    loadConversations,
  } = useChatStore()

  const currentConversation = conversations.find((c) => c.id === currentConversationId)
  const currentMessages = currentConversation?.messages || []

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true
      loadConversations().then(() => {
        const state = useChatStore.getState()
        if (!state.currentConversationId) {
          useChatStore.getState().createNewConversation()
        }
      })
    }
  }, [loadConversations])

  useEffect(() => {
    if (!currentConversationId) return
    const conv = conversations.find((c) => c.id === currentConversationId)
    if (!conv || conv.detailLoaded || conv.messages.length > 0) return
    loadConversationDetail(currentConversationId)
  }, [currentConversationId, conversations, loadConversationDetail])

  useEffect(() => {
    if (currentConversationId) {
      setThreadId(currentConversationId)
    }
  }, [currentConversationId])

  const sendMessageMutation = useMutation<ChatResponse, Error, string>({
    mutationFn: async (query) => {
      let convId = currentConversationId
      if (!convId) {
        const newConv = await conversationApi.createConversation({ title: '新对话' })
        convId = newConv.id
        setThreadId(convId)
        useChatStore.setState((state) => ({
          conversations: [
            { id: newConv.id, title: newConv.title, messages: [], detailLoaded: true },
            ...state.conversations,
          ],
          currentConversationId: newConv.id,
        }))
      }

      return chatApi.sendMessage({
        query,
        thread_id: convId || undefined,
        uploaded_file_path: uploadedFile?.path,
      })
    },
    onMutate: async (query) => {
      addMessage({
        id: `user-${Date.now()}`,
        role: 'user',
        content: query,
      })
    },
    onSuccess: async (data) => {
      addMessage({
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response,
        agentType: data.agent_type,
        celeryTaskId: data.celery_task_id,
        downloadUrl: data.download_url,
        references: data.references,
      })

      if (data.thread_id !== threadId) {
        setThreadId(data.thread_id)
      }

      loadConversations()
    },
    onError: (error) => {
      message.error(`发送失败: ${error.message}`)
    },
  })

  const handleSend = (text: string) => {
    if (!currentConversationId) {
      message.error('请先选择或创建一个对话')
      return
    }
    sendMessageMutation.mutate(text)
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentMessages])

  const drawerWidth = Math.min(300, typeof window !== 'undefined' ? window.innerWidth * 0.88 : 300)

  return (
    <Layout style={{ height: '100%', minWidth: 0 }}>
      {!isMobile && <ConversationSidebar />}

      <Drawer
        title="对话与文件"
        placement="left"
        open={isMobile && convDrawerOpen}
        onClose={() => setConvDrawerOpen(false)}
        width={drawerWidth}
        styles={{ body: { padding: 0 } }}
        className="conversation-drawer"
      >
        <ConversationPanel showBrand={false} onClose={() => setConvDrawerOpen(false)} />
      </Drawer>

      <Layout style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
        <Header
          className="chat-page-header"
          style={{
            background: '#fff',
            borderBottom: '1px solid #e5e7eb',
            padding: isMobile ? '0 12px' : '0 24px',
            height: isMobile ? 52 : 64,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
          }}
        >
          {isMobile && (
            <Button
              type="text"
              icon={<MenuOutlined />}
              aria-label="打开对话列表"
              onClick={() => setConvDrawerOpen(true)}
            />
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <Title
              level={isMobile ? 5 : 4}
              style={{
                margin: 0,
                color: '#111827',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {currentConversation?.title || '网络运维智能助手'}
            </Title>
            {!isMobile && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                AI 驱动的网络运维平台 · Supervisor + RAG + 技能系统
              </Text>
            )}
          </div>
        </Header>

        <Content
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            background: '#f8fafc',
            overflow: 'hidden',
            minHeight: 0,
          }}
        >
          <div
            className="chat-messages-scroll"
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: isMobile ? '12px' : '24px',
              paddingBottom: isMobile ? 100 : 120,
              WebkitOverflowScrolling: 'touch',
            }}
          >
            {currentMessages.length === 0 && !sendMessageMutation.isLoading && (
              <div style={{ textAlign: 'center', padding: isMobile ? '24px 8px' : '60px 24px', color: '#64748b' }}>
                <Title level={isMobile ? 4 : 3} style={{ marginBottom: 12, color: '#111827' }}>
                  欢迎使用 NetOps Agent
                </Title>
                <Text style={{ fontSize: 14, display: 'block', marginBottom: 16 }}>
                  您可以问我关于网络配置、设备巡检、故障排查等问题
                </Text>
                <div style={{ maxWidth: 600, margin: '0 auto', textAlign: 'left' }}>
                  {[
                    { label: '💾 设备备份', text: '备份生产环境设备配置' },
                    { label: '🔍 设备巡检', text: '对 prod 分组执行设备巡检' },
                    { label: '❓ 知识问答', text: '交换机端口 Down 了如何排查？' },
                  ].map((item) => (
                    <div
                      key={item.text}
                      style={{
                        background: '#fff',
                        padding: isMobile ? 12 : 16,
                        borderRadius: 12,
                        marginBottom: 10,
                        border: '1px solid #e5e7eb',
                        cursor: 'pointer',
                      }}
                      onClick={() => handleSend(item.text)}
                    >
                      <Text style={{ fontSize: 14 }}>
                        {item.label}："{item.text}"
                      </Text>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {currentMessages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                agentType={msg.agentType}
                downloadUrl={msg.downloadUrl}
                compact={isMobile}
              />
            ))}

            {sendMessageMutation.isLoading && (
              <div style={{ display: 'flex', alignItems: 'center', padding: '16px 0' }}>
                <Spin size="small" />
                <Text style={{ marginLeft: 12, color: '#64748b' }}>Agent 正在思考中...</Text>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <InputArea onSend={handleSend} loading={sendMessageMutation.isLoading} compact={isMobile} />
        </Content>
      </Layout>
    </Layout>
  )
}

export default ChatPage
