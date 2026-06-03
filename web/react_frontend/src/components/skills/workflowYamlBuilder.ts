// SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
// SPDX-License-Identifier: Apache-2.0

/**
 * 从向导表单生成 WORKFLOW.yaml / 同步 CHAT.intent.yaml
 */

export interface SkillChainConfig {
  pluginName: string
  description?: string
  step1Name?: string
  step1Label?: string
  step1Skill: string
  step2Name?: string
  step2Label?: string
  step2Skill?: string
  includeLlmAnalysis?: boolean
}

export function buildWorkflowYaml(config: SkillChainConfig): string {
  const {
    pluginName,
    description = '自定义 Workflow',
    step1Name = 'step_one',
    step1Label = '第一步',
    step1Skill,
    step2Name = 'step_two',
    step2Label = '第二步',
    step2Skill,
    includeLlmAnalysis = true,
  } = config

  const lines: string[] = [
    `name: ${pluginName}`,
    `description: ${description}`,
    'version: "1.0"',
    '',
    'steps:',
    `  - name: ${step1Name}`,
    `    label: ${step1Label}`,
    `    skill: ${step1Skill}`,
    '    inputs:',
    '      ticket_id: ${context.ticket_id}',
    '      ticket_title: ${context.ticket_title}',
    '      policy_file_url: ${context.policy_file_url}',
    '      topology_file_url: ${context.topology_file_url}',
    '      requester: ${context.requester}',
    '      assignee: ${context.assignee}',
    '      priority: ${context.priority}',
    '      parameters: ${context.parameters}',
    '      change_background: ${context.change_background}',
    '      change_purpose: ${context.change_purpose}',
    '      requester_dept: ${context.requester_dept}',
    '      due_date: ${context.due_date}',
    '      workflow_run_id: ${run.id}',
  ]

  if (step2Skill) {
    const isChangeTicketWriter = step2Skill === 'itsm-change-ticket-writer'
    const isFirewallGenerator = step1Skill === 'firewall-policy-generator'

    lines.push(
      '',
      `  - name: ${step2Name}`,
      `    label: ${step2Label}`,
      `    skill: ${step2Skill}`,
      '    inputs:',
      '      ticket_id: ${context.ticket_id}',
      '      ticket_title: ${context.ticket_title}',
      '      change_background: ${context.change_background}',
      '      change_purpose: ${context.change_purpose}',
      '      requester: ${context.requester}',
      '      requester_dept: ${context.requester_dept}',
      '      priority: ${context.priority}',
      '      due_date: ${context.due_date}',
      '      assignee: ${context.assignee}',
    )

    if (isChangeTicketWriter && isFirewallGenerator) {
      lines.push(
        `      manifest: \${steps.${step1Name}.result.manifest}`,
        `      config_file_key: \${steps.${step1Name}.artifacts.config_zip.file_key}`,
        `      config_files_url: \${steps.${step1Name}.artifacts.config_zip.download_url}`,
      )
    } else {
      lines.push(`      prev_result: \${steps.${step1Name}.result}`)
    }

    lines.push('      workflow_run_id: ${run.id}')
  }

  if (includeLlmAnalysis) {
    const prevStep = step2Skill ? step2Name : step1Name
    lines.push(
      '',
      '  - name: llm_analysis',
      '    label: LLM 结果分析',
      '    skill: llm-result-analyzer',
      '    inputs:',
      '      ticket_id: ${context.ticket_id}',
      `      prev_result: \${steps.${prevStep}.result}`,
      '      analysis_prompt: ${context.analysis_prompt}',
      '      analysis_focus: ${context.analysis_focus}',
      `      source_step: ${prevStep}`,
      '      workflow_run_id: ${run.id}',
    )
  }

  lines.push(
    '',
    'on_complete:',
    '  message: Workflow 已完成',
    '  notify_each_step: false',
    '  notification:',
    `    title: "流程已完成 (\${context.ticket_id})"`,
    '    body: "所有步骤已执行。"',
    '    level: success',
  )

  return lines.join('\n')
}

/** 从 WORKFLOW.yaml 文本解析 workflow name */
export function parseWorkflowName(yamlText: string): string | null {
  const match = yamlText.match(/^name:\s*['"]?([a-z0-9-]+)['"]?\s*$/m)
  return match ? match[1] : null
}

/** 将 CHAT.intent.yaml 的 workflow 字段与 WORKFLOW name 对齐 */
export function syncChatIntentWorkflow(chatYaml: string, workflowName: string): string {
  if (!chatYaml.trim()) {
    return `workflow: ${workflowName}\npriority: 50\ndescription: 聊天触发\n\nmatch:\n  require_any:\n    - 关键词\n`
  }
  if (/^workflow:\s*.+$/m.test(chatYaml)) {
    return chatYaml.replace(/^workflow:\s*.+$/m, `workflow: ${workflowName}`)
  }
  return `workflow: ${workflowName}\n${chatYaml}`
}

/** 保存前规范化：WORKFLOW name 与插件目录名一致 */
export function normalizeWorkflowYaml(yamlText: string, pluginName: string): string {
  return yamlText.replace(/^name:\s*.+$/m, `name: ${pluginName}`)
}
