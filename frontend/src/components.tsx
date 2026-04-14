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
            title="删除"
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
    <div className="status-bar">
      {runSteps.map((step) => (
        <div key={step.key} className={`status-pill ${step.state === 'active' ? 'active' : ''}`}>
           {step.state === 'completed' ? '✓' : ''} {step.label}
        </div>
      ))}
      {hasRunningRun && (
        <button 
          onClick={onCancel} 
          disabled={busy || activeRun.status === 'cancelling'}
          style={{ background: 'transparent', border: 'none', color: '#ef4444', fontSize: '0.75rem', cursor: 'pointer', padding: '0 0.5rem' }}
        >
          {activeRun.status === 'cancelling' ? '停止中...' : '停止'}
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
        <h2>{activeThreadTitle || '新建对话'}</h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          {activeRun && <span className="status-pill">{activeRun.current_step}</span>}
        </div>
      </header>

      <div className="message-list">
        {renderMainTimeline()}
        {renderRunInspector()}
        {busy && (
          <div className="busy-indicator">
            <span className="thinking-text">BOE Data Copilot 正在思考中...</span>
          </div>
        )}
      </div>

      <div className="composer-area">
        <div className="composer-container">
          <form onSubmit={onSend} className="composer-dock">
            <textarea 
              value={question} 
              onChange={(e) => onQuestionChange(e.target.value)} 
              placeholder={renderComposerHint || "发送消息..."} 
              rows={1} 
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  onSend(e as any);
                }
              }}
            />
            <div className="composer-toolbar">
              <span style={{ fontSize: '0.75rem', color: '#3f3f46' }}>Shift + Enter 换行</span>
              <button 
                type="submit" 
                className="send-btn" 
                disabled={!canSend}
              >
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
        <h2 style={{ textAlign: 'center', marginBottom: '1.5rem' }}>安全设置</h2>
        <form onSubmit={onSubmit} className="auth-form">
          <input 
            type="password" 
            value={currentPassword} 
            onChange={(e) => onCurrentPasswordChange(e.target.value)} 
            placeholder="当前密码" 
          />
          <input 
            type="password" 
            value={newPassword} 
            onChange={(e) => onNewPasswordChange(e.target.value)} 
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
    <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: '2rem' }}>用户管理</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
        {adminUsers.map((user) => (
          <div key={user.id} className="embedded-card" style={{ padding: '1.5rem', background: 'rgba(255,255,255,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <strong>{user.username}</strong>
              <span className={`badge ${user.is_active ? 'badge-green' : 'badge-gray'}`}>
                {user.is_active ? 'Active' : 'Disabled'}
              </span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#71717a', marginBottom: '1rem' }}>
              Roles: {user.roles.join(', ')}
            </div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '1rem' }}>
              <button className="nav-item" style={{ flex: 1, justifyContent: 'center', background: 'rgba(255,255,255,0.05)' }} onClick={() => onToggleUser(user)}>
                {user.is_active ? '禁用' : '启用'}
              </button>
              <button className="nav-item" style={{ flex: 1, justifyContent: 'center', background: 'rgba(255,255,255,0.05)' }} onClick={() => onToggleAdmin(user)}>
                {user.roles.includes('admin') ? '降级' : '设为管理员'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input 
                style={{ flex: 1, padding: '0.5rem' }}
                value={drafts[user.id] || ''} 
                onChange={(e) => onDraftChange(user.id, e.target.value)} 
                placeholder="新密码" 
              />
              <button className="send-btn" onClick={() => onResetPassword(user)}>重置</button>
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
    <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: '2rem' }}>审计日志</h2>
      <div className="embedded-card">
        <table className="result-table">
          <thead>
            <tr>
              <th>动作</th>
              <th>目标</th>
              <th>状态</th>
              <th>用户</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((row) => (
              <tr key={row.id}>
                <td>{row.action}</td>
                <td>{row.target_type}</td>
                <td>{row.status}</td>
                <td>{row.actor_username || 'system'}</td>
                <td>{row.created_at}</td>
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
              <div style={{ padding: '0.5rem', textAlign: 'center', fontSize: '0.7rem', color: '#3f3f46', background: 'rgba(0,0,0,0.2)' }}>
                仅展示前 10 条结果 (共 {rowCount} 条)
              </div>
            )}
          </div>
        )}

        {message.role === 'assistant' && sqlQuery && (
          <div className="embedded-card">
            <div className="sql-header">
              <span>SQL QUERY</span>
              <span>EXECUTED</span>
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
              {route?.route && <span>• {String(route.route).toUpperCase()}</span>}
              {activeSkill && <span>• {activeSkill}</span>}
            </>
          )}
          {message.role === 'assistant' && canRegenerate && (
            <button 
              onClick={() => onRegenerate(message.id)} 
              disabled={busy}
              style={{ background: 'transparent', border: 'none', color: '#71717a', fontSize: '0.75rem', cursor: 'pointer', padding: 0 }}
            >
              重新生成
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
