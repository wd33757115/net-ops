import React from 'react'
import { Layout, Menu } from 'antd'
import { MessageOutlined, AppstoreOutlined, DashboardOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'

const { Sider } = Layout

const menuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: 'Chat' },
  { key: '/skills', icon: <AppstoreOutlined />, label: 'Skills' },
  { key: '/status', icon: <DashboardOutlined />, label: 'Status' },
]

const AppSidebar: React.FC = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const selectedKey = menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/chat'

  return (
    <Sider width={200} theme="light" style={{ borderRight: '1px solid #e5e7eb', background: '#fff' }}>
      <div style={{ padding: '20px 16px 8px', fontWeight: 700, fontSize: 16, color: '#111827' }}>
        NetOps Agent
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{ borderInlineEnd: 'none', marginTop: 8 }}
      />
    </Sider>
  )
}

export default AppSidebar
