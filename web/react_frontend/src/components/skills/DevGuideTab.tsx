import React, { useState } from 'react'
import { Alert, Card, Collapse, Input, Table, Typography } from 'antd'
import { useQuery } from 'react-query'
import { workflowApi } from '../../services/api'
import WorkflowRunMonitor from './WorkflowRunMonitor'
import { GrokToolBtn } from '../ui/GrokUi'

const { Paragraph, Text } = Typography

const DEV_GUIDE_SECTIONS = [
  {
    key: 'structure',
    label: '1. 插件目录结构',
    children: (
      <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 8 }}>{`src/workflows/itsm/<plugin-name>/
├── WORKFLOW.yaml        # Skill 链 + 表达式
├── CHAT.intent.yaml     # 聊天触发（可选）
└── ITSM.webhook.yaml    # Webhook 触发（可选）`}</pre>
    ),
  },
  {
    key: 'expressions',
    label: '2. 表达式约定',
    children: (
      <Table
        size="small"
        pagination={false}
        dataSource={[
          { key: '1', expr: '${context.ticket_id}', desc: '运行上下文' },
          { key: '2', expr: '${run.id}', desc: 'Workflow Run ID' },
          { key: '3', expr: '${steps.x.result.*}', desc: '上游步骤 JSON 结果' },
          { key: '4', expr: '${steps.x.artifacts.key.download_url}', desc: 'MinIO 产物 URL' },
        ]}
        columns={[
          { title: '表达式', dataIndex: 'expr', render: (v) => <Text code>{v}</Text> },
          { title: '含义', dataIndex: 'desc' },
        ]}
      />
    ),
  },
  {
    key: 'mode-a',
    label: '3. 模式 A：LLM 分析第三步',
    children: (
      <>
        <Paragraph>
          当第二步依赖第一步结果且需要 LLM 解读时，第三步固定使用 Skill <Text code>llm-result-analyzer</Text>：
        </Paragraph>
        <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 8 }}>{`  - name: llm_analysis
    label: LLM 结果分析
    skill: llm-result-analyzer
    inputs:
      prev_result: \${steps.change_ticket.result}
      analysis_prompt: \${context.analysis_prompt}
      analysis_focus: summary`}</pre>
      </>
    ),
  },
  {
    key: 'chat',
    label: '4. 聊天触发规则',
    children: (
      <>
        <Alert
          type="warning"
          showIcon
          message="聊天触发 Workflow 时，当前消息必须包含可识别工单号（如 REQ2025）"
          description="示例：「根据工单 REQ2025001，生成防火墙策略并进行 LLM 分析」"
        />
        <Paragraph type="secondary" style={{ marginTop: 12 }}>
          同 priority 时按 secondary 关键词命中数 tie-break；Webhook 请使用 ITSM.webhook.yaml，勿与聊天 Intent 混用 auto_if_source。
        </Paragraph>
      </>
    ),
  },
  {
    key: 'notify',
    label: '5. 通知策略',
    children: (
      <>
        <p>在 WORKFLOW.yaml 的 <code>on_complete</code> 中配置：</p>
        <ul>
          <li><code>notify_each_step: true</code> — 每步完成发站内通知（长流程推荐）</li>
          <li><code>notify_each_step: false</code> — 默认，仅最终成功/失败通知</li>
          <li><code>notify_on_failure: true</code> — 失败时通知（默认开启）</li>
        </ul>
      </>
    ),
  },
  {
    key: 'checklist',
    label: '6. 发布检查清单',
    children: (
      <ul>
        <li>WORKFLOW.yaml 中引用的 Skill 已在 Skills 页启用</li>
        <li>表达式 <code>${'${steps.*}'}</code> 步骤名与 YAML 中 name 一致</li>
        <li>CHAT.intent.yaml 关键词与业务话术对齐</li>
        <li>保存后点击「重载插件」或重启 Gateway</li>
        <li>使用向导「试跑 Workflow」验证（需 Celery Worker）</li>
      </ul>
    ),
  },
]

const DevGuideTab: React.FC = () => {
  const [runIdInput, setRunIdInput] = useState('')
  const [monitorRunId, setMonitorRunId] = useState<string | null>(null)

  const { data: recentRuns = [] } = useQuery(
    'workflow-runs',
    () => workflowApi.listRuns({ limit: 10 }),
    { refetchOnWindowFocus: false }
  )

  return (
    <div className="grok-dev-guide">
      <Alert
        type="info"
        showIcon
        message="开发指南"
        description="完整文档见 src/workflows/itsm/README.md。以下为核心要点与运行监控入口。"
        style={{ marginBottom: 16 }}
      />

      <Collapse items={DEV_GUIDE_SECTIONS} defaultActiveKey={['mode-a']} />

      <Card title="最近 Workflow 运行" style={{ marginTop: 24 }} size="small">
        <Table
          size="small"
          rowKey="run_id"
          pagination={false}
          dataSource={recentRuns}
          columns={[
            { title: 'Run ID', dataIndex: 'run_id', ellipsis: true, width: 200 },
            { title: '模板', dataIndex: 'template_name' },
            { title: '工单', dataIndex: 'ticket_id' },
            { title: '状态', dataIndex: 'status' },
            {
              title: '操作',
              render: (_, row) => (
                <GrokToolBtn onClick={() => setMonitorRunId(row.run_id)}>查看</GrokToolBtn>
              ),
            },
          ]}
        />
      </Card>

      <Card title="按 Run ID 查询" style={{ marginTop: 16 }} size="small">
        <Input.Search
          placeholder="输入 Workflow Run ID"
          value={runIdInput}
          onChange={(e) => setRunIdInput(e.target.value)}
          onSearch={(v) => setMonitorRunId(v.trim() || null)}
          enterButton="查询"
        />
        {monitorRunId && (
          <div style={{ marginTop: 16 }}>
            <WorkflowRunMonitor runId={monitorRunId} embedded onClose={() => setMonitorRunId(null)} />
          </div>
        )}
      </Card>
    </div>
  )
}

export default DevGuideTab
