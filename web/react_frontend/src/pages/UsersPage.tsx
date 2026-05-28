import React, { useMemo, useState } from 'react'
import {
  Form,
  Input,
  Modal,
  Select,
  Switch,
  Table,
  message,
} from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import GrokShellLayout from '../components/layout/GrokShellLayout'
import { GrokChip, GrokRowAction, GrokToolBtn } from '../components/ui/GrokUi'
import { ManagedUser, userAdminApi } from '../services/api'

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

  const activeCount = users.filter((u) => u.is_active).length

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
        render: (role: string) => <GrokChip tone={role === 'admin' ? 'warn' : 'default'}>{role}</GrokChip>,
      },
      {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        render: (active: boolean) => (
          <GrokChip tone={active ? 'ok' : 'default'}>{active ? '启用' : '禁用'}</GrokChip>
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
          <span className="grok-row-actions">
            <GrokRowAction
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
            </GrokRowAction>
            <GrokRowAction onClick={() => setResetUser(record)}>重置密码</GrokRowAction>
          </span>
        ),
      },
    ],
    [editForm]
  )

  const toolbar = (
    <>
      <GrokToolBtn icon={<ReloadOutlined />} onClick={() => refetch()}>
        刷新
      </GrokToolBtn>
      <GrokToolBtn primary icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
        新建用户
      </GrokToolBtn>
    </>
  )

  return (
    <GrokShellLayout
      title="账户管理"
      subtitle="创建用户、分配角色、启用/禁用账号与重置密码"
      toolbar={toolbar}
    >
      <div className="grok-stat-grid">
        <div className="grok-stat-card">
          <div className="grok-stat-label">用户总数</div>
          <div className="grok-stat-value">{isLoading ? '—' : users.length}</div>
        </div>
        <div className="grok-stat-card">
          <div className="grok-stat-label">已启用</div>
          <div className="grok-stat-value">{isLoading ? '—' : activeCount}</div>
        </div>
        <div className="grok-stat-card">
          <div className="grok-stat-label">已禁用</div>
          <div className="grok-stat-value">{isLoading ? '—' : users.length - activeCount}</div>
        </div>
      </div>

      <section className="grok-panel grok-panel-flush">
        <Table
          className="grok-table"
          rowKey="id"
          loading={isLoading}
          columns={columns}
          dataSource={users}
          pagination={{ pageSize: 10, showSizeChanger: true }}
        />
      </section>

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
    </GrokShellLayout>
  )
}

export default UsersPage
