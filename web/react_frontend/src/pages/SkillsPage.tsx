import React, { useState } from 'react'
import { Tabs } from 'antd'
import GrokShellLayout from '../components/layout/GrokShellLayout'
import SkillManageTab from '../components/skills/SkillManageTab'
import WorkflowPluginList from '../components/skills/WorkflowPluginList'
import CollabTemplateTab from '../components/skills/CollabTemplateTab'
import DevGuideTab from '../components/skills/DevGuideTab'
import WorkflowWizard, { WorkflowWizardInitial } from '../components/skills/WorkflowWizard'
import { Card } from 'antd'

const SkillsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('skills')
  const [wizardOpen, setWizardOpen] = useState(false)
  const [wizardInitial, setWizardInitial] = useState<WorkflowWizardInitial | null>(null)

  const openWizard = (initial?: WorkflowWizardInitial) => {
    setWizardInitial(initial || null)
    setWizardOpen(true)
  }

  const tabItems = [
    {
      key: 'skills',
      label: 'Skill 管理',
      children: <SkillManageTab />,
    },
    {
      key: 'workflows',
      label: 'Workflow 插件',
      children: (
        <>
          <WorkflowPluginList onCreateWizard={() => openWizard()} />
          {wizardOpen && activeTab === 'workflows' && (
            <div className="grok-wizard-overlay">
              <Card title="Workflow 创建向导" className="grok-wizard-card">
                <WorkflowWizard
                  open={wizardOpen}
                  onClose={() => setWizardOpen(false)}
                  initial={wizardInitial}
                  onSaved={() => setActiveTab('workflows')}
                />
              </Card>
            </div>
          )}
        </>
      ),
    },
    {
      key: 'collab',
      label: '协同模板',
      children: <CollabTemplateTab />,
    },
    {
      key: 'guide',
      label: '开发指南',
      children: <DevGuideTab />,
    },
  ]

  return (
    <GrokShellLayout
      title="Skills 和连接器"
      subtitle="管理 Skill、编排 Workflow、配置多 Skill 协同与聊天触发"
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        className="grok-skills-tabs"
      />
    </GrokShellLayout>
  )
}

export default SkillsPage
