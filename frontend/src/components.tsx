import { useEffect, useRef, type FormEvent, type ReactNode } from 'react'
import type { AdminMetricsHistoryResponse, AdminMetricsResponse, AuditRow, MessageRow, RunRow, ThreadDetail, ThreadSummary, UserRow } from './api'
import { formatDisplayDate, getRunStatusLabel, getRunStatusTone, getRunStepLabel, type RunStepState } from './view-models'

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
            title={thread.title || '新会话'}
          >
            <span className="thread-item-label">{thread.title || '新会话'}</span>
          </button>
          <button
            className="thread-delete"
            type="button"
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
  activeRunDetail: string
  runSteps: Array<{ key: string; label: string; state: RunStepState }>
}

function stepTone(state: RunStepState) {
  switch (state) {
    case 'active':
      return 'info'
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    case 'cancelled':
      return 'neutral'
    default:
      return 'neutral'
  }
}

function stepPrefix(state: RunStepState) {
  switch (state) {
    case 'completed':
      return '✓ '
    case 'failed':
      return '! '
    case 'cancelled':
      return '- '
    default:
      return ''
  }
}

export function RunPanel({ activeRun, activeRunDetail, runSteps }: RunPanelProps) {
  if (!activeRun) return null

  const statusLabel = getRunStatusLabel(activeRun.status)
  const statusTone = getRunStatusTone(activeRun.status)
  const stepLabel = getRunStepLabel(activeRun.current_step)

  return (
    <div className="run-panel">
      <div className="run-panel-summary">
        <span className={`status-pill status-pill--${statusTone}`}>{statusLabel}</span>
        {stepLabel && <span className="status-pill status-pill--neutral">当前阶段: {stepLabel}</span>}
        {activeRun.kind && <span className="status-pill status-pill--neutral">模式: {activeRun.kind}</span>}
      </div>
      <div className="run-panel-steps">
        {runSteps.map((step) => (
          <div key={step.key} className={`status-pill status-pill--${stepTone(step.state)}`}>
            {stepPrefix(step.state)}{step.label}
          </div>
        ))}
      </div>
      {activeRunDetail && activeRun.status !== 'completed' && (
        <div className="run-panel-detail">{activeRunDetail}</div>
      )}
    </div>
  )
}

type ChatPanelProps = {
  activeThreadTitle: string
  activeThread: ThreadDetail | null
  busy: boolean
  showThinking: boolean
  hasRunningRun: boolean
  activeRun: RunRow | null
  renderMainTimeline: () => ReactNode
  renderRunInspector: () => ReactNode
  renderComposerHint: string
  question: string
  onQuestionChange: (value: string) => void
  onSend: (event: FormEvent) => void
  onCancel: () => void
  canSend: boolean
}

export function ChatPanel({
  activeThreadTitle,
  activeThread,
  busy,
  showThinking,
  hasRunningRun,
  activeRun,
  renderMainTimeline,
  renderRunInspector,
  renderComposerHint,
  question,
  onQuestionChange,
  onSend,
  onCancel,
  canSend,
}: ChatPanelProps) {
  const messageListRef = useRef<HTMLDivElement | null>(null)
  const isEmptyState = !showThinking && !(activeThread?.messages?.length)
  const headerStatusLabel = activeRun ? getRunStatusLabel(activeRun.status) : ''
  const headerStatusTone = activeRun ? getRunStatusTone(activeRun.status) : 'neutral'
  const headerStepLabel = activeRun ? getRunStepLabel(activeRun.current_step) : ''

  useEffect(() => {
    if (isEmptyState) {
      return
    }

    const container = messageListRef.current
    if (!container) return

    const frameId = window.requestAnimationFrame(() => {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    })

    return () => window.cancelAnimationFrame(frameId)
  }, [activeThread?.public_id, activeThread?.messages?.length, showThinking, isEmptyState])

  return (
    <div className="chat-panel-shell">
      <header className="chat-header">
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>{activeThreadTitle || '新建对话'}</h2>
          {activeThread?.updated_at && <span style={{ fontSize: '0.7rem', color: 'var(--text-desc)' }}>{formatDisplayDate(activeThread.updated_at)}</span>}
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {activeRun && <span className={`status-pill status-pill--${headerStatusTone}`}>{headerStatusLabel}</span>}
          {activeRun && headerStepLabel && <span className="status-pill status-pill--neutral">{headerStepLabel}</span>}
        </div>
      </header>

      {isEmptyState ? (
        <div className="empty-state-panel">
          {renderMainTimeline()}
        </div>
      ) : (
        <div ref={messageListRef} className="message-list">
          {renderMainTimeline()}
          {renderRunInspector()}
          {showThinking && (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <span className="thinking-text">思考中...</span>
            </div>
          )}
        </div>
      )}

      <div className="composer-area">
        <div className="composer-container">
          <form onSubmit={onSend} className="composer-dock">
            <textarea
              value={question}
              onChange={(e) => onQuestionChange(e.target.value)}
              placeholder={renderComposerHint || '发送消息...'}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend(e as any)
                }
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0.25rem 0.5rem' }}>
              <button
                type={hasRunningRun ? 'button' : 'submit'}
                className={`btn-send ${hasRunningRun ? 'is-stop' : ''}`}
                disabled={hasRunningRun ? activeRun?.status === 'cancelling' : !canSend}
                onClick={hasRunningRun ? onCancel : undefined}
              >
                {hasRunningRun ? (activeRun?.status === 'cancelling' ? '停止中' : '停止') : busy ? '...' : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polyline points="22 2 15 22 11 13 2 9 22 2"></polyline></svg>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
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
              <span className={`status-pill ${user.is_active ? 'status-pill--success' : 'status-pill--danger'}`}>{user.is_active ? 'Active' : 'Banned'}</span>
            </div>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '1.5rem' }}>
              <button
                className={`btn-ghost ${user.is_active ? 'is-danger' : ''}`}
                style={{ flex: 1, padding: '0.6rem' }}
                type="button"
                onClick={() => onToggleUser(user)}
              >
                {user.is_active ? '禁用账号' : '激活账号'}
              </button>
              <button
                className={`btn-ghost ${user.roles.includes('admin') ? 'is-danger' : ''}`}
                style={{ flex: 1, padding: '0.6rem' }}
                type="button"
                onClick={() => onToggleAdmin(user)}
              >
                {user.roles.includes('admin') ? '取消管理' : '提升管理'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '8px', background: 'rgba(0,0,0,0.03)', padding: '4px', borderRadius: '12px' }}>
              <input style={{ flex: 1, padding: '0.6rem', fontSize: '0.85rem', border: 'none', background: 'transparent' }} value={drafts[user.id] || ''} onChange={(e) => onDraftChange(user.id, e.target.value)} placeholder="重置密码" />
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
                <td style={{ padding: '1.25rem 1rem' }}><span className="status-pill status-pill--neutral">{row.status}</span></td>
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

