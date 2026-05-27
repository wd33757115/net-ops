import React, { useState } from 'react'
import { Button, List, Typography, Upload, message, Spin, Popconfirm } from 'antd'
import { PlusOutlined, FileTextOutlined, FolderOpenOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { useChatStore, Conversation } from '../store/useChatStore'
import { chatApi } from '../services/api'

const { Title, Text } = Typography

interface ConversationPanelProps {
  /** 手机端选中对话或新建后关闭抽屉 */
  onClose?: () => void
  /** 是否显示顶部品牌区（桌面侧栏内显示，手机抽屉内可省略） */
  showBrand?: boolean
}

const ConversationPanel: React.FC<ConversationPanelProps> = ({
  onClose,
  showBrand = true,
}) => {
  const {
    conversations,
    currentConversationId,
    setCurrentConversation,
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
    onClose?.()
  }

  const handleNewConversation = async () => {
    await useChatStore.getState().createNewConversation()
    onClose?.()
  }

  const handleDeleteConversation = async (id: string) => {
    setDeletingId(id)
    try {
      const { conversationApi } = await import('../services/api')
      await conversationApi.deleteConversation(id)
      deleteConversation(id)
      message.success('对话已删除')
    } catch {
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
    }
    if (days === 1) return '昨天'
    if (days < 7) return `${days}天前`
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#fff',
      }}
    >
      {showBrand && (
        <div style={{ padding: '16px 16px 8px' }}>
          <Title level={4} style={{ margin: 0, color: '#111827' }}>
            对话与文件
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            网络运维智能助手
          </Text>
        </div>
      )}

      <div style={{ padding: '0 16px 12px', display: 'flex', gap: 8 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={handleNewConversation}
          style={{ borderRadius: 8, background: '#3b82f6', flex: 1 }}
        >
          新建对话
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={loadConversations}
          loading={loading}
          style={{ borderRadius: 8 }}
        />
      </div>

      <div style={{ padding: '0 16px 12px' }}>
        <Upload.Dragger
          accept=".xlsx,.xls,.csv"
          fileList={[]}
          beforeUpload={handleFileUpload}
          showUploadList={false}
          disabled={uploading}
          style={{ borderRadius: 8 }}
        >
          <p className="ant-upload-drag-icon">
            <FolderOpenOutlined style={{ fontSize: 28, color: '#64748b' }} />
          </p>
          <p className="ant-upload-text" style={{ fontSize: 13 }}>
            点击或拖拽上传文件
          </p>
          <p className="ant-upload-hint" style={{ fontSize: 12 }}>
            支持 Excel、CSV 格式
          </p>
        </Upload.Dragger>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px 16px', minHeight: 0 }}>
        <Text strong style={{ display: 'block', padding: '8px 12px', fontSize: 12, color: '#64748b' }}>
          对话历史
        </Text>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <Spin size="small" />
          </div>
        ) : (
          <List
            dataSource={conversations}
            renderItem={(conv) => (
              <List.Item
                style={{
                  cursor: 'pointer',
                  borderRadius: 8,
                  padding: '10px 12px',
                  marginBottom: 4,
                  background: conv.id === currentConversationId ? '#eff6ff' : 'transparent',
                  borderLeft:
                    conv.id === currentConversationId ? '3px solid #3b82f6' : '3px solid transparent',
                }}
                onClick={() => handleSelectConversation(conv)}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  <FileTextOutlined style={{ color: '#64748b', fontSize: 16, flexShrink: 0 }} />
                  <div style={{ overflow: 'hidden', flex: 1 }}>
                    <Text
                      style={{
                        fontSize: 14,
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {conv.title}
                    </Text>
                    {conv.updatedAt && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
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
                    style={{ color: '#ef4444', padding: 4, flexShrink: 0 }}
                    onClick={(e) => e.stopPropagation()}
                    loading={deletingId === conv.id}
                  />
                </Popconfirm>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  )
}

export default ConversationPanel
