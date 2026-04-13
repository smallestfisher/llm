import type { FormEvent, ReactNode } from 'react'
import type { AuditRow, MessageRow, RunRow, ThreadDetail, ThreadSummary, UserRow } from './api'

type ThreadListProps = {
  threads: ThreadSummary[]
  activeThreadId: string
  busy: boolean
  onSelect: (publicId: string) => void
  onDelete: (publicId: string) => void
}

export function ThreadList({ threads, activeThreadId, busy, onSelect, onDelete }: ThreadListProps) {
  return (
    <div className="thread-list">
      {threads.map((thread) => (
        <div key={thread.public_id} className={`thread-row ${thread.public_id === activeThreadId ? 'active' : ''}`}>
          <button className={`thread-item ${thread.public_id === activeThreadId ? 'active' : ''}`} onClick={() => onSelect(thread.public_id)}>
            <span>{thread.title}</span>
          </button>
          <button className="thread-delete" disabled={busy} onClick={() => onDelete(thread.public_id)}>删除</button>
        </div>
      ))}
    </div>
  )
}

type RunPanelProps = {
  activeRun: RunRow | null
  busy: boolean
  activeRunDetail: string
  runSteps: Array<{ key: string; label: string; state: string }>
  hasRunningRun: boolean
  onCancel: () => void
}

