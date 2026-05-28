import React, { useMemo, useState } from 'react'
import { Button, Col, Form, Input, Modal, Row, Select, Spin, Empty, message } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import SkillCard from '../components/SkillCard'
import SkillEditorModal from '../components/SkillEditorModal'
import GrokShellLayout from '../components/layout/GrokShellLayout'
import { GrokToolBtn } from '../components/ui/GrokUi'
import { skillApi, SkillItem } from '../services/api'

const SkillsPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [viewContent, setViewContent] = useState<string | null>(null)
  const [viewName, setViewName] = useState<string | null>(null)
  const [editName, setEditName] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [actionSkill, setActionSkill] = useState<string | null>(null)

  const { data: skills = [], isLoading, refetch } = useQuery<SkillItem[]>(
    'skills',
    skillApi.list,
    { refetchOnWindowFocus: false }
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return skills
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.description || '').toLowerCase().includes(q) ||
        (s.tags || []).some((t) => t.toLowerCase().includes(q))
    )
  }, [skills, search])

  const toggleMutation = useMutation(
    ({ name, enabled }: { name: string; enabled: boolean }) => skillApi.toggle(name, enabled),
    { onSuccess: () => queryClient.invalidateQueries('skills') }
  )

  const reloadMutation = useMutation(
    (name: string) => skillApi.reload(name),
    {
      onSuccess: (_, name) => {
        message.success(`已重载 ${name}`)
        queryClient.invalidateQueries('skills')
      },
    }
  )

  const createMutation = useMutation(
    (values: Record<string, unknown>) => skillApi.create(values),
    {
      onSuccess: () => {
        message.success('Skill 创建成功')
        setCreateOpen(false)
        form.resetFields()
        queryClient.invalidateQueries('skills')
      },
      onError: () => message.error('创建失败'),
    }
  )

  const handleView = async (name: string) => {
    try {
      const res = await skillApi.getContent(name)
      setViewName(name)
      setViewContent(res.content)
    } catch {
      message.error('读取 Skill 内容失败')
    }
  }

  const toolbar = (
    <>
      <Input
        className="grok-search-input"
        placeholder="搜索 Skill…"
        allowClear
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <GrokToolBtn icon={<ReloadOutlined />} onClick={() => refetch()}>
        刷新
      </GrokToolBtn>
      <GrokToolBtn primary icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
        新建 Skill
      </GrokToolBtn>
    </>
  )

  return (
    <GrokShellLayout
      title="Skills"
      subtitle="查看、启用、编辑与热重载 Agent Skills"
      toolbar={toolbar}
    >
      {isLoading ? (
        <div className="grok-page-loading">
          <Spin size="large" />
        </div>
      ) : filtered.length === 0 ? (
        <Empty description="暂无 Skill" className="grok-empty" />
      ) : (
        <Row gutter={[16, 16]}>
          {filtered.map((skill) => (
            <Col xs={24} md={12} xl={8} key={skill.name}>
              <SkillCard
                skill={skill}
                loading={actionSkill === skill.name && (toggleMutation.isLoading || reloadMutation.isLoading)}
                onToggle={(name, enabled) => {
                  setActionSkill(name)
                  toggleMutation.mutate({ name, enabled })
                }}
                onReload={(name) => {
                  setActionSkill(name)
                  reloadMutation.mutate(name)
                }}
                onView={handleView}
                onEdit={setEditName}
              />
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title={viewName ? `查看 ${viewName}` : '查看 Skill'}
        open={!!viewContent}
        onCancel={() => { setViewContent(null); setViewName(null) }}
        footer={null}
        width={800}
      >
        <Input.TextArea value={viewContent || ''} readOnly rows={20} style={{ fontFamily: 'monospace' }} />
      </Modal>

      <Modal
        title="新建 Skill"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={createMutation.isLoading}
        onOk={() => form.submit()}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => {
            const tags = values.tags
              ? String(values.tags).split(',').map((t: string) => t.trim()).filter(Boolean)
              : []
            const triggers = values.triggers
              ? String(values.triggers).split('\n').map((t: string) => t.trim()).filter(Boolean)
              : []
            createMutation.mutate({ ...values, tags, triggers })
          }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="my-skill" />
          </Form.Item>
          <Form.Item name="description" label="描述" rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="category" label="分类" initialValue="general">
            <Select options={[
              { value: 'network', label: 'network' },
              { value: 'security', label: 'security' },
              { value: 'monitoring', label: 'monitoring' },
              { value: 'general', label: 'general' },
            ]} />
          </Form.Item>
          <Form.Item name="triggers" label="触发词（每行一个）">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="network, backup" />
          </Form.Item>
        </Form>
      </Modal>

      <SkillEditorModal
        open={!!editName}
        skillName={editName}
        onClose={() => setEditName(null)}
        onSaved={() => queryClient.invalidateQueries('skills')}
      />
    </GrokShellLayout>
  )
}

export default SkillsPage
