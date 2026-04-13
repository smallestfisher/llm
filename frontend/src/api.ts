const API_BASE = '/api'

export type AuthResponse = {
  id: number
  username: string
  roles: string[]
  token: string
  is_active?: boolean
}

export type ThreadSummary = {
  id: number
  public_id: string
  title: string
  updated_at: string | null
}

export type MessageRow = {
  id: number
  turn_id: number | null
  role: string
  content: string
  metadata: Record<string, unknown>
  created_at: string | null
}

export type RunRow = {
  id: number
  public_id: string
  turn_id: number
  kind: string
  status: string
  current_step: string
  route: string
  route_reason: string
  sql_query: string
  error_message: string
  started_at: string | null
  finished_at: string | null
}

export type ThreadDetail = {
  id: number
  public_id: string
  title: string
  updated_at: string | null
  latest_run?: {
    public_id: string
    status: string
    current_step: string
    route: string
    route_reason: string
    sql_query: string
    error_message: string
  } | null
  messages: MessageRow[]
  turns: Array<Record<string, unknown>>
  runs: RunRow[]
}

export type UserRow = {
  id: number
  username: string
  roles: string[]
  is_active: boolean
  created_at: string | null
  last_login_at: string | null
}

export type AuditRow = {
  id: number
  action: string
  target_type: string
  target_id: string
  status: string
  ip_address: string
  details: Record<string, unknown>
  created_at: string | null
  actor_username: string | null
}

function authHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}

async function requireJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let detail = fallback
    try {
      const payload = await response.json()
      detail = payload?.detail || fallback
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return response.json()
}

export async function register(username: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  return requireJson<AuthResponse>(response, '注册失败')
}

export async function login(username: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  return requireJson<AuthResponse>(response, '登录失败')
}

export async function fetchMe(token: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/me`, { headers: authHeaders(token) })
  return requireJson<AuthResponse>(response, '获取当前用户失败')
}

export async function listThreads(token: string): Promise<ThreadSummary[]> {
  const response = await fetch(`${API_BASE}/threads`, {
    headers: authHeaders(token),
  })
  return requireJson<ThreadSummary[]>(response, '获取线程失败')
}

export async function createThread(token: string): Promise<ThreadSummary> {
  const response = await fetch(`${API_BASE}/threads`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return requireJson<ThreadSummary>(response, '创建线程失败')
}

export async function deleteThread(token: string, publicId: string): Promise<{ ok: boolean; public_id: string }> {
  const response = await fetch(`${API_BASE}/threads/${publicId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return requireJson(response, '删除线程失败')
}

export async function fetchThread(token: string, publicId: string): Promise<ThreadDetail> {
  const response = await fetch(`${API_BASE}/threads/${publicId}`, {
    headers: authHeaders(token),
  })
  return requireJson<ThreadDetail>(response, '获取线程详情失败')
}

export type SendMessageResult = {
  thread_id: string
  turn_id: number
  user_message_id: number
  run_id: string
  status: string
}

export type RegenerateResult = {
  thread_id: string
  turn_id: number
  run_id: string
  status: string
}

export async function sendMessage(token: string, publicId: string, question: string): Promise<SendMessageResult> {
  const response = await fetch(`${API_BASE}/threads/${publicId}/messages`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ question }),
  })
  return requireJson<SendMessageResult>(response, '发送消息失败')
}

export async function regenerateMessage(token: string, publicId: string, assistantMessageId: number): Promise<RegenerateResult> {
  const response = await fetch(`${API_BASE}/threads/${publicId}/regenerate`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ assistant_message_id: assistantMessageId }),
  })
  return requireJson<RegenerateResult>(response, '重新生成失败')
}

export async function cancelRun(token: string, publicId: string, runId: string) {
  const response = await fetch(`${API_BASE}/threads/${publicId}/runs/cancel`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ run_id: runId }),
  })
  return requireJson(response, '停止运行失败')
}

export async function changePassword(token: string, currentPassword: string, newPassword: string) {
  const response = await fetch(`${API_BASE}/me/password`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  return requireJson(response, '修改密码失败')
}

export async function listAdminUsers(token: string): Promise<{ items: UserRow[] }> {
  const response = await fetch(`${API_BASE}/admin/users`, {
    headers: authHeaders(token),
  })
  return requireJson(response, '获取用户列表失败')
}

export async function updateUserStatus(token: string, userId: number, isActive: boolean) {
  const response = await fetch(`${API_BASE}/admin/users/${userId}/status`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ is_active: isActive }),
  })
  return requireJson(response, '更新用户状态失败')
}

export async function updateUserRoles(token: string, userId: number, roles: string[]) {
  const response = await fetch(`${API_BASE}/admin/users/${userId}/roles`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ roles }),
  })
  return requireJson(response, '更新用户角色失败')
}

export async function resetUserPassword(token: string, userId: number, newPassword: string) {
  const response = await fetch(`${API_BASE}/admin/users/${userId}/password`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ new_password: newPassword }),
  })
  return requireJson(response, '重置密码失败')
}

export async function listAudits(token: string): Promise<{ items: AuditRow[] }> {
  const response = await fetch(`${API_BASE}/admin/audits`, {
    headers: authHeaders(token),
  })
  return requireJson(response, '获取审计日志失败')
}
