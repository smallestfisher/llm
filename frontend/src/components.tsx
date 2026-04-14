import type { FormEvent, ReactNode } from 'react'
import type { AuditRow, MessageRow, RunRow, ThreadDetail, ThreadSummary, UserRow } from './api'
import { formatDisplayDate } from './view-models'

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
        <div key={thread.public_id} className="thread-row" style={{ position: 'relative' }}>
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
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
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
    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', alignItems: 'center' }}>
      {runSteps.map((step) => (
        <div key={step.key} className={`status-pill ${step.state === 'active' ? 'active' : ''}`}>
           {step.state === 'completed' ? '✓' : ''} {step.label}
        </div>
      ))}
      {hasRunningRun && (
        <button 
          onClick={onCancel} 
          disabled={busy || activeRun.status === 'cancelling'}
          style={{ background: 'transparent', border: 'none', color: '#ff3b30', fontSize: '0.75rem', cursor: 'pointer', marginLeft: '12px', fontWeight: 600 }}
        >
          停止运行
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
          <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>{activeThreadTitle || '新建对话'}</h2>
          {activeThread?.updated_at && <span style={{ fontSize: '0.7rem', color: 'var(--text-desc)' }}>{activeThread.updated_at}</span>}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {activeRun && <span className="status-pill active">{activeRun.current_step}</span>}
        </div>
      </header>

      <div className="message-list">
        {renderMainTimeline()}
        {renderRunInspector()}
        {busy && (
          <div style={{ padding: '2rem', textAlign: 'center' }}>
            <span className="thinking-text">思考中...</span>
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
            <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0.25rem 0.5rem' }}>
              <button type="submit" className="btn-send" disabled={!canSend}>
                {busy ? '...' : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polyline points="22 2 15 22 11 13 2 9 22 2"></polyline></svg>
                )}
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
      <div className="auth-card" style={{ maxWidth: '420px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '2rem', fontWeight: 800 }}>个人设置</h2>
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <input type="password" value={currentPassword} onChange={(e) => onCurrentPasswordChange(e.target.value)} placeholder="当前密码" />
            <input type="password" value={newPassword} onChange={(e) => onNewPasswordChange(e.target.value)} placeholder="新密码" />
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>保存修改</button>
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
      <header style={{ marginBottom: '3rem' }}>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.03em' }}>用户中心</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>管理系统访问权限与安全策略</p>
      </header>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.5rem' }}>
        {adminUsers.map((user) => (
          <div key={user.id} className="embedded-card" style={{ padding: '1.75rem', background: 'rgba(255,255,255,0.6)', backdropFilter: 'blur(10px)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <strong style={{ fontSize: '1.15rem', letterSpacing: '-0.01em' }}>{user.username}</strong>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-desc)', marginTop: '2px' }}>Role: {user.roles.join(', ')}</span>
              </div>
              <span className={`status-pill ${user.is_active ? 'active' : ''}`}>{user.is_active ? 'Active' : 'Banned'}</span>
            </div>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '1.5rem' }}>
              <button 
                className="btn-ghost" 
                style={{ flex: 1, padding: '0.6rem', fontSize: '0.75rem' }} 
                onClick={() => onToggleUser(user)}
              >
                {user.is_active ? '禁用账号' : '激活账号'}
              </button>
              <button 
                className="btn-ghost" 
                style={{ flex: 1, padding: '0.6rem', fontSize: '0.75rem' }} 
                onClick={() => onToggleAdmin(user)}
              >
                {user.roles.includes('admin') ? '取消管理' : '提升管理'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '8px', background: 'rgba(0,0,0,0.03)', padding: '4px', borderRadius: '12px' }}>
              <input style={{ flex: 1, padding: '0.6rem', fontSize: '0.85rem', border: 'none', background: 'transparent' }} value={drafts[user.id] || ''} onChange={(e) => onDraftChange(user.id, e.target.value)} placeholder="新密码" />
              <button className="btn-send" style={{ borderRadius: '10px', padding: '0 1rem' }} onClick={() => onResetPassword(user)}>确认</button>
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
      <header style={{ marginBottom: '3rem' }}>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.03em' }}>安全审计</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>全量系统操作日志实时监控</p>
      </header>
      <div className="embedded-card" style={{ background: '#fff' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ background: '#f8f8fa', color: 'var(--text-secondary)' }}>
              <th style={{ padding: '1.25rem 1rem', textAlign: 'left', fontWeight: 700 }}>动作</th>
              <th style={{ padding: '1.25rem 1rem', textAlign: 'left', fontWeight: 700 }}>目标</th>
              <th style={{ padding: '1.25rem 1rem', textAlign: 'left', fontWeight: 700 }}>状态</th>
              <th style={{ padding: '1.25rem 1rem', textAlign: 'left', fontWeight: 700 }}>操作人</th>
              <th style={{ padding: '1.25rem 1rem', textAlign: 'left', fontWeight: 700 }}>时间</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((row) => (
              <tr key={row.id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <td style={{ padding: '1.25rem 1rem', color: 'var(--primary-color)', fontWeight: 700 }}>{row.action}</td>
                <td style={{ padding: '1.25rem 1rem', color: 'var(--text-secondary)' }}>{row.target_type}</td>
                <td style={{ padding: '1.25rem 1rem' }}><span className="status-pill">{row.status}</span></td>
                <td style={{ padding: '1.25rem 1rem', fontWeight: 500 }}>{row.actor_username || 'system'}</td>
                <td style={{ padding: '1.25rem 1rem', fontSize: '0.75rem', color: 'var(--text-desc)', fontFamily: 'monospace' }}>{formatDisplayDate(row.created_at)}</td>
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
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ background: '#f2f2f7', color: 'var(--text-secondary)' }}>
                    {columns.map((col) => <th key={String(col)} style={{ padding: '0.75rem 1rem', textAlign: 'left' }}>{String(col)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 10).map((row, rowIndex) => (
                    <tr key={rowIndex} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      {(Array.isArray(row) ? row : []).map((cell, cellIndex) => <td key={cellIndex} style={{ padding: '0.75rem 1rem' }}>{String(cell)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rows.length > 10 && (
              <div style={{ padding: '0.6rem', textAlign: 'center', fontSize: '0.7rem', color: 'var(--text-desc)', background: '#fff', borderTop: '1px solid var(--border-subtle)' }}>
                仅展示前 10 条结果 (共 {rowCount} 条)
              </div>
            )}
          </div>
        )}

        {message.role === 'assistant' && sqlQuery && (
          <div className="embedded-card">
            <div className="sql-header">
              <span>SQL ENGINE</span>
              <span>READ ONLY</span>
            </div>
            <div style={{ background: '#f9f9fb', padding: '1rem' }}>
              <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '0.8rem', color: '#444', overflowX: 'auto' }}>{sqlQuery}</pre>
            </div>
          </div>
        )}

        <div className="message-meta">
          <span>{message.created_at}</span>
          {message.role === 'assistant' && (
            <>
              {route?.route && <span style={{ color: 'var(--primary-color)', fontWeight: 600 }}>• {String(route.route).toUpperCase()}</span>}
              {activeSkill && <span>• {activeSkill}</span>}
            </>
          )}
          {message.role === 'assistant' && canRegenerate && (
            <button 
              className="btn-ghost" 
              style={{ padding: '4px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }} 
              onClick={() => onRegenerate(message.id)} 
              disabled={busy}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
              重新生成
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
