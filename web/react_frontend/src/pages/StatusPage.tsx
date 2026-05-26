import React, { useState } from 'react'
import {
  Button,
  Card,
  Col,
  Row,
  Statistic,
  Typography,
  Spin,
  Tag,
  Space,
  Table,
  Alert,
  message,
} from 'antd'
import { useQuery } from 'react-query'
import { ReloadOutlined, MedicineBoxOutlined } from '@ant-design/icons'
import { chatApi, skillApi, type DiagnosticsResponse, type ServiceCheck } from '../services/api'

const { Title, Text } = Typography

const statusColor: Record<string, string> = {
  ok: 'success',
  degraded: 'warning',
  down: 'error',
  skipped: 'default',
}

const overallColor: Record<string, string> = {
  healthy: 'success',
  degraded: 'warning',
  unhealthy: 'error',
}

const StatusPage: React.FC = () => {
  const [diagEnabled, setDiagEnabled] = useState(false)

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery(
    'health',
    chatApi.getHealth
  )
  const { data: stats, isLoading: statsLoading } = useQuery('skill-stats', skillApi.getStats)

  const {
    data: diagnostics,
    isLoading: diagLoading,
    isFetching: diagFetching,
    refetch: runDiagnostics,
  } = useQuery<DiagnosticsResponse>(
    'diagnostics',
    chatApi.getDiagnostics,
    { enabled: diagEnabled, retry: false }
  )

  const handleDiagnostics = async () => {
    setDiagEnabled(true)
    try {
      await runDiagnostics()
      message.success('诊断完成')
    } catch {
      message.error('诊断请求失败，请确认 FastAPI 已启动')
    }
  }

  if (healthLoading || statsLoading) {
    return (
      <div style={{ padding: 80, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  const diagColumns = [
    {
      title: '服务',
      dataIndex: 'name',
      key: 'name',
      width: 160,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => <Tag color={statusColor[s] || 'default'}>{s.toUpperCase()}</Tag>,
    },
    {
      title: '说明',
      dataIndex: 'message',
      key: 'message',
    },
    {
      title: '延迟 (ms)',
      dataIndex: 'latency_ms',
      key: 'latency_ms',
      width: 100,
      render: (v: number | null) => (v != null ? v : '—'),
    },
  ]

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>
            系统状态
          </Title>
          <Text type="secondary">Django BFF 与 FastAPI 后端运行概况</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetchHealth()}>
            刷新健康
          </Button>
          <Button
            type="primary"
            icon={<MedicineBoxOutlined />}
            loading={diagLoading || diagFetching}
            onClick={handleDiagnostics}
          >
            一键诊断
          </Button>
        </Space>
      </div>

      {diagnostics && (
        <Alert
          style={{ marginTop: 16 }}
          type={
            diagnostics.status === 'healthy'
              ? 'success'
              : diagnostics.status === 'degraded'
                ? 'warning'
                : 'error'
          }
          showIcon
          message={
            <Space>
              <Text strong>诊断结果</Text>
              <Tag color={overallColor[diagnostics.status]}>{diagnostics.status}</Tag>
              <Text>{diagnostics.summary}</Text>
            </Space>
          }
        />
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="服务健康（BFF → FastAPI /health）" style={{ borderRadius: 12 }}>
            <Space style={{ marginBottom: 12 }}>
              <Tag color={health?.status === 'healthy' ? 'success' : 'warning'}>
                {health?.status || 'unknown'}
              </Tag>
              {health?.services &&
                Object.entries(health.services).map(([k, v]) => (
                  <Tag key={k} color={v ? 'success' : 'error'}>
                    {k}: {v ? 'OK' : 'FAIL'}
                  </Tag>
                ))}
            </Space>
            <pre style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(health, null, 2)}
            </pre>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Skill 统计" style={{ borderRadius: 12 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总数" value={stats?.total_skills || 0} />
              </Col>
              <Col span={8}>
                <Statistic title="启用" value={stats?.enabled_skills || 0} />
              </Col>
              <Col span={8}>
                <Statistic title="禁用" value={stats?.disabled_skills || 0} />
              </Col>
            </Row>
            <div style={{ marginTop: 16 }}>
              <Text strong>分类分布</Text>
              <div style={{ marginTop: 8 }}>
                <Space wrap>
                  {Object.entries(stats?.categories || {}).map(([cat, count]) => (
                    <Tag key={cat}>
                      {cat}: {count as number}
                    </Tag>
                  ))}
                </Space>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24}>
          <Card
            title="全栈诊断"
            extra={
              <Text type="secondary">
                PostgreSQL · Redis · Celery Broker/Worker · MinIO · Qdrant · RAG
              </Text>
            }
            style={{ borderRadius: 12 }}
          >
            {!diagnostics && !diagLoading && (
              <Text type="secondary">点击「一键诊断」检查各中间件与 Worker 状态</Text>
            )}
            {(diagLoading || diagFetching) && !diagnostics && <Spin />}
            {diagnostics && (
              <Table<ServiceCheck>
                rowKey="id"
                size="small"
                pagination={false}
                columns={diagColumns}
                dataSource={diagnostics.checks}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default StatusPage
