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
import { getActiveRun, getActiveRunDetail, getHasRunningRun, getLatestAssistantMessageIds, getRunSteps, isRegeneratableMessage } from './view-models'

const QUICK_SUGGESTIONS = [
  '查看 A1 产线昨天的平均良率',
  '查询 Samsung 目前的在途库存量',
  'OLED 产品过去三个月的产出趋势',
]

const VIEW_OPTIONS: Array<{ key: View; label: string; adminOnly?: boolean }> = [
  { key: 'chat', label: '聊天' },
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
    <div className="quick-suggestions">
      {QUICK_SUGGESTIONS.map((item) => (
        <button key={item} className="ghost-button" type="button" onClick={() => onPickQuickSuggestion(item)}>
          {item}
        </button>
      ))}
    </div>
  )
}

function renderEmptyThread(onPickQuickSuggestion: (value: string) => void) {
  return (
    <section className="panel empty-thread">
      <h2>开始一段新对话</h2>
      <p>先从一个业务问题开始。你可以直接发送问题，或点击下面的建议问题。</p>
      {renderQuickSuggestions(onPickQuickSuggestion)}
    </section>
  )
}

function renderRunInspector(activeRun: ReturnType<typeof getActiveRun>): ReactNode {
  if (!activeRun) return null
  return (
    <details className="run-inspector">
      <summary>查看当前运行详情</summary>
      <div className="run-inspector-grid">
        <div>
          <strong>状态</strong>
          <span>{activeRun.status}</span>
        </div>
        <div>
          <strong>步骤</strong>
          <span>{activeRun.current_step}</span>
        </div>
        <div>
          <strong>路由</strong>
          <span>{activeRun.route || '-'}</span>
        </div>
        <div>
          <strong>原因</strong>
          <span>{activeRun.route_reason || '-'}</span>
        </div>
      </div>
      {activeRun.sql_query ? <pre className="run-inspector-pre">{activeRun.sql_query}</pre> : null}
      {activeRun.error_message ? <pre className="run-inspector-pre error-pre">{activeRun.error_message}</pre> : null}
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
    <div className="message-list">
      {messages.map((message) => (
        <MessageCard
          key={message.id}
          message={message}
          busy={busy}
          canRegenerate={isRegeneratableMessage(message, latestAssistantMessages)}
          onRegenerate={onRegenerate}
        />
      ))}
    </div>
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
  const composerHint = hasRunningRun ? '当前有运行中的任务，可停止后继续操作。' : '输入业务问题，重构版将逐步接入完整工作流。'

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
        <form className="panel auth-panel" onSubmit={handleAuthSubmit}>
          <h1>BOE Data Copilot</h1>
          <p>{mode === 'login' ? '登录到重构版工作台' : '注册重构版账号'}</p>
          <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="用户名" />
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="密码" />
          {error ? <div className="error-text">{error}</div> : null}
          <button type="submit" disabled={busy}>{busy ? '处理中...' : mode === 'login' ? '登录' : '注册'}</button>
          <button type="button" className="ghost-button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? '切换到注册' : '切换到登录'}
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-head">
          <div>
            <h1>BOE Data Copilot</h1>
            <p>{session.username}</p>
          </div>
          <button onClick={handleCreateThread} disabled={busy || runBusy}>新建对话</button>
        </div>
        <nav className="nav-list">
          {VIEW_OPTIONS.filter((option) => !option.adminOnly || isAdmin).map((option) => (
            <button
              key={option.key}
              className={`ghost-button ${view === option.key ? 'active-nav' : ''}`}
              onClick={() => setView(option.key)}
            >
              {option.label}
            </button>
          ))}
        </nav>
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          busy={busy || runBusy}
          onSelect={handleSelectThread}
          onDelete={handleDeleteThread}
        />
        <button className="ghost-button" onClick={handleLogout}>退出登录</button>
      </aside>
      <main className="main-panel">
        {error ? <div className="panel error-text">{error}</div> : null}
        {view === 'chat' ? (
          <>
            <RunPanel
              activeRun={activeRun}
              busy={busy}
              activeRunDetail={activeRunDetail}
              runSteps={runSteps}
              hasRunningRun={hasRunningRun}
              onCancel={handleCancelRun}
            />
            <ChatPanel
              activeThreadTitle={activeThreadTitle}
              activeThread={activeThread}
              busy={busy || runBusy || isPolling}
              activeRun={activeRun}
              renderMainTimeline={() => renderTimeline(activeThread, latestAssistantMessages, busy || runBusy, handleRegenerate, setQuestion)}
              renderRunInspector={() => renderRunInspector(activeRun)}
              renderComposerHint={composerHint}
              question={question}
              onQuestionChange={setQuestion}
              onSend={handleSendMessage}
              canSend={canSend}
            />
          </>
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