type AdminMetricsPanelProps = {
  metrics: AdminMetricsResponse | null
  history: AdminMetricsHistoryResponse | null
  refreshing: boolean
  windowSec: number
  onWindowChange: (value: number) => void
  onRefresh: () => void
}

function formatSeconds(seconds: number) {
  if (!seconds) return '0s'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  if (minutes < 60) return `${minutes}m ${remain}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

function renderCounterRows(data: Record<string, number>, emptyText: string) {
  const entries = Object.entries(data || {}).sort((left, right) => right[1] - left[1])
  if (!entries.length) {
    return <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>{emptyText}</div>
  }
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
      <thead>
        <tr style={{ background: '#f8f8fa', color: 'var(--text-secondary)' }}>
          <th style={{ padding: '0.9rem 1rem', textAlign: 'left', fontWeight: 700 }}>键</th>
          <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>次数</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key} style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <td style={{ padding: '0.9rem 1rem', fontWeight: 600 }}>{key}</td>
            <td style={{ padding: '0.9rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function AdminMetricsPanel({ metrics, history, refreshing, windowSec, onWindowChange, onRefresh }: AdminMetricsPanelProps) {
  const windowData = metrics?.window
  const activeRunStatus = windowData?.run_status || metrics?.run_status || {}
  const activeRouteCounts = windowData?.route_counts || metrics?.route_counts || {}
  const activeCache = windowData?.cache || metrics?.cache || { hit: 0, miss: 0, hit_rate: 0 }
  const activeNodes = windowData?.nodes || metrics?.nodes || {}
  const nodeEntries = Object.entries(activeNodes).sort((left, right) => right[1].count - left[1].count)
  const windowLabelSec = windowData?.window_sec || metrics?.window_sec || windowSec

  const windowOptions = [
    { label: '5m', value: 300 },
    { label: '15m', value: 900 },
    { label: '1h', value: 3600 },
  ]
  const alerts = metrics?.alerts || []
  const historyPoints = history?.points || []

  return (
    <div style={{ padding: '3rem 2rem', maxWidth: '1100px', margin: '0 auto', overflowY: 'auto' }}>
      <header style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.03em' }}>运行指标</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>路由、节点耗时、缓存命中与失败率快照</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="status-pill status-pill--neutral">窗口 {Math.floor(windowLabelSec / 60)}m</span>
          {windowOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className="btn-ghost"
              style={{ padding: '0.45rem 0.75rem', minWidth: '56px', background: windowSec === option.value ? '#fff' : undefined }}
              onClick={() => onWindowChange(option.value)}
            >
              {option.label}
            </button>
          ))}
          <button type="button" className="btn-ghost" style={{ padding: '0.45rem 0.75rem', minWidth: '70px' }} onClick={onRefresh}>
            {refreshing ? '刷新中' : '刷新'}
          </button>
        </div>
      </header>

      {!metrics ? (
        <div className="embedded-card" style={{ padding: '1.2rem 1rem', color: 'var(--text-muted)' }}>
          暂无数据
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '1rem' }}>
            <div className="embedded-card" style={{ padding: '1rem' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Uptime</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{formatSeconds(metrics.uptime_sec)}</div>
            </div>
            <div className="embedded-card" style={{ padding: '1rem' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Inflight Runs</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{metrics.inflight_runs}</div>
            </div>
            <div className="embedded-card" style={{ padding: '1rem' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Cache Hit Rate</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{(activeCache.hit_rate * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-desc)' }}>{activeCache.hit} hit / {activeCache.miss} miss</div>
            </div>
            <div className="embedded-card" style={{ padding: '1rem' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Completed</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{activeRunStatus.completed || 0}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-desc)' }}>
                failed {activeRunStatus.failed || 0} / cancelled {activeRunStatus.cancelled || 0}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '14px', marginBottom: '1rem' }}>
            <div className="embedded-card" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '0.9rem 1rem', fontSize: '0.86rem', fontWeight: 700 }}>Run Status</div>
              {renderCounterRows(activeRunStatus, '暂无状态数据')}
            </div>
            <div className="embedded-card" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '0.9rem 1rem', fontSize: '0.86rem', fontWeight: 700 }}>Route Counts</div>
              {renderCounterRows(activeRouteCounts, '暂无路由数据')}
            </div>
          </div>

          <div className="embedded-card" style={{ overflow: 'hidden', marginBottom: '1rem' }}>
            <div style={{ padding: '0.9rem 1rem', fontSize: '0.86rem', fontWeight: 700 }}>Alerts</div>
            {!alerts.length ? (
              <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>当前窗口无告警</div>
            ) : (
              <div style={{ display: 'grid', gap: '10px', padding: '0.8rem 1rem 1rem' }}>
                {alerts.map((alert) => (
                  <div
                    key={alert.code}
                    style={{
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '10px',
                      padding: '0.75rem 0.9rem',
                      background: alert.level === 'warning' ? 'rgba(255, 245, 240, 0.8)' : 'rgba(245, 249, 255, 0.8)',
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: '4px' }}>{alert.message}</div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                      code={alert.code} value={alert.value} threshold={alert.threshold}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="embedded-card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '0.9rem 1rem', fontSize: '0.86rem', fontWeight: 700 }}>Node Performance</div>
            {!nodeEntries.length ? (
              <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>暂无节点数据</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                <thead>
                  <tr style={{ background: '#f8f8fa', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'left', fontWeight: 700 }}>Node</th>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>Count</th>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>Avg(ms)</th>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>P95(ms)</th>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>Max(ms)</th>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>Failures</th>
                    <th style={{ padding: '0.9rem 1rem', textAlign: 'right', fontWeight: 700 }}>Failure Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {nodeEntries.map(([node, stat]) => (
                    <tr key={node} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '0.9rem 1rem', fontWeight: 600 }}>{node}</td>
                      <td style={{ padding: '0.9rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{stat.count}</td>
                      <td style={{ padding: '0.9rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{stat.avg_ms}</td>
                      <td style={{ padding: '0.9rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{stat.p95_ms ?? '-'}</td>
                      <td style={{ padding: '0.9rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{stat.max_ms}</td>
                      <td style={{ padding: '0.9rem 1rem', textAlign: 'right', color: stat.failure_count > 0 ? '#c62828' : 'var(--text-secondary)', fontFamily: 'monospace' }}>
                        {stat.failure_count}
                      </td>
                      <td style={{ padding: '0.9rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>
                        {typeof stat.failure_rate === 'number' ? `${(stat.failure_rate * 100).toFixed(1)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="embedded-card" style={{ overflow: 'hidden', marginTop: '1rem' }}>
            <div style={{ padding: '0.9rem 1rem', fontSize: '0.86rem', fontWeight: 700 }}>Trend ({history?.bucket_sec || 300}s bucket)</div>
            {!historyPoints.length ? (
              <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>暂无趋势数据</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                <thead>
                  <tr style={{ background: '#f8f8fa', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '0.8rem 1rem', textAlign: 'left', fontWeight: 700 }}>Time</th>
                    <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontWeight: 700 }}>Runs</th>
                    <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontWeight: 700 }}>Fail Rate</th>
                    <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontWeight: 700 }}>P95 Run(ms)</th>
                    <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontWeight: 700 }}>Cache Hit</th>
                  </tr>
                </thead>
                <tbody>
                  {historyPoints.slice(-20).map((point) => (
                    <tr key={point.ts} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '0.8rem 1rem', fontFamily: 'monospace' }}>{formatDisplayDate(new Date(point.ts * 1000).toISOString())}</td>
                      <td style={{ padding: '0.8rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{point.run_count}</td>
                      <td style={{ padding: '0.8rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{(point.failure_rate * 100).toFixed(1)}%</td>
                      <td style={{ padding: '0.8rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{point.p95_run_ms}</td>
                      <td style={{ padding: '0.8rem 1rem', textAlign: 'right', fontFamily: 'monospace' }}>{(point.cache_hit_rate * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
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
          <span>{formatDisplayDate(message.created_at)}</span>
          {message.role === 'assistant' && (
            <>
              {route?.route && <span style={{ color: 'var(--primary-color)', fontWeight: 600 }}>• {String(route.route).toUpperCase()}</span>}
              {activeSkill && <span>• {activeSkill}</span>}
            </>
          )}
          {message.role === 'assistant' && canRegenerate && (
            <button
              className="btn-ghost message-regenerate"
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
