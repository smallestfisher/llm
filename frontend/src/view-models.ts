import type { MessageRow, RunRow, ThreadDetail } from './api'

export type RunStepState = 'pending' | 'active' | 'completed' | 'failed' | 'cancelled'
export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export type QueryStateView = {
  mode: string
  confidence: number | null
  reason: string
  operationType: string
  operationFamily: string
  operationSummary: string
  domain: string
  domains: string[]
  metric: string
  intent: string
  queryText: string
  dimensions: string[]
  filters: Record<string, unknown>
  presentation: Record<string, unknown>
}

type RunStepDefinition = {
  key: string
  label: string
}

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
  route_intent: '路由与判域',
  cross_domain_compose: '跨域拆解',
  skill_dispatch: '技能分发',
  check_guard: '问题校验',
  workflow: '技能编排与 SQL 执行',
  refine_filters: '过滤条件整理',
  get_schema: '载入表结构',
  write_sql: '生成 SQL',
  execute_sql: '执行 SQL',
  reflect_sql: 'SQL 修正重试',
  answer: '组织最终回答',
  generate_answer: '组织最终回答',
  cross_domain_merge: '跨域结果汇总',
  completed: '处理完成',
  generic_skill: '通用技能执行',
  production_skill: '生产技能执行',
  planning_skill: '计划技能执行',
  inventory_skill: '库存技能执行',
  demand_skill: '需求技能执行',
  sales_skill: '销售技能执行',
}

const SKILL_STEP_KEYS = [
  'generic_skill',
  'production_skill',
  'planning_skill',
  'inventory_skill',
  'demand_skill',
  'sales_skill',
] as const

const DEFAULT_RUN_STEPS: RunStepDefinition[] = [
  { key: 'route_intent', label: RUN_STEP_LABELS.route_intent },
  { key: 'skill_dispatch', label: RUN_STEP_LABELS.skill_dispatch },
  { key: 'check_guard', label: RUN_STEP_LABELS.check_guard },
  { key: 'refine_filters', label: RUN_STEP_LABELS.refine_filters },
  { key: 'get_schema', label: RUN_STEP_LABELS.get_schema },
  { key: 'write_sql', label: RUN_STEP_LABELS.write_sql },
  { key: 'execute_sql', label: RUN_STEP_LABELS.execute_sql },
  { key: 'reflect_sql', label: RUN_STEP_LABELS.reflect_sql },
  { key: 'generate_answer', label: RUN_STEP_LABELS.generate_answer },
]

const CROSS_DOMAIN_STEPS: RunStepDefinition[] = [
  { key: 'route_intent', label: RUN_STEP_LABELS.route_intent },
  { key: 'cross_domain_compose', label: RUN_STEP_LABELS.cross_domain_compose },
  { key: 'skill_dispatch', label: RUN_STEP_LABELS.skill_dispatch },
  { key: 'cross_domain_merge', label: RUN_STEP_LABELS.cross_domain_merge },
  { key: 'generate_answer', label: RUN_STEP_LABELS.generate_answer },
]

const LEGACY_STEP_ALIASES: Record<string, string> = {
  route: 'route_intent',
  workflow: 'skill_dispatch',
  answer: 'generate_answer',
}

function isKnownStep(step: string): boolean {
  return Boolean(RUN_STEP_LABELS[step])
}

function hasCrossDomainRoute(activeRun: RunRow): boolean {
  return activeRun.route === 'cross_domain' || activeRun.current_step === 'cross_domain_compose' || activeRun.current_step === 'cross_domain_merge'
}

function getOrderedRunSteps(activeRun: RunRow): RunStepDefinition[] {
  if (hasCrossDomainRoute(activeRun)) return CROSS_DOMAIN_STEPS
  return DEFAULT_RUN_STEPS
}

function normalizeRunStep(currentStep: string | null | undefined): string {
  if (!currentStep) return ''
  if (LEGACY_STEP_ALIASES[currentStep]) return LEGACY_STEP_ALIASES[currentStep]
  if (currentStep === 'queued') return 'queued'
  if (currentStep === 'completed') return 'completed'
  if (isKnownStep(currentStep)) return currentStep
  if (SKILL_STEP_KEYS.includes(currentStep as (typeof SKILL_STEP_KEYS)[number])) return 'skill_dispatch'
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
  const ordered = getOrderedRunSteps(activeRun)
  const normalizedStep = normalizeRunStep(activeRun.current_step)
  const activeIndex = ordered.findIndex((step) => step.key === normalizedStep)

  if (activeRun.status === 'completed' || normalizedStep === 'completed') {
    return ordered.map((step) => ({
      key: step.key,
      label: step.label,
      state: 'completed' as RunStepState,
    }))
  }

  return ordered.map((step, index) => ({
    key: step.key,
    label: step.label,
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

export function getActiveQueryState(activeThread: ThreadDetail | null): QueryStateView | null {
  if (!activeThread?.messages?.length) return null
  const messages = [...activeThread.messages]
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    const metadata = message.metadata || {}
    const resolved = metadata.resolved_request
    if (!resolved || typeof resolved !== 'object') continue
    const record = resolved as Record<string, unknown>
    const queryState = (record.query_state || {}) as Record<string, unknown>
    const queryOp = (record.query_op || {}) as Record<string, unknown>
    return {
      mode: String(record.mode || ''),
      confidence: typeof record.confidence === 'number' ? record.confidence : null,
      reason: String(record.reason || ''),
      operationType: String(queryOp.type || ''),
      operationFamily: String(queryOp.family || ''),
      operationSummary: String(queryOp.summary || ''),
      domain: String(queryState.domain || ''),
      domains: Array.isArray(queryState.domains) ? queryState.domains.map((item) => String(item)) : [],
      metric: String(queryState.metric || ''),
      intent: String(queryState.intent || ''),
      queryText: String(queryState.query_text || record.resolved_question || ''),
      dimensions: Array.isArray(queryState.dimensions) ? queryState.dimensions.map((item) => String(item)) : [],
      filters: queryState.filters && typeof queryState.filters === 'object' ? (queryState.filters as Record<string, unknown>) : {},
      presentation: queryState.presentation && typeof queryState.presentation === 'object' ? (queryState.presentation as Record<string, unknown>) : {},
    }
  }
  return null
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
