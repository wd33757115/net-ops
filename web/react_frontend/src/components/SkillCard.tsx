import React from 'react'
import { Card, Switch, Button, Space, Tag, Typography } from 'antd'
import { EyeOutlined, ReloadOutlined, EditOutlined } from '@ant-design/icons'
import { SkillItem } from '../services/api'

const { Text, Paragraph } = Typography

interface SkillCardProps {
  skill: SkillItem
  onToggle: (name: string, enabled: boolean) => void
  onReload: (name: string) => void
  onView: (name: string) => void
  onEdit: (name: string) => void
  loading?: boolean
}

const SkillCard: React.FC<SkillCardProps> = ({
  skill,
  onToggle,
  onReload,
  onView,
  onEdit,
  loading,
}) => {
  return (
    <Card
      size="small"
      style={{ borderRadius: 12, height: '100%' }}
      title={
        <Space>
          <Text strong>{skill.name}</Text>
          <Tag color={skill.enabled ? 'green' : 'default'}>{skill.enabled ? 'active' : 'inactive'}</Tag>
        </Space>
      }
      extra={<Tag>{skill.category}</Tag>}
    >
      <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ minHeight: 44, marginBottom: 12 }}>
        {skill.description || '暂无描述'}
      </Paragraph>
      <Space wrap size={[4, 4]} style={{ marginBottom: 12 }}>
        {(skill.tags || []).slice(0, 4).map((tag) => (
          <Tag key={tag}>{tag}</Tag>
        ))}
      </Space>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          v{skill.version || '1.0.0'}
        </Text>
        <Space>
          <Switch
            checked={skill.enabled}
            loading={loading}
            onChange={(checked) => onToggle(skill.name, checked)}
            checkedChildren="开"
            unCheckedChildren="关"
          />
          <Button size="small" icon={<EyeOutlined />} onClick={() => onView(skill.name)}>
            View
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => onEdit(skill.name)}>
            Edit
          </Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => onReload(skill.name)}>
            Reload
          </Button>
        </Space>
      </div>
    </Card>
  )
}

export default SkillCard
