import type { MessageRow, RunRow, ThreadDetail } from './api'

export type RunStepState = 'pending' | 'active' | 'completed' | 'failed' | 'cancelled'
export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

const RUN_STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  cancelling: '停止中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已停止',
}

const RUN_STEP_LABELS: Record<string, string> = {
  queued: '任务排队',
  route: '路由与判域',
  workflow: '技能编排与 SQL 执行',
  answer: '组织最终回答',
  completed: '处理完成',
}

function normalizeRunStep(currentStep: string | null | undefined): string {
  if (!currentStep) return ''
  if (currentStep === 'queued') return 'queued'
  if (currentStep === 'completed') return 'completed'
  if (['route', 'workflow', 'answer'].includes(currentStep)) return currentStep
  return ''
}

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
  const normalizedStep = normalizeRunStep(activeRun.current_step)
  const activeIndex = ordered.indexOf(normalizedStep)

  if (activeRun.status === 'completed' || normalizedStep === 'completed') {
    return ordered.map((key) => ({
      key,
      label: RUN_STEP_LABELS[key],
      state: 'completed' as RunStepState,
    }))
  }

  return ordered.map((key, index) => ({
    key,
    label: RUN_STEP_LABELS[key],
    state:
      activeIndex < 0
        ? 'pending'
        : index < activeIndex
          ? 'completed'
          : index === activeIndex
            ? activeRun.status === 'failed'
              ? 'failed'
              : activeRun.status === 'cancelled'
                ? 'cancelled'
                : 'active'
            : 'pending',
  }))
}

export function getRunStatusLabel(status: string | null | undefined): string {
  if (!status) return '未知状态'
  return RUN_STATUS_LABELS[status] || status
}

export function getRunStatusTone(status: string | null | undefined): StatusTone {
  switch (status) {
    case 'running':
    case 'pending':
      return 'info'
    case 'completed':
      return 'success'
    case 'cancelling':
      return 'warning'
    case 'failed':
      return 'danger'
    case 'cancelled':
      return 'neutral'
    default:
      return 'neutral'
  }
}

export function getRunStepLabel(currentStep: string | null | undefined): string {
  if (!currentStep) return ''
  return RUN_STEP_LABELS[normalizeRunStep(currentStep)] || currentStep
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

    const formatter = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })

    const parts = formatter.formatToParts(date)
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
    return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}:${values.second}`
  } catch {
    return String(isoString).replace('T', ' ').split('.')[0]
  }
}
