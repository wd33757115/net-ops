import React from 'react'
import { renderAssistantContent } from '../utils/linkify'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  agentType?: string
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, agentType }) => {
  const isUser = role === 'user'

  if (isUser) {
    return (
      <div className="grok-message grok-message-user">
        <div className="grok-message-user-bubble">{content}</div>
      </div>
    )
  }

  return (
    <article className="grok-message grok-message-assistant">
      <div className="grok-message-body">{renderAssistantContent(content)}</div>
      {agentType && <footer className="grok-message-meta">via {agentType}</footer>}
    </article>
  )
}

export default ChatMessage
