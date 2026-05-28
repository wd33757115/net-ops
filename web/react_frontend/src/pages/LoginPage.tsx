import React, { useState } from 'react'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const { Title, Paragraph } = Typography

const LoginPage: React.FC = () => {
  const { login, isAuthenticated, loading } = useAuth()
  const [submitting, setSubmitting] = useState(false)
  const location = useLocation()
  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/chat'

  if (!loading && isAuthenticated) {
    return <Navigate to={from} replace />
  }

  const onFinish = async (values: { username: string; password: string }) => {
    setSubmitting(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #eef2ff 0%, #f8fafc 50%, #ecfeff 100%)',
        padding: 24,
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 12px 40px rgba(15,23,42,0.08)' }}>
        <Title level={3} style={{ marginBottom: 8 }}>
          NetOps Agent
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 24 }}>
          多用户登录 · 独立会话 · RBAC
        </Paragraph>
        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input
              prefix={<UserOutlined />}
              placeholder="admin / operator / viewer"
              size="large"
              autoComplete="username"
            />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size="large"
              autoComplete="current-password"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
            登录
          </Button>
        </Form>
        <Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0, fontSize: 12 }}>
          演示账号：admin/admin123 · operator/operator123 · viewer/viewer123
        </Paragraph>
      </Card>
    </div>
  )
}

export default LoginPage
