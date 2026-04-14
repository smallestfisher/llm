import type { MessageRow, RunRow, ThreadDetail } from './api'

export function getActiveRun(activeThread: ThreadDetail | null): RunRow | null {
  if (!activeThread?.runs?.length) return null
  const runs = [...activeThread.runs]
  runs.sort((a, b) => {
    const left = a.started_at || ''
    const right = b.started_at || ''
    return left < right ? 1 : -1
  })
  return runs.find((run) => ['running', 'pending', 'cancelling'].includes(run.status)) || runs[0] || null
}

export function getRunSteps(activeRun: RunRow | null) {
  if (!activeRun) return []
  const ordered = ['route', 'workflow', 'answer']
  const labels: Record<string, string> = {
    route: '路由与判域',
    workflow: '技能编排与 SQL 执行',
    answer: '组织最终回答',
  }
  const activeIndex = ordered.indexOf(activeRun.current_step || '')
  return ordered.map((key, index) => ({
    key,
    label: labels[key],
    state: activeIndex < 0 ? 'pending' : index < activeIndex ? 'completed' : index === activeIndex ? 'active' : 'pending',
  }))
}

export function getLatestAssistantMessageIds(activeThread: ThreadDetail | null): Set<number> {
  if (!activeThread) return new Set<number>()
  const ids = new Set<number>()
  for (const turn of activeThread.turns) {
    const assistantId = Number(turn.latest_assistant_message_id || 0)
    if (assistantId) ids.add(assistantId)
  }
  return ids
}

export function getActiveRunDetail(activeRun: RunRow | null): string {
  if (!activeRun) return ''
  if (activeRun.error_message) return activeRun.error_message
  if (activeRun.route_reason) return activeRun.route_reason
  return activeRun.current_step
}

export function getHasRunningRun(activeRun: RunRow | null): boolean {
  return Boolean(activeRun && ['running', 'pending', 'cancelling'].includes(activeRun.status))
}

export function getIsTerminalRun(activeRun: RunRow | null): boolean {
  return Boolean(activeRun && ['completed', 'failed', 'cancelled'].includes(activeRun.status))
}

export function isRegeneratableMessage(message: MessageRow, latestAssistantMessages: Set<number>) {
  return message.role === 'assistant' && latestAssistantMessages.has(message.id)
}

export function formatDisplayDate(isoString: string | null | undefined): string {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    if (isNaN(date.getTime())) return isoString.replace('T', ' ').split('.')[0]
    
    const Y = date.getFullYear()
    const M = String(date.getMonth() + 1).padStart(2, '0')
    const D = String(date.getDate()).padStart(2, '0')
    const h = String(date.getHours()).padStart(2, '0')
    const m = String(date.getMinutes()).padStart(2, '0')
    const s = String(date.getSeconds()).padStart(2, '0')
    
    return `${Y}-${M}-${D} ${h}:${m}:${s}`
  } catch {
    return String(isoString).replace('T', ' ').split('.')[0]
  }
}
