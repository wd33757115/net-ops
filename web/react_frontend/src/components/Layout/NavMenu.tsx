import React, { useMemo } from 'react'
import { Button, Menu, Space, Tag } from 'antd'
import {
  MessageOutlined,
  AppstoreOutlined,
  DashboardOutlined,
  BookOutlined,
  LogoutOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export const navMenuItems = [
  { key: '/chat', icon: React.createElement(MessageOutlined), label: 'Chat' },
  { key: '/skills', icon: React.createElement(AppstoreOutlined), label: 'Skills' },
  { key: '/knowledge', icon: React.createElement(BookOutlined), label: '知识库' },
  { key: '/status', icon: React.createElement(DashboardOutlined), label: 'Status' },
]

const adminMenuItem = {
  key: '/users',
  icon: React.createElement(TeamOutlined),
  label: '账户管理',
}

interface NavMenuProps {
  onNavigate?: () => void
}

const NavMenu: React.FC<NavMenuProps> = ({ onNavigate }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const menuItems = useMemo(() => {
    if (user?.role === 'admin') {
      return [...navMenuItems.slice(0, 1), adminMenuItem, ...navMenuItems.slice(1)]
    }
    return navMenuItems
  }, [user?.role])
  const selectedKey =
    menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/chat'

  const handleLogout = async () => {
    await logout()
    navigate('/login')
    onNavigate?.()
  }

  return (
    <>
      <div style={{ padding: '16px 16px 8px', fontWeight: 700, fontSize: 16, color: '#111827' }}>
        NetOps Agent
      </div>
      {user && (
        <div style={{ padding: '0 16px 8px' }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <span style={{ fontSize: 13, color: '#374151' }}>{user.username}</span>
            <Tag color="blue">{user.role}</Tag>
          </Space>
        </div>
      )}
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => {
          navigate(key)
          onNavigate?.()
        }}
        style={{ borderInlineEnd: 'none', marginTop: 8 }}
      />
      <div style={{ padding: 16, marginTop: 'auto' }}>
        <Button icon={<LogoutOutlined />} block onClick={handleLogout}>
          退出登录
        </Button>
      </div>
    </>
  )
}

export default NavMenu
