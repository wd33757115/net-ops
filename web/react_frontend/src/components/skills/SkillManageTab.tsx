import React, { useMemo, useState } from 'react'
import { Col, Empty, Input, Modal, Row, Spin, message } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import SkillCard from '../SkillCard'
import SkillEditorModal from '../SkillEditorModal'
import SkillCreateWizard from './SkillCreateWizard'
import { GrokToolBtn } from '../ui/GrokUi'
import { skillApi, SkillItem } from '../../services/api'

interface SkillManageTabProps {
  onOpenWizard?: () => void
}

const SkillManageTab: React.FC<SkillManageTabProps> = () => {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [viewContent, setViewContent] = useState<string | null>(null)
  const [viewName, setViewName] = useState<string | null>(null)
  const [editName, setEditName] = useState<string | null>(null)
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

  const handleView = async (name: string) => {
    try {
      const res = await skillApi.getContent(name)
      setViewName(name)
      setViewContent(res.content)
    } catch {
      message.error('读取 Skill 内容失败')
    }
  }

  return (
    <>
      <div className="grok-page-toolbar grok-page-toolbar-inline">
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
      </div>

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

      <SkillCreateWizard
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => queryClient.invalidateQueries('skills')}
      />

      <SkillEditorModal
        open={!!editName}
        skillName={editName}
        onClose={() => setEditName(null)}
        onSaved={() => queryClient.invalidateQueries('skills')}
      />
    </>
  )
}

export default SkillManageTab
