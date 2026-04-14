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
        <div key={thread.public_id} className="thread-row">
          <button 
            className={`thread-item ${thread.public_id === activeThreadId ? 'active' : ''}`} 
            onClick={() => onSelect(thread.public_id)}
          >
            {thread.title || '新会话'}
          </button>
          <button 
            className="thread-delete" 
            disabled={busy} 
            onClick={() => onDelete(thread.public_id)}
            title="删除会话"
          >
            ✕
          </button>
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
    <div className="run-panel">
      <div className="run-panel-head">
        <div>
          <span className="badge badge-blue">{activeRun.status}</span>
          <span style={{ marginLeft: '8px', fontSize: '0.875rem', color: '#64748b' }}>{activeRunDetail}</span>
        </div>
        {hasRunningRun && (
          <button 
            className="btn btn-danger" 
            style={{ padding: '4px 12px' }}
            onClick={onCancel} 
            disabled={busy || activeRun.status === 'cancelling'}
          >
            {activeRun.status === 'cancelling' ? '停止中...' : '停止运行'}
          </button>
        )}
      </div>
      <div className="run-steps">
        {runSteps.map((step) => (
          <div key={step.key} className={`run-step ${step.state}`}>
            <span className="run-step-marker">
              {step.state === 'completed' ? '✓' : step.state === 'active' ? '●' : '○'}
            </span>
            <span>{step.label}</span>
          </div>
        ))}
      </div>
    </div>
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
    <main className="main-panel">
      <header className="chat-header">
        <div>
          <h2>{activeThreadTitle || 'BOE Data Copilot'}</h2>
          {activeThread?.updated_at && (
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>上次更新：{activeThread.updated_at}</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
           {activeRun && <span className="badge badge-gray">{activeRun.current_step}</span>}
        </div>
      </header>

      <div className="message-list">
        {renderMainTimeline()}
        {renderRunInspector()}
        {busy && (
          <div style={{ textAlign: 'center', padding: '1rem', color: '#64748b', fontSize: '0.875rem' }}>
            <span className="loading-dots">正在思考中</span>
          </div>
        )}
      </div>

      <div className="composer-area">
        <div className="composer-container">
          <form onSubmit={onSend} className="composer-input-wrap">
            <textarea 
              value={question} 
              onChange={(e) => onQuestionChange(e.target.value)} 
              placeholder={renderComposerHint || "输入业务问题，例如：上周 A1 产品的产出是多少？"} 
              rows={3} 
            />
            <div className="composer-actions">
              <button 
                type="submit" 
                className="btn btn-primary" 
                disabled={!canSend}
              >
                {busy ? '处理中...' : '发送问题'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
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
    <div className="admin-content">
      <div className="auth-panel" style={{ margin: '2rem auto', boxShadow: 'var(--shadow-lg)' }}>
        <h2>修改个人密码</h2>
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <input 
            className="input"
            value={currentPassword} 
            onChange={(e) => onCurrentPasswordChange(e.target.value)} 
            type="password" 
            placeholder="当前密码" 
          />
          <input 
            className="input"
            value={newPassword} 
            onChange={(e) => onNewPasswordChange(e.target.value)} 
            type="password" 
            placeholder="新密码" 
          />
          <button type="submit" className="btn btn-primary" disabled={busy}>更新密码</button>
        </form>
      </div>
    </div>
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
    <div className="admin-content">
      <h2 style={{ marginBottom: '1.5rem' }}>用户管理</h2>
      <div className="card-grid">
        {adminUsers.map((user) => (
          <article key={user.id} className="data-card">
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <h4>{user.username}</h4>
              <span className={`badge ${user.is_active ? 'badge-green' : 'badge-gray'}`}>
                {user.is_active ? '已启用' : '已禁用'}
              </span>
            </div>
            <div style={{ fontSize: '0.875rem', color: '#64748b' }}>
              角色：{user.roles.map(r => <span key={r} className="badge badge-gray" style={{ marginLeft: '4px' }}>{r}</span>)}
            </div>
            <div className="user-actions">
              <button className="btn btn-ghost" style={{ flex: 1 }} disabled={busy} onClick={() => onToggleUser(user)}>
                {user.is_active ? '禁用用户' : '启用用户'}
              </button>
              <button className="btn btn-ghost" style={{ flex: 1 }} disabled={busy} onClick={() => onToggleAdmin(user)}>
                {user.roles.includes('admin') ? '取消管理员' : '设为管理员'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <input 
                style={{ flex: 1 }}
                value={drafts[user.id] || ''} 
                onChange={(e) => onDraftChange(user.id, e.target.value)} 
                placeholder="重置密码" 
              />
              <button className="btn btn-primary" style={{ padding: '8px 12px' }} disabled={busy} onClick={() => onResetPassword(user)}>
                重置
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

type AuditPanelProps = { audits: AuditRow[] }

export function AuditPanel({ audits }: AuditPanelProps) {
  return (
    <div className="admin-content">
      <h2 style={{ marginBottom: '1.5rem' }}>审计日志</h2>
      <div className="result-table-wrap">
        <table className="result-table">
          <thead>
            <tr>
              <th>操作</th>
              <th>目标</th>
              <th>状态</th>
              <th>操作人</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((row) => (
              <tr key={row.id}>
                <td><span className="badge badge-blue">{row.action}</span></td>
                <td>{row.target_type} / {row.target_id}</td>
                <td>{row.status}</td>
                <td>{row.actor_username || 'system'}</td>
                <td>{row.created_at || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
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
      <div className="message-bubble">
        {message.content}
        
        {message.role === 'assistant' && (rows.length > 0 && columns.length > 0) && (
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
            {rows.length > 10 && (
              <div style={{ padding: '8px', textAlign: 'center', fontSize: '0.75rem', color: '#64748b', background: '#f8fafc' }}>
                仅展示前 10 条结果
              </div>
            )}
          </div>
        )}

        {message.role === 'assistant' && sqlQuery && (
          <div className="sql-block">
            <div className="sql-block-header">
              <span>SQL Query</span>
              <span>PostgreSQL / MySQL</span>
            </div>
            <pre>{sqlQuery}</pre>
          </div>
        )}
      </div>

      <div className="message-meta">
        <span>{message.created_at || ''}</span>
        {message.role === 'assistant' && (
          <>
            {route?.route && <span>• 路由：{String(route.route)}</span>}
            {activeSkill && <span>• 技能：{activeSkill}</span>}
            {rowCount > 0 && <span>• 共 {rowCount} 条数据</span>}
          </>
        )}
      </div>

      {message.role === 'assistant' && canRegenerate && (
        <div className="message-actions" style={{ marginTop: '0.5rem' }}>
          <button className="btn btn-ghost" style={{ padding: '4px 12px', fontSize: '0.75rem' }} disabled={busy} onClick={() => onRegenerate(message.id)}>
            重新生成回复
          </button>
        </div>
      )}
    </article>
  )
}
