import React, { useState } from 'react'
import { Card, Empty, Input, Steps, Typography, message } from 'antd'
import { RocketOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from 'react-query'
import { GrokChip, GrokToolBtn } from '../ui/GrokUi'
import { workflowApi, CollabTemplate } from '../../services/api'
import WorkflowWizard, { WorkflowWizardInitial } from './WorkflowWizard'

const { Text, Paragraph } = Typography

const CollabTemplateTab: React.FC = () => {
  const [wizardOpen, setWizardOpen] = useState(false)
  const [wizardInitial, setWizardInitial] = useState<WorkflowWizardInitial | null>(null)
  const [generating, setGenerating] = useState<string | null>(null)

  const { data: templates = [], isLoading, refetch } = useQuery(
    'collab-templates',
    workflowApi.listCollabTemplates
  )

  const handleUseTemplate = async (tpl: CollabTemplate) => {
    setGenerating(tpl.id)
    try {
      const res = await workflowApi.generateFromCollabTemplate({
        template_id: tpl.id,
        plugin_name: tpl.default_plugin_name,
      })
      setWizardInitial({
        pluginName: tpl.default_plugin_name,
        category: tpl.category,
        workflowYaml: res.files['WORKFLOW.yaml'],
        chatIntentYaml: res.files['CHAT.intent.yaml'],
        templateId: tpl.id,
      })
      setWizardOpen(true)
      message.success('已生成模板 YAML，请在向导中确认并保存')
    } catch {
      message.error('生成失败')
    } finally {
      setGenerating(null)
    }
  }

  return (
    <>
      <Paragraph type="secondary">
        多 Skill 协同模板：模式 A 推荐 Workflow 第三步使用 <Text code>llm-result-analyzer</Text>，
        通过 <Text code>${'${steps.x.result}'}</Text> 传递上游结果。
      </Paragraph>

      {isLoading ? null : templates.length === 0 ? (
        <Empty description="暂无协同模板" />
      ) : (
        <div className="grok-skill-grid">
          {templates.map((tpl) => (
            <Card key={tpl.id} className="grok-skill-card" bordered={false}>
              <div className="grok-skill-card-title">{tpl.title}</div>
              <Paragraph type="secondary">{tpl.description}</Paragraph>
              <Steps
                size="small"
                direction="vertical"
                current={-1}
                items={tpl.steps.map((s) => ({
                  title: s.label,
                  description: s.skill,
                }))}
                style={{ marginBottom: 12 }}
              />
              <div className="grok-chip-row">
                <GrokChip tone="ok">模式 A</GrokChip>
                <GrokChip>{tpl.default_plugin_name}</GrokChip>
              </div>
              <GrokToolBtn
                primary
                icon={<RocketOutlined />}
                loading={generating === tpl.id}
                onClick={() => handleUseTemplate(tpl)}
                style={{ marginTop: 12 }}
              >
                使用此模板创建 Workflow
              </GrokToolBtn>
            </Card>
          ))}
        </div>
      )}

      {wizardOpen && (
        <div className="grok-wizard-overlay">
          <Card title="Workflow 创建向导" className="grok-wizard-card">
            <WorkflowWizard
              open={wizardOpen}
              onClose={() => setWizardOpen(false)}
              initial={wizardInitial}
              onSaved={() => refetch()}
            />
          </Card>
        </div>
      )}
    </>
  )
}

export default CollabTemplateTab
