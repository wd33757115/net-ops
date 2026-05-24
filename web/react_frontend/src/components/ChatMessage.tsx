import React from 'react'
import { Avatar, Typography, Tag, Button, Space } from 'antd'
import { UserOutlined, RobotOutlined, DownloadOutlined } from '@ant-design/icons'

const { Text, Paragraph } = Typography

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  agentType?: string
  downloadUrl?: string
}

const ChatMessage: React.FC<ChatMessageProps> = ({ 
  role, 
  content, 
  agentType, 
  downloadUrl 
}) => {
  const isUser = role === 'user'

  return (
    <div 
      style={{ 
        display: 'flex', 
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '24px'
      }}
    >
      {!isUser && (
        <Avatar 
          icon={<RobotOutlined />} 
          style={{ 
            backgroundColor: '#111827',
            marginRight: '12px'
          }}
        />
      )}

      <div style={{ 
        maxWidth: '70%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start'
      }}>
        <div
          style={{
            background: isUser ? '#3b82f6' : '#f1f5f9',
            color: isUser ? '#fff' : '#111827',
            padding: '12px 16px',
            borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}
        >
          <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
            {content}
          </Paragraph>
        </div>

        <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center' }}>
          {agentType && !isUser && (
            <Tag color="blue" style={{ fontSize: '12px' }}>
              via {agentType}
            </Tag>
          )}
          {downloadUrl && (
            <Space style={{ marginLeft: '8px' }}>
              <Tag color="success" style={{ fontSize: '12px' }}>
                任务已完成
              </Tag>
              <Button 
                type="link" 
                size="small" 
                icon={<DownloadOutlined />}
                href={downloadUrl}
                target="_blank"
                style={{ padding: 0 }}
              >
                下载文件
              </Button>
            </Space>
          )}
        </div>
      </div>

      {isUser && (
        <Avatar 
          icon={<UserOutlined />} 
          style={{ 
            backgroundColor: '#6366f1',
            marginLeft: '12px'
          }}
        />
      )}
    </div>
  )
}

export default ChatMessage
