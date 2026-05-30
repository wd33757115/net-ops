import React, { useEffect, useState } from 'react'
import { Alert, Card, Collapse, Spin, Steps, Tag, Typography } from 'antd'
import { useQuery } from 'react-query'
import { workflowApi, WorkflowRunDetail } from '../../services/api'
import { GrokChip } from '../ui/GrokUi'

const { Text, Paragraph } = Typography

interface WorkflowRunMonitorProps {
  runId: string | null
  onClose?: () => void
  embedded?: boolean
}

const statusColor: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
}

const WorkflowRunMonitor: React.FC<WorkflowRunMonitorProps> = ({ runId, onClose, embedded }) => {
  const [run, setRun] = useState<WorkflowRunDetail | null>(null)

  const { isLoading, refetch } = useQuery(
    ['workflow-run', runId],
    () => workflowApi.getRun(runId!),
    {
      enabled: !!runId,
      refetchInterval: (data) => {
        if (!data) return 3000
        return data.status === 'completed' || data.status === 'failed' ? false : 3000
      },
      onSuccess: (data) => setRun(data),
    }
  )

  useEffect(() => {
    if (!runId) setRun(null)
  }, [runId])

  if (!runId) return null

  const content = (
    <>
      {isLoading && !run ? (
        <Spin />
      ) : run ? (
        <>
          <div className="grok-chip-row" style={{ marginBottom: 12 }}>
            <GrokChip tone={run.status === 'completed' ? 'ok' : run.status === 'failed' ? 'warn' : undefined}>
              {run.status}
            </GrokChip>
            <Tag>{run.template_name}</Tag>
            {run.ticket_id && <Tag color="blue">{run.ticket_id}</Tag>}
          </div>
          <Text copyable={{ text: run.run_id }} style={{ fontSize: 12 }}>Run ID: {run.run_id}</Text>
          {run.error_message && <Alert type="error" message={run.error_message} style={{ marginTop: 8 }} />}
          <Steps
            direction="vertical"
            size="small"
            current={run.current_step_index}
            style={{ marginTop: 16 }}
            items={run.steps.map((s) => ({
              title: `${s.step_name} (${s.skill_name})`,
              status: s.status === 'completed' ? 'finish' : s.status === 'failed' ? 'error' : s.status === 'running' ? 'process' : 'wait',
              description: s.error_message || (s.output_artifacts ? '已有产物' : undefined),
            }))}
          />
          {run.steps.some((s) => s.skill_name === 'llm-result-analyzer' && s.output_artifacts) && (
            <Alert
              type="success"
              style={{ marginTop: 12 }}
              message="LLM 分析报告已生成"
              description={
                run.steps
                  .filter((s) => s.skill_name === 'llm-result-analyzer')
                  .map((s) => {
                    const art = s.output_artifacts as Record<string, { download_url?: string }> | null
                    const url = art?.analysis_report?.download_url
                    return url ? <a key={s.step_name} href={url} target="_blank" rel="noreferrer">下载分析报告</a> : '见步骤产物'
                  })
              }
            />
          )}
        </>
      ) : null}
    </>
  )

  if (embedded) {
    return <Card size="small" title="运行监控" extra={onClose ? <a onClick={onClose}>关闭</a> : null}>{content}</Card>
  }

  return (
    <Card
      className="grok-run-monitor"
      title="Workflow 运行"
      extra={onClose ? <a onClick={onClose}>关闭</a> : <a onClick={() => refetch()}>刷新</a>}
    >
      {content}
    </Card>
  )
}

export default WorkflowRunMonitor
