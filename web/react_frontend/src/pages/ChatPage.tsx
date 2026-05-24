import React, { useState, useRef, useEffect } from 'react'
import { Layout, Typography, Spin, message } from 'antd'
import { useMutation } from 'react-query'
import Sidebar from '../components/Sidebar'
import ChatMessage from '../components/ChatMessage'
import InputArea from '../components/InputArea'
import { useChatStore } from '../store/useChatStore'
import { chatApi, ChatResponse, conversationApi } from '../services/api'

const { Header, Content } = Layout
const { Title, Text } = Typography

const ChatPage: React.FC = () => {
  const [threadId, setThreadId] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)
  
  const { 
    currentConversationId, 
    conversations, 
    addMessage,
    uploadedFile,
    updateConversationTitle,
    loadConversationDetail,
    loadConversations,
    createNewConversation
  } = useChatStore()

  const currentConversation = conversations.find(
    c => c.id === currentConversationId
  )

  const currentMessages = currentConversation?.messages || []

  // 页面加载时初始化
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true
      // 加载对话列表
      loadConversations().then(() => {
        // 如果没有当前对话，创建一个新对话
        const state = useChatStore.getState()
        if (!state.currentConversationId) {
          useChatStore.getState().createNewConversation()
        }
      })
    }
  }, [loadConversations])

  // 当切换对话时，加载对话详情
  useEffect(() => {
    if (currentConversationId && (!currentConversation || currentConversation.messages.length === 0)) {
      loadConversationDetail(currentConversationId)
    }
  }, [currentConversationId, currentConversation, loadConversationDetail])

  useEffect(() => {
    if (currentConversationId) {
      setThreadId(currentConversationId)
    }
  }, [currentConversationId])

  const sendMessageMutation = useMutation<ChatResponse, Error, string>({
    mutationFn: async (query) => {
      // 确保有当前对话
      let convId = currentConversationId
      if (!convId) {
        const newConv = await conversationApi.createConversation({ title: '新对话' })
        convId = newConv.id
        setThreadId(convId)
        // 更新store中的当前对话
        useChatStore.setState(state => ({
          conversations: [{ id: newConv.id, title: newConv.title, messages: [] }, ...state.conversations],
          currentConversationId: newConv.id
        }))
      }

      const response = await chatApi.sendMessage({
        query,
        thread_id: convId || undefined,
        uploaded_file_path: uploadedFile?.path
      })
      return response
    },
    onMutate: async (query) => {
      // 添加用户消息到本地状态
      addMessage({
        id: `user-${Date.now()}`,
        role: 'user',
        content: query
      })
    },
    onSuccess: async (data) => {
      // 添加助手消息到本地状态
      addMessage({
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response,
        agentType: data.agent_type,
        celeryTaskId: data.celery_task_id,
        downloadUrl: data.download_url,
        references: data.references
      })

      if (data.thread_id !== threadId) {
        setThreadId(data.thread_id)
      }

      // 刷新对话列表以获取更新后的标题
      loadConversations()
    },
    onError: (error) => {
      message.error(`发送失败: ${error.message}`)
    }
  })

  const handleSend = (text: string) => {
    if (!currentConversationId) {
      message.error('请先选择或创建一个对话')
      return
    }
    sendMessageMutation.mutate(text)
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [currentMessages])

  return (
    <Layout style={{ height: '100vh' }}>
      <Sidebar />
      
      <Layout style={{ display: 'flex', flexDirection: 'column' }}>
        <Header style={{ 
          background: '#fff', 
          borderBottom: '1px solid #e5e7eb',
          padding: '0 24px',
          height: '64px',
          display: 'flex',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <Title level={4} style={{ margin: 0, color: '#111827' }}>
              {currentConversation?.title || '网络运维智能助手'}
            </Title>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              AI 驱动的网络运维平台 · Supervisor + RAG + 技能系统
            </Text>
          </div>
        </Header>

        <Content style={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column',
          background: '#f8fafc',
          overflow: 'hidden'
        }}>
          <div style={{ 
            flex: 1, 
            overflowY: 'auto', 
            padding: '24px',
            paddingBottom: '120px'
          }}>
            {currentMessages.length === 0 && !sendMessageMutation.isLoading && (
              <div style={{ 
                textAlign: 'center', 
                padding: '60px 24px',
                color: '#64748b'
              }}>
                <Title level={3} style={{ marginBottom: '16px', color: '#111827' }}>
                  欢迎使用 NetOps Agent
                </Title>
                <Text style={{ fontSize: '15px', display: 'block', marginBottom: '24px' }}>
                  您可以问我关于网络配置、设备巡检、故障排查等问题
                </Text>
                <div style={{ 
                  maxWidth: '600px', 
                  margin: '0 auto',
                  textAlign: 'left'
                }}>
                  <div style={{ 
                    background: '#fff', 
                    padding: '16px', 
                    borderRadius: '12px',
                    marginBottom: '12px',
                    border: '1px solid #e5e7eb',
                    cursor: 'pointer'
                  }} onClick={() => handleSend('备份生产环境设备配置')}>
                    <Text style={{ fontSize: '14px' }}>
                      💾 设备备份："备份生产环境设备配置"
                    </Text>
                  </div>
                  <div style={{ 
                    background: '#fff', 
                    padding: '16px', 
                    borderRadius: '12px',
                    marginBottom: '12px',
                    border: '1px solid #e5e7eb',
                    cursor: 'pointer'
                  }} onClick={() => handleSend('对 prod 分组执行设备巡检')}>
                    <Text style={{ fontSize: '14px' }}>
                      🔍 设备巡检："对 prod 分组执行设备巡检"
                    </Text>
                  </div>
                  <div style={{ 
                    background: '#fff', 
                    padding: '16px', 
                    borderRadius: '12px',
                    border: '1px solid #e5e7eb',
                    cursor: 'pointer'
                  }} onClick={() => handleSend('交换机端口 Down 了如何排查？')}>
                    <Text style={{ fontSize: '14px' }}>
                      ❓ 知识问答："交换机端口 Down 了如何排查？"
                    </Text>
                  </div>
                </div>
              </div>
            )}

            {currentMessages.map(msg => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                agentType={msg.agentType}
                downloadUrl={msg.downloadUrl}
              />
            ))}

            {sendMessageMutation.isLoading && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                padding: '20px 0' 
              }}>
                <Spin size="small" />
                <Text style={{ marginLeft: '12px', color: '#64748b' }}>
                  Agent 正在思考中...
                </Text>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <InputArea 
            onSend={handleSend}
            loading={sendMessageMutation.isLoading}
          />
        </Content>
      </Layout>
    </Layout>
  )
}

export default ChatPage