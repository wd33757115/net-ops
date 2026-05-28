import React, { useMemo } from 'react'
import { Button, Menu, Tag } from 'antd'
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
    <div className="app-nav-menu">
      <div className="app-nav-brand">
        <span className="app-nav-logo">NetOps</span>
        <span className="app-nav-sub">Agent</span>
      </div>
      {user && (
        <div className="app-nav-user">
          <span className="app-nav-username">{user.username}</span>
          <Tag bordered={false} color="processing" className="app-nav-role">
            {user.role}
          </Tag>
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
        className="app-nav-items"
      />
      <div className="app-nav-footer">
        <Button type="text" icon={<LogoutOutlined />} block onClick={handleLogout}>
          退出登录
        </Button>
      </div>
    </div>
  )
}

export default NavMenu
