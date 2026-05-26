import React, { useState } from 'react'
import { Layout, Button, List, Typography, Upload, message, Spin, Popconfirm } from 'antd'
import { PlusOutlined, FileTextOutlined, FolderOpenOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { useChatStore, Conversation } from '../store/useChatStore'
import { chatApi } from '../services/api'

const { Sider } = Layout
const { Title, Text } = Typography

const ConversationSidebar: React.FC = () => {
  const { 
    conversations, 
    currentConversationId, 
    setCurrentConversation,
    createNewConversation,
    setUploadedFile,
    loadConversations,
    loadConversationDetail,
    deleteConversation,
    loading,
  } = useChatStore()

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const handleFileUpload = (file: File) => {
    if (!currentConversationId) {
      message.warning('请先选择或创建一个对话')
      return Upload.LIST_IGNORE
    }

    setUploading(true)
    const reader = new FileReader()
    reader.onload = async () => {
      try {
        const result = reader.result as string
        const base64 = result.includes(',') ? result.split(',')[1] : result
        const uploadResult = await chatApi.uploadFile({
          thread_id: currentConversationId,
          filename: file.name,
          file_content: base64,
        })
        setUploadedFile({ name: file.name, path: uploadResult.file_path })
        message.success(uploadResult.message || `文件 ${file.name} 已上传`)
      } catch {
        message.error('文件上传失败')
      } finally {
        setUploading(false)
      }
    }
    reader.onerror = () => {
      message.error('读取文件失败')
      setUploading(false)
    }
    reader.readAsDataURL(file)
    return false
  }

  const handleSelectConversation = async (conv: Conversation) => {
    setCurrentConversation(conv.id)
    if (!conv.detailLoaded && conv.messages.length === 0 && (conv.messageCount ?? 0) > 0) {
      await loadConversationDetail(conv.id)
    }
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
          icon={<ReloadOutlined />}
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
          disabled={uploading}
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

export default ConversationSidebar
