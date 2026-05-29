import React, { useState } from 'react'
import { Button, Drawer } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import ChatShellSidebar from '../chat/ChatShellSidebar'
import NotificationBell from '../NotificationBell'
import { useIsMobile } from '../../hooks/useIsMobile'

interface GrokShellLayoutProps {
  children: React.ReactNode
  title?: string
  subtitle?: string
  /** 页面顶部工具栏（搜索、操作按钮） */
  toolbar?: React.ReactNode
  /** @deprecated 使用 toolbar */
  actions?: React.ReactNode
  mode?: 'page' | 'chat'
  footer?: React.ReactNode
  scrollRef?: React.RefObject<HTMLDivElement | null>
}

const GrokShellLayout: React.FC<GrokShellLayoutProps> = ({
  children,
  title,
  subtitle,
  toolbar,
  actions,
  mode = 'page',
  footer,
  scrollRef,
}) => {
  const isMobile = useIsMobile()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const drawerWidth = Math.min(300, typeof window !== 'undefined' ? window.innerWidth * 0.88 : 300)

  const showPageHeader = mode === 'page' && (title || subtitle)
  const pageToolbar = toolbar ?? actions

  return (
    <div className="grok-shell">
      {!isMobile && <ChatShellSidebar />}

      <Drawer
        title={null}
        placement="left"
        open={isMobile && sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        width={drawerWidth}
        styles={{ body: { padding: 0 } }}
        className="grok-sidebar-drawer"
      >
        <ChatShellSidebar onNavigate={() => setSidebarOpen(false)} />
      </Drawer>

      <main className={`grok-main${mode === 'chat' ? ' grok-main-chat' : ''}`}>
        {mode === 'chat' && (
          <div className="grok-chat-topbar">
            <NotificationBell />
          </div>
        )}
        {isMobile && (
          <div className="grok-mobile-bar">
            <Button
              type="text"
              icon={<MenuOutlined />}
              aria-label="打开菜单"
              onClick={() => setSidebarOpen(true)}
            />
          </div>
        )}

        {mode === 'chat' ? (
          <>
            <div ref={scrollRef} className="grok-messages-scroll">
              <div className="grok-messages-inner">{children}</div>
            </div>
            {footer}
          </>
        ) : (
          <div className="grok-content-scroll">
            <div className="grok-content-inner">
              {showPageHeader && (
                <header className="grok-page-header">
                  <div className="grok-page-heading">
                    {title && <h1 className="grok-page-title">{title}</h1>}
                    {subtitle && <p className="grok-page-subtitle">{subtitle}</p>}
                  </div>
                </header>
              )}
              {pageToolbar && <div className="grok-page-toolbar">{pageToolbar}</div>}
              <div className="grok-page-body">{children}</div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default GrokShellLayout
