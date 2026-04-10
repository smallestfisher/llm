# BOE Data Copilot (V3.0 架构文档)

## 1. 当前主架构

当前主系统已经完成从单体 LangGraph 流程到 `Router + Skills + Composer + Orchestrator` 的迁移。

核心处理链路：

1. `app.py` 接收请求，读取本地聊天历史并启动流式响应。
2. `core/workflow/orchestrator.py` 作为唯一主编排入口。
3. `core/router/intent_router.py` 判定问题是 `production`、`inventory`、`cross_domain` 还是 `general`。
4. `core/router/filter_extractor.py` 提取共享过滤器，例如 `recent_days`、`latest`、日期范围、月份范围。
5. 单域问题交给对应 skill 执行。
6. 跨域问题交给 `core/composer/cross_domain.py` 拆成多个 skill plan，再顺序执行并汇总。
7. 结果通过统一状态结构回传给前端，前端显示执行状态、答案和表格结果。

## 2. 模块分层

### Web 层
- `app.py`
  负责会话、登录注册、用户管理、审计日志、聊天接口和流式输出。

### Orchestrator 层
- `core/workflow/orchestrator.py`
  负责主链路调度。
  它只决定谁来执行，不再承担领域 SQL 细节。

### Router 层
- `core/router/intent_router.py`
  负责领域路由和跨域判定。
- `core/router/filter_extractor.py`
  负责抽取共享过滤器。

### Skills 层
- `core/skills/base.py`
  skill 通用执行骨架。
- `core/skills/production/skill.py`
  生产与计划域 skill。
- `core/skills/inventory/skill.py`
  库存与供应保障域 skill。
- `core/skills/generic/skill.py`
  通用兜底 skill。
- `core/skills/prompting.py`
  skill 独立 prompt 生成。

### Composer 层
- `core/composer/cross_domain.py`
  负责跨域拆分、顺序执行结果汇总和统一回答。

### Runtime 层
- `core/runtime/skill_runtime.py`
  提供 LLM 调用、SQL 清洗、SQL 执行、回答生成等公共运行时。
- `core/runtime/state.py`
  定义 `RouteDecision`、`SkillPlan`、`SkillResult` 等跨层状态对象。

### Persistence 层
- `core/database.py`
  业务数据库访问。
- `core/auth_db.py`
  本地 SQLite 用户、角色、聊天、审计持久化。

## 3. 旧架构位置

- `core/graph.py` 仍保留在仓库中。
- 它现在是历史兼容实现，不再参与 Web 应用主运行路径。
- 保留它的原因是避免外部脚本、旧实验或临时对比脚本立即失效。

如果后续确认外部没有引用，可以再移到 `legacy/` 或直接删除。

## 4. 新旧架构差异

### 旧架构
`parse_query -> guard -> refine -> schema -> write_sql -> execute -> reflect -> answer`

问题：
- 所有问题都被塞进同一个大流程
- 语义解析节点过重
- 跨域问题只能硬扛在一个统一流程里
- 扩展新业务域时耦合度高

### 新架构
`router -> one or more skills -> composer -> final response`

收益：
- 每个业务域可以独立收敛 prompt 和 SQL 规则
- 跨域编排可以渐进增强
- 低置信度问题可落到 generic skill，而不是回退旧大图
- 更适合后续扩 skill、扩 domain、扩组合策略

## 5. 维护策略

### 新增业务域
1. 新建一个 skill 文件。
2. 配置 `domain_label`、`guard_scope`、`focus_areas`、`sql_rules`、`answer_rules`。
3. 在 router 中补充领域关键词和路由规则。
4. 必要时在 composer 中加入该域的跨域组合逻辑。
5. 增加单测和回归样例。

### 表结构变更
优先顺序：
1. 改真实数据库
2. 改 `core/config/tables.json`
3. 再改 skill 的规则和 prompt
4. 最后补路由词典和回归测试

不要反过来先靠 prompt 猜字段。

### 精度优化
当前数据库字段不是最终生产版时，优先保证：
- 技能边界清晰
- 运行链路稳定
- 共享过滤器正确传播
- 跨域结果可汇总

等正式生产库字段稳定后，再按 skill 分域调优 SQL 精度。

## 6. 当前已完成事项

- FastAPI Web 应用替换旧 Chainlit 交互
- 本地注册、登录、角色、密码修改、禁用账号、审计日志
- 聊天线程与消息持久化
- 新主架构接管运行入口
- 单域 skill 执行
- 跨域顺序编排与结果汇总
- 基础路由、过滤器、composer 单测

## 7. 剩余可选优化

- 将跨域从顺序执行升级为并行执行
- 为 skill 增加更严格的 schema selector
- 增加更细的领域答案汇总模板
- 补用户系统和聊天接口集成测试
