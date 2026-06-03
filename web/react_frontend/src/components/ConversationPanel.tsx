// SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from 'react'
import { Button, Typography, message, Spin, Popconfirm, Tooltip } from 'antd'
import {
  PlusOutlined,
  MessageOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useChatStore, Conversation } from '../store/useChatStore'

const { Text } = Typography

interface ConversationPanelProps {
  onClose?: () => void
  /** 保留参数兼容；品牌信息已移至主导航 */
  showBrand?: boolean
}

const ConversationPanel: React.FC<ConversationPanelProps> = ({ onClose }) => {
  const {
    conversations,
    currentConversationId,
    setCurrentConversation,
    loadConversations,
    loadConversationDetail,
    deleteConversation,
    loading,
  } = useChatStore()

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)

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
    <div className="conversation-panel">
      <div className="conversation-panel-toolbar">
        <Button
          type="default"
          icon={<PlusOutlined />}
          block
          className="conversation-new-btn"
          onClick={handleNewConversation}
        >
          新对话
        </Button>
        <Tooltip title="刷新列表">
          <Button
            type="text"
            icon={<ReloadOutlined />}
            onClick={loadConversations}
            loading={loading}
            className="conversation-refresh-btn"
          />
        </Tooltip>
      </div>

      <div className="conversation-panel-list">
        <Text className="conversation-panel-label">最近</Text>
        {loading && conversations.length === 0 ? (
          <div className="conversation-panel-loading">
            <Spin size="small" />
          </div>
        ) : conversations.length === 0 ? (
          <Text type="secondary" className="conversation-panel-empty">
            暂无对话，点击上方开始
          </Text>
        ) : (
          <ul className="conversation-history">
            {conversations.map((conv) => {
              const active = conv.id === currentConversationId
              return (
                <li
                  key={conv.id}
                  className={`conversation-history-item${active ? ' is-active' : ''}`}
                  onMouseEnter={() => setHoverId(conv.id)}
                  onMouseLeave={() => setHoverId(null)}
                  onClick={() => handleSelectConversation(conv)}
                >
                  <MessageOutlined className="conversation-history-icon" />
                  <div className="conversation-history-body">
                    <span className="conversation-history-title">{conv.title}</span>
                    {conv.updatedAt && (
                      <span className="conversation-history-time">{formatDate(conv.updatedAt)}</span>
                    )}
                  </div>
                  {(hoverId === conv.id || active) && (
                    <Popconfirm
                      title="删除此对话？"
                      onConfirm={() => handleDeleteConversation(conv.id)}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        className="conversation-history-delete"
                        icon={<DeleteOutlined />}
                        loading={deletingId === conv.id}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

export default ConversationPanel
