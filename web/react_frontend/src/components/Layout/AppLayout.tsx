import React, { useState } from 'react'
import { Layout, Drawer, Button } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import { Outlet } from 'react-router-dom'
import AppSidebar from './Sidebar'
import NavMenu from './NavMenu'
import { useIsMobile } from '../../hooks/useIsMobile'

const { Content, Header } = Layout

const AppLayout: React.FC = () => {
  const isMobile = useIsMobile()
  const [navOpen, setNavOpen] = useState(false)

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {!isMobile && <AppSidebar />}

      <Layout style={{ background: '#f8fafc', minWidth: 0 }}>
        {isMobile && (
          <Header
            className="app-mobile-header"
            style={{
              background: '#fff',
              borderBottom: '1px solid #e5e7eb',
              padding: '0 12px',
              height: 48,
              lineHeight: '48px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Button
              type="text"
              icon={<MenuOutlined />}
              aria-label="打开导航菜单"
              onClick={() => setNavOpen(true)}
            />
            <span style={{ fontWeight: 700, fontSize: 15, color: '#111827' }}>NetOps Agent</span>
          </Header>
        )}

        <Drawer
          title="菜单"
          placement="left"
          open={navOpen}
          onClose={() => setNavOpen(false)}
          width={Math.min(280, typeof window !== 'undefined' ? window.innerWidth * 0.85 : 280)}
          styles={{ body: { padding: 0 } }}
        >
          <NavMenu onNavigate={() => setNavOpen(false)} />
        </Drawer>

        <Content
          style={{
            height: isMobile ? 'calc(100vh - 48px)' : '100vh',
            overflow: 'hidden',
            minWidth: 0,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default AppLayout
