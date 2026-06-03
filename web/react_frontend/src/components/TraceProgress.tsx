// SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
// SPDX-License-Identifier: Apache-2.0

import React from 'react'
import { Spin, Typography } from 'antd'

const { Text, Link } = Typography

export interface TraceStep {
  node: string
  label: string
  status?: string
  skills?: string[]
  skill?: string
}

export interface TraceProgressProps {
  steps: TraceStep[]
  statusMessage?: string
  traceId?: string | null
  langfuseUrl?: string | null
  isAdmin?: boolean
  compact?: boolean
}

const TraceProgress: React.FC<TraceProgressProps> = ({
  steps,
  statusMessage,
  langfuseUrl,
  isAdmin,
}) => {
  const latestStep = steps.length > 0 ? steps[steps.length - 1] : null
  const message =
    (latestStep?.label ? `${latestStep.label}…` : null) ||
    statusMessage ||
    '正在思考…'

  return (
    <div className="grok-trace">
      <Spin size="small" />
      <Text className="grok-trace-text">{message}</Text>
      {isAdmin && langfuseUrl && (
        <Link href={langfuseUrl} target="_blank" rel="noreferrer" className="grok-trace-link">
          Trace
        </Link>
      )}
    </div>
  )
}

export default TraceProgress
