import React, { useEffect, useState } from 'react'
import { Layout, Button, List, Typography, Upload, message, Spin, Popconfirm } from 'antd'
import { PlusOutlined, FileTextOutlined, FolderOpenOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { useChatStore, Conversation } from '../store/useChatStore'

const { Sider } = Layout
const { Title, Text } = Typography

const Sidebar: React.FC = () => {
  const { 
    conversations, 
    currentConversationId, 
    setCurrentConversation,
    createNewConversation,
    setUploadedFile,
    loadConversations,
    loadConversationDetail,
    deleteConversation,
    loading
  } = useChatStore()

  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  useEffect(() => {
    if (conversations.length === 0 && !loading) {
      useChatStore.getState().createNewConversation()
    }
  }, [conversations.length, loading])

  const handleFileUpload = (file: any) => {
    const fakePath = `/uploads/${file.name}`
    setUploadedFile({ name: file.name, path: fakePath })
    message.success(`文件 ${file.name} 已上传`)
    return false
  }

  const handleSelectConversation = async (conv: Conversation) => {
    if (conv.messages.length === 0) {
      await loadConversationDetail(conv.id)
    }
    setCurrentConversation(conv.id)
  }

  const handleDeleteConversation = async (id: string) => {
    setDeletingId(id)
    try {
      const { conversationApi } = await import('../services/api')
      await conversationApi.deleteConversation(id)
      deleteConversation(id)
      message.success('对话已删除')
    } catch (error) {
      message.error('删除失败')
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return ''
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (days === 1) {
      return '昨天'
    } else if (days < 7) {
      return `${days}天前`
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    }
  }

  return (
    <Sider 
      width={280} 
      style={{ 
        background: '#fff', 
        borderRight: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <div style={{ padding: '20px 16px' }}>
        <Title level={4} style={{ margin: 0, color: '#111827' }}>
          NetOps Agent
        </Title>
        <Text type="secondary" style={{ fontSize: '13px' }}>
          网络运维智能助手
        </Text>
      </div>

      <div style={{ padding: '0 16px 16px', display: 'flex', gap: '8px' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={() => useChatStore.getState().createNewConversation()}
          style={{
            borderRadius: '8px',
            background: '#3b82f6',
            flex: 1
          }}
        >
          新建对话
        </Button>
        <Button 
          icon={<RefreshOutlined />}
          onClick={loadConversations}
          loading={loading}
          style={{ borderRadius: '8px' }}
        />
      </div>

      <div style={{ padding: '0 16px 16px' }}>
        <Upload.Dragger 
          accept=".xlsx,.xls,.csv"
          fileList={[]}
          beforeUpload={handleFileUpload}
          showUploadList={false}
          style={{ borderRadius: '8px' }}
        >
          <p className="ant-upload-drag-icon">
            <FolderOpenOutlined style={{ fontSize: '32px', color: '#64748b' }} />
          </p>
          <p className="ant-upload-text">
            点击或拖拽上传文件
          </p>
          <p className="ant-upload-hint" style={{ fontSize: '12px' }}>
            支持 Excel、CSV 格式
          </p>
        </Upload.Dragger>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
        <Text strong style={{ display: 'block', padding: '8px 12px', fontSize: '12px', color: '#64748b' }}>
          对话历史
        </Text>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="small" />
            <Text type="secondary" style={{ display: 'block', marginTop: '8px' }}>
              加载中...
            </Text>
          </div>
        ) : (
          <List
            dataSource={conversations}
            renderItem={conv => (
              <List.Item
                style={{
                  cursor: 'pointer',
                  borderRadius: '8px',
                  padding: '10px 12px',
                  marginBottom: '4px',
                  background: conv.id === currentConversationId ? '#eff6ff' : 'transparent',
                  borderLeft: conv.id === currentConversationId ? '3px solid #3b82f6' : '3px solid transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
                onClick={() => handleSelectConversation(conv)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                  <FileTextOutlined style={{ color: '#64748b', fontSize: '16px' }} />
                  <div style={{ overflow: 'hidden' }}>
                    <Text style={{ fontSize: '14px', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {conv.title}
                    </Text>
                    {conv.updatedAt && (
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {formatDate(conv.updatedAt)}
                      </Text>
                    )}
                  </div>
                </div>
                <Popconfirm
                  title="确定删除这个对话吗？"
                  onConfirm={() => handleDeleteConversation(conv.id)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button
                    type="text"
                    icon={<DeleteOutlined />}
                    style={{ 
                      color: '#ef4444',
                      padding: '4px',
                      marginLeft: '8px',
                      display: conv.id === currentConversationId ? 'none' : 'block'
                    }}
                    onClick={(e) => e.stopPropagation()}
                    loading={deletingId === conv.id}
                  />
                </Popconfirm>
              </List.Item>
            )}
          />
        )}
      </div>
    </Sider>
  )
}

export default Sidebar
