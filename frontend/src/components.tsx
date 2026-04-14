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
            {thread.title || '未命名会话'}
          </button>
          <button 
            className="thread-delete" 
            disabled={busy} 
            onClick={() => onDelete(thread.public_id)}
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

export function RunPanel({ activeRun, busy, runSteps, hasRunningRun, onCancel }: RunPanelProps) {
  if (!activeRun) return null
  return (
    <div className="status-bar" style={{ marginBottom: '1.5rem', justifyContent: 'center' }}>
      {runSteps.map((step) => (
        <div key={step.key} className={`status-pill ${step.state === 'active' ? 'active' : ''}`}>
           {step.state === 'completed' ? '✓' : ''} {step.label}
        </div>
      ))}
      {hasRunningRun && (
        <button className="btn-ghost" style={{ marginLeft: '12px', borderColor: '#ef4444', color: '#ef4444' }} onClick={onCancel} disabled={busy || activeRun.status === 'cancelling'}>
          {activeRun.status === 'cancelling' ? '停止中...' : '停止运行'}
        </button>
      )}
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
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <h2>{activeThreadTitle || '新建对话'}</h2>
          {activeThread?.updated_at && <span style={{ fontSize: '0.7rem', color: '#3f3f46' }}>{activeThread.updated_at}</span>}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {activeRun && <span className="status-pill active">{activeRun.current_step}</span>}
        </div>
      </header>

      <div className="message-list">
        {renderMainTimeline()}
        {renderRunInspector()}
        {busy && (
          <div className="busy-indicator">
            <span className="thinking-text" style={{ color: 'var(--primary-color)', fontWeight: 600 }}>BOE Copilot 正在处理中...</span>
          </div>
        )}
      </div>

      <div className="composer-area">
        <div className="composer-container">
          <form onSubmit={onSend} className="composer-dock">
            <textarea 
              value={question} 
              onChange={(e) => onQuestionChange(e.target.value)} 
              placeholder={renderComposerHint || "询问关于生产、库存或计划的问题..."} 
              rows={1} 
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  onSend(e as any);
                }
              }}
            />
            <div className="composer-toolbar">
              <div style={{ display: 'flex', gap: '8px' }}>
                 {/* Placeholder for future tools */}
              </div>
              <button type="submit" className="btn-send" disabled={!canSend}>
                {busy ? '...' : '发送'}
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
    <div className="auth-shell">
      <div className="auth-card" style={{ maxWidth: '400px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '2rem' }}>账号安全</h2>
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="input-group">
            <input type="password" value={currentPassword} onChange={(e) => onCurrentPasswordChange(e.target.value)} placeholder="当前密码" />
            <input type="password" value={newPassword} onChange={(e) => onNewPasswordChange(e.target.value)} placeholder="设置新密码" />
          </div>
          <button type="submit" className="btn-submit" disabled={busy}>更新凭据</button>
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
    <div style={{ padding: '3rem 2rem', maxWidth: '1100px', margin: '0 auto', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: '2.5rem', fontWeight: 800 }}>用户管理</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {adminUsers.map((user) => (
          <div key={user.id} className="embedded-card" style={{ padding: '1.5rem', background: 'rgba(255,255,255,0.01)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <strong style={{ fontSize: '1.1rem' }}>{user.username}</strong>
              <span className={`badge ${user.is_active ? 'badge-green' : 'badge-gray'}`}>{user.is_active ? 'Active' : 'Disabled'}</span>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem' }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => onToggleUser(user)}>{user.is_active ? '禁用' : '启用'}</button>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => onToggleAdmin(user)}>{user.roles.includes('admin') ? '移除管理' : '设为管理'}</button>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input style={{ flex: 1, padding: '0.6rem', fontSize: '0.8rem' }} value={drafts[user.id] || ''} onChange={(e) => onDraftChange(user.id, e.target.value)} placeholder="重置密码" />
              <button className="btn-send" style={{ padding: '0.5rem 1rem' }} onClick={() => onResetPassword(user)}>确认</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

type AuditPanelProps = { audits: AuditRow[] }

export function AuditPanel({ audits }: AuditPanelProps) {
  return (
    <div style={{ padding: '3rem 2rem', maxWidth: '1100px', margin: '0 auto', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: '2.5rem', fontWeight: 800 }}>系统审计</h2>
      <div className="embedded-card">
        <table className="result-table">
          <thead>
            <tr>
              <th>事件</th>
              <th>对象</th>
              <th>状态</th>
              <th>执行人</th>
              <th>时间戳</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((row) => (
              <tr key={row.id}>
                <td style={{ color: 'var(--primary-color)', fontWeight: 600 }}>{row.action}</td>
                <td style={{ color: '#a1a1aa' }}>{row.target_type}</td>
                <td><span className="status-pill">{row.status}</span></td>
                <td>{row.actor_username || 'system'}</td>
                <td style={{ fontSize: '0.75rem', color: '#3f3f46' }}>{row.created_at}</td>
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
      <div className="avatar">
        {message.role === 'assistant' ? 'B' : 'U'}
      </div>
      
      <div className="message-content">
        <div className="message-bubble">
          {message.content}
        </div>

        {message.role === 'assistant' && (rows.length > 0 && columns.length > 0) && (
          <div className="embedded-card">
            <div style={{ overflowX: 'auto' }}>
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
            {rows.length > 10 && (
              <div style={{ padding: '0.6rem', textAlign: 'center', fontSize: '0.7rem', color: '#3f3f46', background: 'rgba(0,0,0,0.3)' }}>
                仅展示前 10 条结果 (共 {rowCount} 条)
              </div>
            )}
          </div>
        )}

        {message.role === 'assistant' && sqlQuery && (
          <div className="embedded-card">
            <div className="sql-header">
              <span>SQL EXECUTOR</span>
              <span>READ-ONLY</span>
            </div>
            <div className="sql-block">
              <pre>{sqlQuery}</pre>
            </div>
          </div>
        )}

        <div className="message-meta">
          <span>{message.created_at}</span>
          {message.role === 'assistant' && (
            <>
              {route?.route && <span style={{ color: 'var(--primary-color)' }}>• {String(route.route).toUpperCase()}</span>}
              {activeSkill && <span>• {activeSkill}</span>}
            </>
          )}
          {message.role === 'assistant' && canRegenerate && (
            <button className="btn-ghost" style={{ padding: '2px 8px', fontSize: '0.7rem' }} onClick={() => onRegenerate(message.id)} disabled={busy}>
              重新生成
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
