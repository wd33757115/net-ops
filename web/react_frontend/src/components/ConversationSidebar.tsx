// SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
// SPDX-License-Identifier: Apache-2.0

import React from 'react'
import { Layout } from 'antd'
import ConversationPanel from './ConversationPanel'

const { Sider } = Layout

/** 桌面端对话列表侧栏（ChatGPT 风格窄栏） */
const ConversationSidebar: React.FC = () => {
  return (
    <Sider
      width={260}
      breakpoint="md"
      collapsedWidth={0}
      className="conversation-sider"
      theme="light"
    >
      <ConversationPanel />
    </Sider>
  )
}

export default ConversationSidebar
