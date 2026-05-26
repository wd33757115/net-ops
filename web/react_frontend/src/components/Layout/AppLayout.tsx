import React from 'react'
import { Layout } from 'antd'
import { Outlet } from 'react-router-dom'
import AppSidebar from './Sidebar'

const { Content } = Layout

const AppLayout: React.FC = () => {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <AppSidebar />
      <Layout style={{ background: '#f8fafc' }}>
        <Content style={{ height: '100vh', overflow: 'hidden' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default AppLayout
