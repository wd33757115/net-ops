import React from 'react'
import { Card, Col, Row, Statistic, Typography, Spin, Tag, Space } from 'antd'
import { useQuery } from 'react-query'
import { chatApi, skillApi } from '../services/api'

const { Title, Text } = Typography

const StatusPage: React.FC = () => {
  const { data: health, isLoading: healthLoading } = useQuery('health', chatApi.getHealth)
  const { data: stats, isLoading: statsLoading } = useQuery('skill-stats', skillApi.getStats)

  if (healthLoading || statsLoading) {
    return (
      <div style={{ padding: 80, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      <Title level={3}>系统状态</Title>
      <Text type="secondary">Django BFF 与 FastAPI 后端运行概况</Text>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} md={12}>
          <Card title="服务健康" style={{ borderRadius: 12 }}>
            <pre style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(health, null, 2)}
            </pre>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Skill 统计" style={{ borderRadius: 12 }}>
            <Row gutter={16}>
              <Col span={8}><Statistic title="总数" value={stats?.total_skills || 0} /></Col>
              <Col span={8}><Statistic title="启用" value={stats?.enabled_skills || 0} /></Col>
              <Col span={8}><Statistic title="禁用" value={stats?.disabled_skills || 0} /></Col>
            </Row>
            <div style={{ marginTop: 16 }}>
              <Text strong>分类分布</Text>
              <div style={{ marginTop: 8 }}>
                <Space wrap>
                  {Object.entries(stats?.categories || {}).map(([cat, count]) => (
                    <Tag key={cat}>{cat}: {count as number}</Tag>
                  ))}
                </Space>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default StatusPage
