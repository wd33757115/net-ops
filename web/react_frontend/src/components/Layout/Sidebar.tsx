import React from 'react'
import { Layout } from 'antd'
import NavMenu from './NavMenu'

const { Sider } = Layout

/** 桌面端左侧导航（手机端由 AppLayout 抽屉承载） */
const AppSidebar: React.FC = () => {
  return (
    <Sider
      width={220}
      theme="light"
      breakpoint="md"
      collapsedWidth={0}
      className="app-nav-sider"
    >
      <NavMenu />
    </Sider>
  )
}

export default AppSidebar
