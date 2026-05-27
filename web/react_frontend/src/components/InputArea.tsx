import React, { useState } from 'react'
import { Input, Button, Space, Tag } from 'antd'
import { SendOutlined, CloseOutlined, FileTextOutlined } from '@ant-design/icons'
import { useChatStore } from '../store/useChatStore'

const { TextArea } = Input

interface InputAreaProps {
  onSend: (text: string) => void
  loading: boolean
  compact?: boolean
}

const InputArea: React.FC<InputAreaProps> = ({ onSend, loading, compact }) => {
  const [text, setText] = useState('')
  const { uploadedFile, setUploadedFile } = useChatStore()

  const handleSend = () => {
    if (text.trim() || uploadedFile) {
      onSend(text)
      setText('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      className="chat-input-area"
      style={{
        padding: compact ? '10px 12px calc(12px + env(safe-area-inset-bottom))' : '16px 24px 24px',
        borderTop: '1px solid #e5e7eb',
        background: '#ffffff',
        flexShrink: 0,
      }}
    >
      {uploadedFile && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          marginBottom: '12px',
          background: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: '8px',
          padding: '8px 12px'
        }}>
          <FileTextOutlined style={{ color: '#16a34a', marginRight: '8px' }} />
          <span style={{ flex: 1, color: '#166534', fontSize: '14px' }}>
            {uploadedFile.name}
          </span>
          <Button 
            type="text" 
            icon={<CloseOutlined />}
            size="small"
            onClick={() => setUploadedFile(null)}
            style={{ color: '#991b1b' }}
          />
        </div>
      )}

      <div style={{ 
        display: 'flex',
        gap: '12px',
        alignItems: 'flex-end'
      }}>
        <div style={{ flex: 1 }}>
          <TextArea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="请输入您的运维问题或指令..."
            autoSize={{ minRows: 1, maxRows: 6 }}
            disabled={loading}
            style={{
              borderRadius: '12px',
              border: '1px solid #e5e7eb',
              resize: 'none',
              boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
            }}
          />
          {!compact && (
            <div
              style={{
                textAlign: 'right',
                fontSize: 12,
                color: '#9ca3af',
                marginTop: 4,
              }}
            >
              Enter 发送 · Shift + Enter 换行
            </div>
          )}
        </div>

        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          disabled={!text.trim() && !uploadedFile}
          style={{
            height: compact ? 44 : 48,
            borderRadius: 12,
            paddingLeft: compact ? 14 : 20,
            paddingRight: compact ? 14 : 20,
            background: '#3b82f6',
          }}
        >
          {compact ? null : '发送'}
        </Button>
      </div>
    </div>
  )
}

export default InputArea
