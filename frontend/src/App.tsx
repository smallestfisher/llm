import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import {
  cancelRun,
  changePassword,
  createThread,
  deleteThread,
  fetchMe,
  fetchThread,
  listAdminUsers,
  listAudits,
  listThreads,
  login,
  regenerateMessage,
  register,
  resetUserPassword,
  sendMessage,
  updateUserRoles,
  updateUserStatus,
  type AuditRow,
  type ThreadDetail,
  type ThreadSummary,
  type UserRow,
} from './api'
import { AdminUsersPanel, AuditPanel, ChatPanel, MessageCard, ProfilePanel, RunPanel, ThreadList } from './components'
import { formatDisplayDate, getActiveRun, getActiveRunDetail, getHasRunningRun, getLatestAssistantMessageIds, getRunSteps, isRegeneratableMessage } from './view-models'

const QUICK_SUGGESTIONS = [
  '查看 A1 产线昨天的平均良率',
  '查询 Samsung 目前的在途库存量',
  'OLED 产品过去三个月的产出趋势',
]

const VIEW_OPTIONS: Array<{ key: View; label: string; adminOnly?: boolean }> = [
  { key: 'chat', label: '智能问答' },
  { key: 'profile', label: '个人设置' },
  { key: 'admin-users', label: '用户管理', adminOnly: true },
  { key: 'admin-audits', label: '审计日志', adminOnly: true },
]

const RUN_POLL_INTERVAL_MS = 1200

type Session = {
  token: string
  username: string
  roles: string[]
}

type View = 'chat' | 'profile' | 'admin-users' | 'admin-audits'

function getSessionStorageKey() {
  return 'boe-rewrite-session'
}

function readSession(): Session | null {
  const raw = window.localStorage.getItem(getSessionStorageKey())
  if (!raw) return null
  try {
    return JSON.parse(raw) as Session
  } catch {
    window.localStorage.removeItem(getSessionStorageKey())
    return null
  }
}

function writeSession(session: Session) {
  window.localStorage.setItem(getSessionStorageKey(), JSON.stringify(session))
}

function clearSessionStorage() {
  window.localStorage.removeItem(getSessionStorageKey())
}

function normalizeSession(auth: { token: string; username: string; roles: string[] }): Session {
  return { token: auth.token, username: auth.username, roles: auth.roles }
}

function isAdminSession(session: Session | null) {
  return session?.roles.includes('admin') ?? false
}

function resolveNextThreadId(rows: ThreadSummary[], preferredThreadId: string, currentThreadId: string) {
  if (preferredThreadId && rows.some((row) => row.public_id === preferredThreadId)) {
    return preferredThreadId
  }
  if (currentThreadId && rows.some((row) => row.public_id === currentThreadId)) {
    return currentThreadId
  }
  return rows[0]?.public_id || ''
}

function renderQuickSuggestions(onPickQuickSuggestion: (value: string) => void) {
  return (
    <div className="quick-suggestions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
      {QUICK_SUGGESTIONS.map((item) => (
        <button key={item} className="suggestion-chip" type="button" onClick={() => onPickQuickSuggestion(item)}>
          {item}
        </button>
      ))}
    </div>
  )
}

function renderEmptyThread(onPickQuickSuggestion: (value: string) => void) {
  return (
    <div className="embedded-card" style={{ margin: '4rem auto', maxWidth: '640px', textAlign: 'center', padding: '4rem 2rem', background: 'rgba(255,255,255,0.4)', backdropFilter: 'blur(20px)' }}>
      <div className="auth-logo" style={{ width: '64px', height: '64px', fontSize: '1.8rem', marginBottom: '2rem' }}>B</div>
      <h2 style={{ fontSize: '1.75rem', fontWeight: 800, marginBottom: '1rem', letterSpacing: '-0.03em' }}>开启业务探索</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '2.5rem', lineHeight: 1.6 }}>
        我是您的制造业数据助手。您可以直接查询生产、库存、计划等实时指标，或进行复杂的多维分析。
      </p>
      {renderQuickSuggestions(onPickQuickSuggestion)}
    </div>
  )
}

