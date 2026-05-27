import React from 'react'
import { Menu } from 'antd'
import { MessageOutlined, AppstoreOutlined, DashboardOutlined, BookOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'

export const navMenuItems = [
  { key: '/chat', icon: React.createElement(MessageOutlined), label: 'Chat' },
  { key: '/skills', icon: React.createElement(AppstoreOutlined), label: 'Skills' },
  { key: '/knowledge', icon: React.createElement(BookOutlined), label: '知识库' },
  { key: '/status', icon: React.createElement(DashboardOutlined), label: 'Status' },
]

interface NavMenuProps {
  onNavigate?: () => void
}

const NavMenu: React.FC<NavMenuProps> = ({ onNavigate }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const selectedKey =
    navMenuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/chat'

  return (
    <>
      <div style={{ padding: '16px 16px 8px', fontWeight: 700, fontSize: 16, color: '#111827' }}>
        NetOps Agent
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={navMenuItems}
        onClick={({ key }) => {
          navigate(key)
          onNavigate?.()
        }}
        style={{ borderInlineEnd: 'none', marginTop: 8 }}
      />
    </>
  )
}

export default NavMenu
