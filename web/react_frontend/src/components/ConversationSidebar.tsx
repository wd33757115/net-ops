import React from 'react'
import { Layout } from 'antd'
import ConversationPanel from './ConversationPanel'

const { Sider } = Layout

/** 桌面端对话列表侧栏 */
const ConversationSidebar: React.FC = () => {
  return (
    <Sider
      width={280}
      breakpoint="md"
      collapsedWidth={0}
      className="conversation-sider"
      style={{
        background: '#fff',
        borderRight: '1px solid #e5e7eb',
      }}
    >
      <ConversationPanel showBrand />
    </Sider>
  )
}

export default ConversationSidebar