export function RunPanel({ activeRun, busy, activeRunDetail, runSteps, hasRunningRun, onCancel }: RunPanelProps) {
  if (!activeRun) return null
  return (
    <section className="panel run-panel">
      <div className="run-panel-head">
        <div>
          <h3>运行状态</h3>
          <p>{activeRun.status} · {activeRunDetail}</p>
        </div>
        {hasRunningRun ? <button onClick={onCancel} disabled={busy || activeRun.status === 'cancelling'}>{activeRun.status === 'cancelling' ? '停止中...' : '停止'}</button> : null}
      </div>
      <ol className="run-steps">
        {runSteps.map((step) => (
          <li key={step.key} className={`run-step run-step-${step.state}`}>
            <span className="run-step-marker">{step.state === 'completed' ? '✓' : step.state === 'active' ? '●' : '○'}</span>
            <span>{step.label}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

type ChatPanelProps = {
  activeThreadTitle: string
  activeThread: ThreadDetail | null
  busy: boolean
  activeRun: RunRow | null
  renderMainTimeline: () => ReactNode
  renderRunInspector: () => ReactNode
  renderComposerHint: string
  question: string
  onQuestionChange: (value: string) => void
  onSend: (event: FormEvent) => void
  canSend: boolean
}

export function ChatPanel({
  activeThreadTitle,
  activeThread,
  busy,
  activeRun,
  renderMainTimeline,
  renderRunInspector,
  renderComposerHint,
  question,
  onQuestionChange,
  onSend,
  canSend,
}: ChatPanelProps) {
  return (
    <section className="panel chat-panel">
      <div className="chat-header">
        <div>
          <h2>{activeThreadTitle}</h2>
          <div className="thread-header-meta">
            {activeRun ? (
              <div className="run-snapshot">
                <span>当前运行</span>
                <strong>{activeRun.status}</strong>
                <span>{activeRun.current_step}</span>
              </div>
            ) : null}
            {activeThread?.updated_at ? <span>更新时间：{activeThread.updated_at}</span> : null}
          </div>
        </div>
      </div>
      {busy ? <div className="busy-banner">当前正在与重构版后端同步，请稍候…</div> : null}
      {renderMainTimeline()}
      {renderRunInspector()}
      <form className="composer" onSubmit={onSend}>
        <label className="composer-hint">{renderComposerHint}</label>
        <textarea value={question} onChange={(e) => onQuestionChange(e.target.value)} placeholder="输入业务问题" rows={4} />
        <button type="submit" disabled={!canSend}>{busy ? '处理中...' : '发送'}</button>
      </form>
    </section>
  )
}

type ProfilePanelProps = {
  currentPassword: string
  newPassword: string
  busy: boolean
  onCurrentPasswordChange: (value: string) => void
  onNewPasswordChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
}

export function ProfilePanel({ currentPassword, newPassword, busy, onCurrentPasswordChange, onNewPasswordChange, onSubmit }: ProfilePanelProps) {
  return (
    <section className="panel">
      <h2>修改密码</h2>
      <form className="composer" onSubmit={onSubmit}>
        <input value={currentPassword} onChange={(e) => onCurrentPasswordChange(e.target.value)} type="password" placeholder="当前密码" />
        <input value={newPassword} onChange={(e) => onNewPasswordChange(e.target.value)} type="password" placeholder="新密码" />
        <button type="submit" disabled={busy}>更新密码</button>
      </form>
    </section>
  )
}

type AdminUsersPanelProps = {
  adminUsers: UserRow[]
  busy: boolean
  drafts: Record<number, string>
  onDraftChange: (userId: number, value: string) => void
  onToggleUser: (user: UserRow) => void
  onToggleAdmin: (user: UserRow) => void
  onResetPassword: (user: UserRow) => void
}

export function AdminUsersPanel({ adminUsers, busy, drafts, onDraftChange, onToggleUser, onToggleAdmin, onResetPassword }: AdminUsersPanelProps) {
  return (
    <section className="panel">
      <h2>用户管理</h2>
      <div className="table-grid">
        {adminUsers.map((user) => (
          <article key={user.id} className="user-card">
            <strong>{user.username}</strong>
            <div>角色：{user.roles.join(' / ')}</div>
            <div>状态：{user.is_active ? '启用' : '禁用'}</div>
            <div className="user-actions">
              <button className="ghost-button" disabled={busy} onClick={() => onToggleUser(user)}>{user.is_active ? '禁用' : '启用'}</button>
              <button className="ghost-button" disabled={busy} onClick={() => onToggleAdmin(user)}>{user.roles.includes('admin') ? '移除管理员' : '设为管理员'}</button>
            </div>
            <div className="user-reset-row">
              <input value={drafts[user.id] || ''} onChange={(e) => onDraftChange(user.id, e.target.value)} placeholder="新密码" />
              <button className="ghost-button" disabled={busy} onClick={() => onResetPassword(user)}>重置密码</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

type AuditPanelProps = { audits: AuditRow[] }

export function AuditPanel({ audits }: AuditPanelProps) {
  return (
    <section className="panel">
      <h2>审计日志</h2>
      <div className="audit-list">
        {audits.map((row) => (
          <article key={row.id} className="audit-card">
            <strong>{row.action}</strong>
            <div>{row.target_type} / {row.target_id}</div>
            <div>{row.status}</div>
            <div>{row.actor_username || 'system'}</div>
            <div>{row.created_at || ''}</div>
          </article>
        ))}
      </div>
    </section>
  )
}

type MessageCardProps = {
  message: MessageRow
  busy: boolean
  canRegenerate: boolean
  onRegenerate: (messageId: number) => void
}

export function MessageCard({ message, busy, canRegenerate, onRegenerate }: MessageCardProps) {
  const metadata = message.metadata || {}
  const sqlQuery = typeof metadata.sql_query === 'string' ? metadata.sql_query : ''
  const route = metadata.route as Record<string, unknown> | undefined
  const activeSkill = typeof metadata.active_skill === 'string' ? metadata.active_skill : ''
  const rowCount = Number(metadata.row_count || 0)
  const rows = Array.isArray(metadata.rows) ? metadata.rows : []
  const columns = Array.isArray(metadata.columns) ? metadata.columns : []
  return (
    <article className={`message-card ${message.role === 'assistant' ? 'assistant' : 'user'}`}>
      <header className="message-headline">
        <strong>{message.role === 'assistant' ? 'BOE Data Copilot' : '你'}</strong>
        <span>{message.created_at || ''}</span>
      </header>
      <div>{message.content}</div>
      <div className="message-meta">
        {route?.route ? <span>路由：{String(route.route)}</span> : null}
        {activeSkill ? <span>技能：{activeSkill}</span> : null}
        {rowCount ? <span>记录数：{rowCount}</span> : null}
      </div>
      {rows.length && columns.length ? (
        <div className="result-table-wrap">
          <table className="result-table">
            <thead>
              <tr>{columns.map((col) => <th key={String(col)}>{String(col)}</th>)}</tr>
            </thead>
            <tbody>
              {rows.slice(0, 10).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {(Array.isArray(row) ? row : []).map((cell, cellIndex) => <td key={cellIndex}>{String(cell)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {sqlQuery ? (
        <details className="sql-block">
          <summary>查看 SQL</summary>
          <pre>{sqlQuery}</pre>
        </details>
      ) : null}
      {message.role === 'assistant' && canRegenerate ? (
        <div className="message-actions">
          <button className="ghost-button" disabled={busy} onClick={() => onRegenerate(message.id)}>重新生成此条</button>
        </div>
      ) : null}
    </article>
  )
}
