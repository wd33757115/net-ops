import React from 'react'

type ChipTone = 'default' | 'ok' | 'warn'

export function GrokChip({ children, tone = 'default' }: { children: React.ReactNode; tone?: ChipTone }) {
  return <span className={`grok-chip${tone !== 'default' ? ` is-${tone}` : ''}`}>{children}</span>
}

interface GrokToolBtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode
  primary?: boolean
}

export function GrokToolBtn({ icon, children, primary, className = '', ...rest }: GrokToolBtnProps) {
  return (
    <button
      type="button"
      className={`grok-tool-btn${primary ? ' is-primary' : ''}${className ? ` ${className}` : ''}`}
      {...rest}
    >
      {icon ? <span className="grok-tool-btn-icon">{icon}</span> : null}
      {children ? <span>{children}</span> : null}
    </button>
  )
}

interface GrokRowActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode
  danger?: boolean
}

export function GrokRowAction({ icon, children, danger, className = '', ...rest }: GrokRowActionProps) {
  return (
    <button
      type="button"
      className={`grok-row-action${danger ? ' is-danger' : ''}${className ? ` ${className}` : ''}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  )
}

export function GrokInfoBar({ children }: { children: React.ReactNode }) {
  return <div className="grok-info-bar">{children}</div>
}

export function statusChipTone(status: string): ChipTone {
  if (status === 'ok' || status === 'healthy' || status === 'success') return 'ok'
  if (status === 'degraded' || status === 'warning' || status === 'down' || status === 'unhealthy') return 'warn'
  return 'default'
}