function renderRunInspector(activeRun: ReturnType<typeof getActiveRun>): ReactNode {
  if (!activeRun) return null
  return (
    <details className="embedded-card" style={{ background: 'rgba(255,255,255,0.2)' }}>
      <summary style={{ padding: '0.75rem 1.25rem', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Debug Inspector
      </summary>
      <div style={{ padding: '1.25rem', borderTop: '1px solid var(--border-subtle)', display: 'grid', gap: '0.75rem', fontSize: '0.8rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Run ID</strong> <span style={{ fontFamily: 'monospace' }}>{activeRun.public_id}</span></div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Status</strong> <span className="status-pill active">{activeRun.status}</span></div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Step</strong> <span style={{ color: 'var(--primary-color)', fontWeight: 600 }}>{activeRun.current_step}</span></div>
        {activeRun.route && <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Route</strong> <span>{activeRun.route}</span></div>}
        {activeRun.sql_query && (
           <div style={{ marginTop: '0.5rem' }}>
             <strong style={{ display: 'block', marginBottom: '0.5rem' }}>SQL Query</strong>
             <pre style={{ margin: 0, padding: '1rem', background: '#f2f2f7', color: '#444', borderRadius: '10px', overflow: 'auto', fontSize: '0.75rem' }}>
               {activeRun.sql_query}
             </pre>
           </div>
        )}
        {activeRun.error_message && (
          <div style={{ color: '#ff3b30', marginTop: '0.5rem' }}>
            <strong>Error Message</strong>
            <pre style={{ whiteSpace: 'pre-wrap', marginTop: '0.5rem', background: '#fff2f2', padding: '1rem', borderRadius: '10px' }}>{activeRun.error_message}</pre>
          </div>
        )}
      </div>
    </details>
  )
}

function renderTimeline(
  activeThread: ThreadDetail | null,
  latestAssistantMessages: Set<number>,
  busy: boolean,
  onRegenerate: (messageId: number) => void,
  onPickQuickSuggestion: (value: string) => void,
) {
  const messages = activeThread?.messages ?? []
  if (!messages.length) {
    return renderEmptyThread(onPickQuickSuggestion)
  }
  return (
    <>
      {messages.map((message) => (
        <MessageCard
          key={message.id}
          message={message}
          busy={busy}
          canRegenerate={isRegeneratableMessage(message, latestAssistantMessages)}
          onRegenerate={onRegenerate}
        />
      ))}
    </>
  )
}

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [view, setView] = useState<View>('chat')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [activeThreadId, setActiveThreadId] = useState('')
  const [activeThread, setActiveThread] = useState<ThreadDetail | null>(null)
  const [question, setQuestion] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [runBusy, setRunBusy] = useState(false)
  const [isPolling, setIsPolling] = useState(false)
  const [profileCurrentPassword, setProfileCurrentPassword] = useState('')
  const [profileNewPassword, setProfileNewPassword] = useState('')
  const [adminUsers, setAdminUsers] = useState<UserRow[]>([])
  const [audits, setAudits] = useState<AuditRow[]>([])
  const [adminPasswordDrafts, setAdminPasswordDrafts] = useState<Record<number, string>>({})
  const pollTimerRef = useRef<number | null>(null)

  const isAdmin = useMemo(() => isAdminSession(session), [session])
  const activeRun = useMemo(() => getActiveRun(activeThread), [activeThread])
  const runSteps = useMemo(() => getRunSteps(activeRun), [activeRun])
  const latestAssistantMessages = useMemo(() => getLatestAssistantMessageIds(activeThread), [activeThread])
  const activeRunDetail = useMemo(() => getActiveRunDetail(activeRun), [activeRun])
  const hasRunningRun = useMemo(() => getHasRunningRun(activeRun), [activeRun])
  const activeThreadTitle = activeThread?.title || '新对话'
  const canSend = Boolean(!busy && !runBusy && activeThreadId)
  const composerHint = hasRunningRun ? '任务运行中，您可以选择停止运行。' : '输入业务数据查询问题...'

  useEffect(() => {
    const stored = readSession()
    if (stored) {
      setSession(stored)
    }
  }, [])

  useEffect(() => {
    if (!session?.token) return
    void bootstrapSession(session.token)
  }, [session?.token])

  useEffect(() => {
    if (!session?.token || !activeThreadId || !hasRunningRun) {
      stopPolling()
      return
    }
    if (pollTimerRef.current !== null) {
      return
    }
    setIsPolling(true)
    pollTimerRef.current = window.setInterval(() => {
      void refreshThreadDetail(session.token, activeThreadId)
    }, RUN_POLL_INTERVAL_MS)
    return () => stopPolling()
  }, [activeThreadId, hasRunningRun, session?.token])

  function stopPolling() {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    setIsPolling(false)
  }

  async function bootstrapSession(token: string) {
    setBusy(true)
    setError('')
    try {
      const me = await fetchMe(token)
      const nextSession = normalizeSession(me)
      setSession(nextSession)
      writeSession(nextSession)
      await refreshThreads(nextSession.token, '')
      if (isAdminSession(nextSession)) {
        await refreshAdminData(nextSession.token, nextSession.roles)
      } else {
        setAdminUsers([])
        setAudits([])
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '初始化失败'
      setError(message)
      handleLogout()
    } finally {
      setBusy(false)
    }
  }

  async function refreshThreadDetail(token: string, publicId: string) {
    const detail = await fetchThread(token, publicId)
    setActiveThread(detail)
    if (!getHasRunningRun(getActiveRun(detail))) {
      stopPolling()
      setRunBusy(false)
      if (session && isAdminSession(session)) {
        await refreshAdminData(token, session.roles)
      }
    }
    return detail
  }

  async function refreshThreads(token: string, preferredThreadId: string) {
    const rows = await listThreads(token)
    setThreads(rows)
    const nextThreadId = resolveNextThreadId(rows, preferredThreadId, activeThreadId)
    if (!nextThreadId) {
      stopPolling()
      setActiveThreadId('')
      setActiveThread(null)
      return
    }
    setActiveThreadId(nextThreadId)
    await refreshThreadDetail(token, nextThreadId)
  }

  async function refreshAdminData(token: string, roles: string[] = session?.roles || []) {
    if (!roles.includes('admin')) {
      setAdminUsers([])
      setAudits([])
      return
    }
    const [usersResponse, auditsResponse] = await Promise.all([listAdminUsers(token), listAudits(token)])
    setAdminUsers(usersResponse.items)
    setAudits(auditsResponse.items)
  }

  async function handleAuthSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const auth = mode === 'login' ? await login(username, password) : await register(username, password)
      const nextSession = normalizeSession(auth)
      setSession(nextSession)
      writeSession(nextSession)
      setUsername('')
      setPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '认证失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateThread() {
    if (!session) return
    setBusy(true)
    setError('')
    try {
      const created = await createThread(session.token)
      await refreshThreads(session.token, created.public_id)
      setView('chat')
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建线程失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleDeleteThread(publicId: string) {
    if (!session) return
    const confirmed = window.confirm('删除该对话后不可恢复，确认继续吗？')
    if (!confirmed) return
    setBusy(true)
    setError('')
    try {
      await deleteThread(session.token, publicId)
      const nextThreadId = activeThreadId === publicId ? '' : activeThreadId
      await refreshThreads(session.token, nextThreadId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除线程失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleSelectThread(publicId: string) {
    if (!session) return
    setBusy(true)
    setError('')
    try {
      stopPolling()
      setRunBusy(false)
      setActiveThreadId(publicId)
      await refreshThreadDetail(session.token, publicId)
      setView('chat')
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取线程失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleSendMessage(event: FormEvent) {
    event.preventDefault()
    const nextQuestion = question.trim()
    if (!session || !activeThreadId || !nextQuestion) return
    setBusy(true)
    setError('')
    try {
      await sendMessage(session.token, activeThreadId, nextQuestion)
      setQuestion('')
      setRunBusy(true)
      await refreshThreadDetail(session.token, activeThreadId)
      await refreshThreads(session.token, activeThreadId)
    } catch (err) {
      setRunBusy(false)
      setError(err instanceof Error ? err.message : '发送失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleRegenerate(messageId: number) {
    if (!session || !activeThreadId) return
    setBusy(true)
    setError('')
    try {
      await regenerateMessage(session.token, activeThreadId, messageId)
      setRunBusy(true)
      await refreshThreadDetail(session.token, activeThreadId)
      await refreshThreads(session.token, activeThreadId)
    } catch (err) {
      setRunBusy(false)
      setError(err instanceof Error ? err.message : '重新生成失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleCancelRun() {
    if (!session || !activeThreadId || !activeRun?.public_id) return
    setBusy(true)
    setError('')
    try {
      await cancelRun(session.token, activeThreadId, activeRun.public_id)
      setRunBusy(true)
      await refreshThreadDetail(session.token, activeThreadId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '停止失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleChangePassword(event: FormEvent) {
    event.preventDefault()
    if (!session) return
    setBusy(true)
    setError('')
    try {
      await changePassword(session.token, profileCurrentPassword, profileNewPassword)
      setProfileCurrentPassword('')
      setProfileNewPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '修改密码失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleToggleUser(user: UserRow) {
    if (!session) return
    setBusy(true)
    setError('')
    try {
      await updateUserStatus(session.token, user.id, !user.is_active)
      await refreshAdminData(session.token)
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新用户状态失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleToggleAdmin(user: UserRow) {
    if (!session) return
    setBusy(true)
    setError('')
    try {
      const nextRoles = user.roles.includes('admin') ? user.roles.filter((role) => role !== 'admin') : [...new Set([...user.roles, 'admin'])]
      await updateUserRoles(session.token, user.id, nextRoles.length ? nextRoles : ['user'])
      await refreshAdminData(session.token)
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新用户角色失败')
    } finally {
      setBusy(false)
    }
  }

  async function handleResetUserPassword(user: UserRow) {
    if (!session) return
    const nextPassword = (adminPasswordDrafts[user.id] || '').trim()
    if (!nextPassword) return
    setBusy(true)
    setError('')
    try {
      await resetUserPassword(session.token, user.id, nextPassword)
      setAdminPasswordDrafts((current) => ({ ...current, [user.id]: '' }))
      await refreshAdminData(session.token)
    } catch (err) {
      setError(err instanceof Error ? err.message : '重置密码失败')
    } finally {
      setBusy(false)
    }
  }

  async function handlePickQuickSuggestion(text: string) {
    if (!session) return
    setBusy(true)
    setError('')
    try {
      let targetThreadId = activeThreadId
      if (!targetThreadId) {
        const created = await createThread(session.token)
        targetThreadId = created.public_id
        setActiveThreadId(targetThreadId)
        await refreshThreads(session.token, targetThreadId)
      }
      await sendMessage(session.token, targetThreadId, text)
      setQuestion('')
      setRunBusy(true)
      await refreshThreadDetail(session.token, targetThreadId)
      await refreshThreads(session.token, targetThreadId)
    } catch (err) {
      setRunBusy(false)
      setError(err instanceof Error ? err.message : '快捷发送失败')
    } finally {
      setBusy(false)
    }
  }

  function handleLogout() {
    stopPolling()
    setRunBusy(false)
    setSession(null)
    setThreads([])
    setActiveThreadId('')
    setActiveThread(null)
    setAdminUsers([])
    setAudits([])
    setAdminPasswordDrafts({})
    setView('chat')
    clearSessionStorage()
  }

  if (!session) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo">B</div>
            <h1 style={{ marginBottom: '0.5rem', fontSize: '1.75rem', fontWeight: 800 }}>BOE Data Copilot</h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>专业制造业数据问答平台</p>
          </div>

          <div className="auth-tabs">
            <button 
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => { setMode('login'); setError(''); }}
            >
              登录
            </button>
            <button 
              className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
              onClick={() => { setMode('register'); setError(''); }}
            >
              注册
            </button>
          </div>

          <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <input 
                type="text"
                value={username} 
                onChange={(event) => setUsername(event.target.value)} 
                placeholder="用户名" 
                autoComplete="username"
                required
              />
              <input 
                type="password" 
                value={password} 
                onChange={(event) => setPassword(event.target.value)} 
                placeholder="密码" 
                autoComplete="current-password"
                required
              />
            </div>
            
            {error && <div className="error-bubble">{error}</div>}

            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? '正在同步...' : mode === 'login' ? '立即登录' : '创建账号'}
            </button>
          </form>

          <div style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {mode === 'login' ? '欢迎回来，请登录您的工作台' : '新用户请完成系统注册'}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="slim-rail">
        <div 
          className={`rail-item ${view === 'chat' ? 'active' : ''}`} 
          title="问答" 
          onClick={() => setView('chat')}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <div 
          className={`rail-item ${view === 'profile' ? 'active' : ''}`} 
          title="设置" 
          onClick={() => setView('profile')}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </div>
        {isAdmin && (
          <>
            <div 
              className={`rail-item ${view === 'admin-users' ? 'active' : ''}`} 
              title="用户" 
              onClick={() => setView('admin-users')}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            </div>
            <div 
              className={`rail-item ${view === 'admin-audits' ? 'active' : ''}`} 
              title="审计" 
              onClick={() => setView('admin-audits')}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </div>
          </>
        )}
        <div style={{ marginTop: 'auto' }} className="rail-item" title="退出" onClick={handleLogout}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ff3b30" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
        </div>
      </aside>

      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">B</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 800 }}>Data Copilot</span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-desc)' }}>{session.username}</span>
          </div>
        </div>

        <button className="btn-create" onClick={handleCreateThread} disabled={busy || runBusy}>
          + 新建会话
        </button>

        <h3>最近会话</h3>
        <div className="thread-list">
          <ThreadList
            threads={threads}
            activeThreadId={activeThreadId}
            busy={busy || runBusy}
            onSelect={handleSelectThread}
            onDelete={handleDeleteThread}
          />
        </div>
      </aside>

      <main className="main-panel">
        {error && (
          <div style={{ position: 'absolute', top: '20px', left: '50%', transform: 'translateX(-50%)', zIndex: 100 }}>
            <div className="error-bubble" style={{ boxShadow: '0 10px 30px rgba(220, 38, 38, 0.1)' }}>
              {error}
            </div>
          </div>
        )}

        {view === 'chat' ? (
          <ChatPanel
            activeThreadTitle={activeThreadTitle}
            activeThread={activeThread}
            busy={busy || runBusy || isPolling}
            activeRun={activeRun}
            renderMainTimeline={() => renderTimeline(activeThread, latestAssistantMessages, busy || runBusy, handleRegenerate, handlePickQuickSuggestion)}
            renderRunInspector={() => (
              <div style={{ maxWidth: '800px', margin: '0 auto 1.5rem', width: '100%' }}>
                <RunPanel
                  activeRun={activeRun}
                  busy={busy}
                  activeRunDetail={activeRunDetail}
                  runSteps={runSteps}
                  hasRunningRun={hasRunningRun}
                  onCancel={handleCancelRun}
                />
              </div>
            )}
            renderComposerHint={composerHint}
            question={question}
            onQuestionChange={setQuestion}
            onSend={handleSendMessage}
            canSend={canSend}
          />
        ) : null}

        {view === 'profile' ? (
          <ProfilePanel
            currentPassword={profileCurrentPassword}
            newPassword={profileNewPassword}
            busy={busy}
            onCurrentPasswordChange={setProfileCurrentPassword}
            onNewPasswordChange={setProfileNewPassword}
            onSubmit={handleChangePassword}
          />
        ) : null}

        {view === 'admin-users' && isAdmin ? (
          <AdminUsersPanel
            adminUsers={adminUsers}
            busy={busy}
            drafts={adminPasswordDrafts}
            onDraftChange={(userId, value) => setAdminPasswordDrafts((current) => ({ ...current, [userId]: value }))}
            onToggleUser={handleToggleUser}
            onToggleAdmin={handleToggleAdmin}
            onResetPassword={handleResetUserPassword}
          />
        ) : null}

        {view === 'admin-audits' && isAdmin ? <AuditPanel audits={audits} /> : null}
      </main>
    </div>
  )
}
