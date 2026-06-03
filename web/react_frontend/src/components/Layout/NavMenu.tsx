// SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
// SPDX-License-Identifier: Apache-2.0

import React from 'react'
import { Button, Menu, Tag } from 'antd'
import {
  MessageOutlined,
  AppstoreOutlined,
  BookOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export const navMenuItems = [
  { key: '/chat', icon: React.createElement(MessageOutlined), label: 'Chat' },
  { key: '/skills', icon: React.createElement(AppstoreOutlined), label: 'Skills' },
  { key: '/knowledge', icon: React.createElement(BookOutlined), label: '知识库' },
]

interface NavMenuProps {
  onNavigate?: () => void
}

const NavMenu: React.FC<NavMenuProps> = ({ onNavigate }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const menuItems = navMenuItems
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
