import React, { useMemo, useState } from 'react'
import {
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { ManagedUser, userAdminApi } from '../services/api'

const { Title, Text } = Typography

const ROLE_OPTIONS = [
  { value: 'admin', label: 'admin — 管理员' },
  { value: 'operator', label: 'operator — 运维' },
  { value: 'viewer', label: 'viewer — 只读' },
]

const UsersPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [editUser, setEditUser] = useState<ManagedUser | null>(null)
  const [resetUser, setResetUser] = useState<ManagedUser | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [resetForm] = Form.useForm()

  const { data: users = [], isLoading, refetch } = useQuery<ManagedUser[]>(
    'managed-users',
    userAdminApi.list,
    { refetchOnWindowFocus: false }
  )

  const createMutation = useMutation(userAdminApi.create, {
    onSuccess: () => {
      message.success('用户已创建')
      setCreateOpen(false)
      createForm.resetFields()
      queryClient.invalidateQueries('managed-users')
    },
    onError: (err: Error) => message.error(err.message || '创建失败'),
  })

  const updateMutation = useMutation(
    ({ id, data }: { id: number; data: Partial<ManagedUser> }) => userAdminApi.update(id, data),
    {
      onSuccess: () => {
        message.success('用户已更新')
        setEditUser(null)
        editForm.resetFields()
        queryClient.invalidateQueries('managed-users')
      },
      onError: (err: Error) => message.error(err.message || '更新失败'),
    }
  )

  const resetMutation = useMutation(
    ({ id, password }: { id: number; password: string }) => userAdminApi.resetPassword(id, password),
    {
      onSuccess: () => {
        message.success('密码已重置')
        setResetUser(null)
        resetForm.resetFields()
      },
      onError: (err: Error) => message.error(err.message || '重置失败'),
    }
  )

  const columns: ColumnsType<ManagedUser> = useMemo(
    () => [
      { title: '用户名', dataIndex: 'username', key: 'username' },
      { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
      {
        title: '角色',
        dataIndex: 'role',
        key: 'role',
        render: (role: string) => <Tag color={role === 'admin' ? 'red' : role === 'operator' ? 'blue' : 'default'}>{role}</Tag>,
      },
      {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        render: (active: boolean) => (
          <Tag color={active ? 'success' : 'default'}>{active ? '启用' : '禁用'}</Tag>
        ),
      },
      {
        title: '最后登录',
        dataIndex: 'last_login',
        key: 'last_login',
        render: (value: string | null) => (value ? new Date(value).toLocaleString() : '—'),
      },
      {
        title: '操作',
        key: 'actions',
        render: (_, record) => (
          <Space size="small">
            <Button
              type="link"
              size="small"
              onClick={() => {
                setEditUser(record)
                editForm.setFieldsValue({
                  email: record.email,
                  role: record.role,
                  is_active: record.is_active,
                })
              }}
            >
              编辑
            </Button>
            <Button type="link" size="small" onClick={() => setResetUser(record)}>
              重置密码
            </Button>
          </Space>
        ),
      },
    ],
    [editForm]
  )

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            账户管理
          </Title>
          <Text type="secondary">创建用户、分配角色、启用/禁用账号与重置密码</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新建用户
          </Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={users}
        pagination={{ pageSize: 10, showSizeChanger: true }}
      />

      <Modal
        title="新建用户"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false)
          createForm.resetFields()
        }}
        onOk={() => createForm.submit()}
        confirmLoading={createMutation.isLoading}
        destroyOnClose
      >
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{ role: 'operator' }}
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input type="email" autoComplete="email" />
          </Form.Item>
          <Form.Item name="password" label="初始密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户：${editUser?.username ?? ''}`}
        open={!!editUser}
        onCancel={() => {
          setEditUser(null)
          editForm.resetFields()
        }}
        onOk={() => editForm.submit()}
        confirmLoading={updateMutation.isLoading}
        destroyOnClose
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(values) => {
            if (!editUser) return
            updateMutation.mutate({ id: editUser.id, data: values })
          }}
        >
          <Form.Item name="email" label="邮箱">
            <Input type="email" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重置密码：${resetUser?.username ?? ''}`}
        open={!!resetUser}
        onCancel={() => {
          setResetUser(null)
          resetForm.resetFields()
        }}
        onOk={() => resetForm.submit()}
        confirmLoading={resetMutation.isLoading}
        destroyOnClose
      >
        <Form
          form={resetForm}
          layout="vertical"
          onFinish={(values) => {
            if (!resetUser) return
            resetMutation.mutate({ id: resetUser.id, password: values.new_password })
          }}
        >
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[{ required: true, message: '请输入新密码' }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default UsersPage
