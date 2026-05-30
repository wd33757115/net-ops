import React, { useState } from 'react'
import { Card, Empty, Input, Modal, Spin, Tag, Typography, message } from 'antd'
import { EyeOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQuery } from 'react-query'
import { GrokChip, GrokToolBtn } from '../ui/GrokUi'
import { workflowApi, WorkflowTemplateSummary } from '../../services/api'
import WorkflowRunMonitor from './WorkflowRunMonitor'

const { Text, Paragraph } = Typography

interface WorkflowPluginListProps {
  onCreateWizard: () => void
}

const WorkflowPluginList: React.FC<WorkflowPluginListProps> = ({ onCreateWizard }) => {
  const [search, setSearch] = useState('')
  const [viewName, setViewName] = useState<string | null>(null)
  const [yamlContent, setYamlContent] = useState<string | null>(null)
  const [monitorRunId, setMonitorRunId] = useState<string | null>(null)

  const { data: templates = [], isLoading, refetch } = useQuery(
    'workflow-templates',
    workflowApi.listTemplates,
    { refetchOnWindowFocus: false }
  )

  const filtered = templates.filter((t: WorkflowTemplateSummary) => {
    const q = search.trim().toLowerCase()
    if (!q) return true
    return t.name.includes(q) || (t.description || '').toLowerCase().includes(q)
  })

  const handleView = async (name: string) => {
    try {
      const detail = await workflowApi.getTemplate(name)
      setViewName(name)
      setYamlContent(detail.files['WORKFLOW.yaml'] || '')
    } catch {
      message.error('读取 Workflow 失败')
    }
  }

  const handleReload = async () => {
    try {
      await workflowApi.reload()
      message.success('Workflow 插件已重载')
      refetch()
    } catch {
      message.error('重载失败')
    }
  }

  return (
    <>
      <div className="grok-page-toolbar grok-page-toolbar-inline">
        <Input
          className="grok-search-input"
          placeholder="搜索 Workflow 插件…"
          allowClear
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <GrokToolBtn icon={<ReloadOutlined />} onClick={handleReload}>重载插件</GrokToolBtn>
        <GrokToolBtn icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</GrokToolBtn>
        <GrokToolBtn primary icon={<PlusOutlined />} onClick={onCreateWizard}>创建 Workflow</GrokToolBtn>
      </div>

      {isLoading ? (
        <div className="grok-page-loading"><Spin size="large" /></div>
      ) : filtered.length === 0 ? (
        <Empty description="暂无 Workflow 插件" className="grok-empty" />
      ) : (
        <div className="grok-skill-grid">
          {filtered.map((tpl) => (
            <Card key={tpl.name} className="grok-skill-card" bordered={false}>
              <div className="grok-skill-card-title">{tpl.name}</div>
              <Paragraph type="secondary" ellipsis={{ rows: 2 }}>{tpl.description || '—'}</Paragraph>
              <div className="grok-chip-row">
                <GrokChip tone="ok">v{tpl.version}</GrokChip>
                <GrokChip>{tpl.step_count} 步</GrokChip>
                {tpl.has_chat_intent && <Tag color="blue">聊天触发</Tag>}
                {tpl.has_webhook && <Tag color="purple">Webhook</Tag>}
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>{tpl.plugin_dir}</Text>
              <div className="grok-skill-card-btns" style={{ marginTop: 12 }}>
                <GrokToolBtn icon={<EyeOutlined />} onClick={() => handleView(tpl.name)}>查看 YAML</GrokToolBtn>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        title={viewName ? `WORKFLOW.yaml — ${viewName}` : 'Workflow'}
        open={!!yamlContent}
        onCancel={() => { setYamlContent(null); setViewName(null) }}
        footer={null}
        width={860}
      >
        <Input.TextArea value={yamlContent || ''} readOnly rows={24} style={{ fontFamily: 'monospace', fontSize: 12 }} />
      </Modal>

      <WorkflowRunMonitor runId={monitorRunId} onClose={() => setMonitorRunId(null)} />
    </>
  )
}

export default WorkflowPluginList
