import React, { useEffect, useState } from 'react'
import { Alert, Form, Input, Select, Steps, Tag, Typography, message } from 'antd'
import { useMutation, useQuery } from 'react-query'
import { skillApi, workflowApi } from '../../services/api'
import ChatIntentEditor from './ChatIntentEditor'
import WorkflowRunMonitor from './WorkflowRunMonitor'
import { GrokToolBtn } from '../ui/GrokUi'

const { TextArea } = Input
const { Text } = Typography

export interface WorkflowWizardInitial {
  pluginName?: string
  category?: string
  workflowYaml?: string
  chatIntentYaml?: string
  templateId?: string
}

interface WorkflowWizardProps {
  open: boolean
  onClose: () => void
  initial?: WorkflowWizardInitial | null
  onSaved?: () => void
}

const DEFAULT_CHAT = `workflow: my-workflow
priority: 50
description: 聊天触发示例

match:
  require_any:
    - 关键词
  require_any_secondary:
    - 变更

context_defaults:
  analysis_focus: summary

response_template: |
  [OK] 已启动 Workflow
  - 流程 ID: {run_id}
  - 工单: {ticket_id}
  - 步骤: {workflow_description}
`

const WorkflowWizard: React.FC<WorkflowWizardProps> = ({ open, onClose, initial, onSaved }) => {
  const [step, setStep] = useState(0)
  const [form] = Form.useForm()
  const [workflowYaml, setWorkflowYaml] = useState('')
  const [chatYaml, setChatYaml] = useState(DEFAULT_CHAT)
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null)
  const [testRunId, setTestRunId] = useState<string | null>(null)
  const [savedRunId, setSavedRunId] = useState<string | null>(null)

  const { data: skills = [] } = useQuery('skills', skillApi.list, { enabled: open })
  const { data: templates = [] } = useQuery('workflow-templates', workflowApi.listTemplates, { enabled: open })

  useEffect(() => {
    if (!open) return
    setStep(0)
    setValidation(null)
    setTestRunId(null)
    setSavedRunId(null)
    if (initial?.workflowYaml) {
      setWorkflowYaml(initial.workflowYaml)
      setChatYaml(initial.chatIntentYaml || DEFAULT_CHAT)
      form.setFieldsValue({
        plugin_name: initial.pluginName || 'my-workflow',
        category: initial.category || 'itsm',
        base_template: initial.templateId || undefined,
      })
    } else {
      setWorkflowYaml('')
      setChatYaml(DEFAULT_CHAT)
      form.resetFields()
      form.setFieldsValue({ category: 'itsm' })
    }
  }, [open, initial, form])

  const validateMutation = useMutation(
    () => workflowApi.validate({ workflow_yaml: workflowYaml, chat_intent_yaml: chatYaml }),
    {
      onSuccess: (res) => {
        setValidation(res)
        if (res.valid) message.success('校验通过')
        else message.error('校验未通过')
      },
    }
  )

  const saveMutation = useMutation(
    async () => {
      const values = await form.validateFields()
      return workflowApi.saveTemplate({
        name: values.plugin_name,
        category: values.category,
        files: { 'WORKFLOW.yaml': workflowYaml, 'CHAT.intent.yaml': chatYaml },
      })
    },
    {
      onSuccess: () => {
        message.success('Workflow 插件已保存')
        onSaved?.()
        setStep(4)
      },
      onError: () => message.error('保存失败'),
    }
  )

  const testRunMutation = useMutation(
    async () => {
      const values = form.getFieldsValue()
      const ctx = {
        ticket_id: values.test_ticket_id || 'REQ2025001',
        analysis_prompt: values.test_analysis_prompt || '请总结变更风险',
        analysis_focus: 'summary',
      }
      return workflowApi.testRun({ template_name: values.plugin_name, context: ctx })
    },
    {
      onSuccess: (res) => {
        setTestRunId(res.run_id)
        message.success('试跑已启动')
      },
      onError: () => message.error('试跑失败（需 admin 权限且 Celery 运行中）'),
    }
  )

  const handleGenerateFromTemplate = async (templateName: string) => {
    try {
      const detail = await workflowApi.getTemplate(templateName)
      setWorkflowYaml(detail.files['WORKFLOW.yaml'] || '')
      if (detail.files['CHAT.intent.yaml']) setChatYaml(detail.files['CHAT.intent.yaml']!)
      form.setFieldValue('plugin_name', `${templateName}-copy`)
      message.success(`已复制模板 ${templateName}`)
    } catch {
      message.error('加载模板失败')
    }
  }

  if (!open) return null

  return (
    <div className="grok-wizard-panel">
      <Steps
        current={step}
        size="small"
        style={{ marginBottom: 24 }}
        items={[
          { title: '选场景' },
          { title: 'Skill 链' },
          { title: 'YAML 编辑' },
          { title: '聊天触发' },
          { title: '试跑发布' },
        ]}
      />

      <Form form={form} layout="vertical">
        {step === 0 && (
          <>
            <Form.Item name="plugin_name" label="插件目录名" rules={[{ required: true, pattern: /^[a-z0-9-]+$/ }]}>
              <Input placeholder="itsm-my-workflow" />
            </Form.Item>
            <Form.Item name="category" label="分类目录">
              <Select options={[
                { value: 'itsm', label: 'itsm' },
                { value: 'custom', label: 'custom' },
              ]} />
            </Form.Item>
            <Form.Item label="从已有模板复制">
              <Select
                placeholder="选择模板…"
                allowClear
                options={templates.map((t) => ({ value: t.name, label: `${t.name} — ${t.description}` }))}
                onChange={(v) => v && handleGenerateFromTemplate(v)}
              />
            </Form.Item>
            <Text type="secondary">或前往「协同模板」Tab 使用模式 A 一键生成。</Text>
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <GrokToolBtn primary onClick={() => setStep(1)}>下一步</GrokToolBtn>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <Text>配置 Skill 链（第三步推荐使用 <Tag>llm-result-analyzer</Tag> 实现模式 A）。</Text>
            <Form.Item label="Step 1 Skill" name="step1_skill">
              <Select
                showSearch
                placeholder="选择 Skill"
                options={skills.map((s) => ({ value: s.name, label: s.name }))}
                onChange={(v) => {
                  const name = form.getFieldValue('plugin_name') || 'my-workflow'
                  if (!workflowYaml) {
                    setWorkflowYaml(`name: ${name}\ndescription: 自定义 Workflow\nversion: "1.0"\n\nsteps:\n  - name: step_one\n    label: 第一步\n    skill: ${v}\n    inputs:\n      ticket_id: \${context.ticket_id}\n      workflow_run_id: \${run.id}\n\non_complete:\n  message: 已完成\n`)
                  }
                }}
              />
            </Form.Item>
            <Form.Item label="Step 2 Skill" name="step2_skill">
              <Select
                showSearch
                allowClear
                options={skills.map((s) => ({ value: s.name, label: s.name }))}
              />
            </Form.Item>
            <Form.Item label="Step 3（LLM 分析）" initialValue="llm-result-analyzer">
              <Select
                value="llm-result-analyzer"
                disabled
                options={[{ value: 'llm-result-analyzer', label: 'llm-result-analyzer（模式 A 推荐）' }]}
              />
            </Form.Item>
            <Alert
              type="info"
              showIcon
              message="表达式映射示例"
              description={
                <code>{'prev_result: ${steps.change_ticket.result}'}</code>
              }
              style={{ marginBottom: 16 }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <GrokToolBtn onClick={() => setStep(0)}>上一步</GrokToolBtn>
              <GrokToolBtn primary onClick={() => setStep(2)}>下一步</GrokToolBtn>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <Text>编辑 WORKFLOW.yaml，使用 <code>${'${context.*}'}</code> 与 <code>${'${steps.*.result}'}</code> 映射依赖。</Text>
            <TextArea
              value={workflowYaml}
              onChange={(e) => setWorkflowYaml(e.target.value)}
              rows={18}
              style={{ fontFamily: 'monospace', fontSize: 12, marginTop: 8 }}
            />
            {validation && (
              <div style={{ marginTop: 8 }}>
                {validation.errors.map((e) => <Alert key={e} type="error" message={e} style={{ marginBottom: 4 }} />)}
                {validation.warnings.map((w) => <Alert key={w} type="warning" message={w} style={{ marginBottom: 4 }} />)}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
              <GrokToolBtn onClick={() => setStep(1)}>上一步</GrokToolBtn>
              <div style={{ display: 'flex', gap: 8 }}>
                <GrokToolBtn onClick={() => validateMutation.mutate()} loading={validateMutation.isLoading}>校验 YAML</GrokToolBtn>
                <GrokToolBtn primary onClick={() => setStep(3)}>下一步</GrokToolBtn>
              </div>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <ChatIntentEditor
              value={chatYaml}
              onChange={setChatYaml}
              workflowName={form.getFieldValue('plugin_name')}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
              <GrokToolBtn onClick={() => setStep(2)}>上一步</GrokToolBtn>
              <GrokToolBtn primary onClick={() => setStep(4)}>下一步</GrokToolBtn>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <Form.Item name="test_ticket_id" label="试跑工单号" initialValue="REQ2025001">
              <Input placeholder="REQ2025001" />
            </Form.Item>
            <Form.Item name="test_analysis_prompt" label="LLM 分析问题" initialValue="请分析变更风险与合规性">
              <Input />
            </Form.Item>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <GrokToolBtn primary loading={saveMutation.isLoading} onClick={() => saveMutation.mutate()}>保存并发布</GrokToolBtn>
              <GrokToolBtn loading={testRunMutation.isLoading} onClick={() => testRunMutation.mutate()}>试跑 Workflow</GrokToolBtn>
            </div>
            {(testRunId || savedRunId) && (
              <WorkflowRunMonitor
                runId={testRunId || savedRunId}
                embedded
                onClose={() => { setTestRunId(null); setSavedRunId(null) }}
              />
            )}
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between' }}>
              <GrokToolBtn onClick={() => setStep(3)}>上一步</GrokToolBtn>
              <GrokToolBtn primary onClick={onClose}>完成</GrokToolBtn>
            </div>
          </>
        )}
      </Form>
    </div>
  )
}

export default WorkflowWizard
