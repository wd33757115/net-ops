import React from 'react'
import { Outlet } from 'react-router-dom'

/** 各页面自带 GrokShellLayout，此处仅提供全屏容器 */
const AppLayout: React.FC = () => {
  return (
    <div className="grok-app-root">
      <Outlet />
    </div>
  )
}

export default AppLayout
