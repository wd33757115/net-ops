import React from 'react'
import { Avatar, Typography, Tag } from 'antd'
import { UserOutlined, RobotOutlined } from '@ant-design/icons'
import { renderAssistantContent } from '../utils/linkify'

const { Paragraph } = Typography

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  agentType?: string
  downloadUrl?: string
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, agentType }) => {
  const isUser = role === 'user'

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '24px',
      }}
    >
      {!isUser && (
        <Avatar
          icon={<RobotOutlined />}
          style={{
            backgroundColor: '#111827',
            marginRight: '12px',
          }}
        />
      )}

      <div
        style={{
          maxWidth: '70%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
        }}
      >
        <div
          style={{
            background: isUser ? '#3b82f6' : '#f1f5f9',
            color: isUser ? '#fff' : '#111827',
            padding: '12px 16px',
            borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          }}
        >
          <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
            {isUser ? content : renderAssistantContent(content)}
          </Paragraph>
        </div>

        {agentType && !isUser && (
          <Tag color="blue" style={{ fontSize: '12px', marginTop: 8 }}>
            via {agentType}
          </Tag>
        )}
      </div>

      {isUser && (
        <Avatar
          icon={<UserOutlined />}
          style={{
            backgroundColor: '#6366f1',
            marginLeft: '12px',
          }}
        />
      )}
    </div>
  )
}

export default ChatMessage
