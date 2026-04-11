# BOE Data Copilot 架构说明

## 1. 当前主架构

当前主系统已完成从旧单体流程向分层编排架构的迁移。

运行主链路：

`app.py -> router -> filters -> skill or cross-domain composer -> orchestrator -> runtime -> db/answer`

当前 Web 应用主入口是 [app.py](/home/y/llm/llm/app.py)。

## 2. 分层结构

### Web 层

- [app.py](/home/y/llm/llm/app.py)
  FastAPI 应用入口
- `templates/`
  Jinja2 页面模板
- `static/`
  前端静态资源

职责：

- 登录注册
- 会话管理
- 页面渲染
- 聊天流式输出
- 用户后台
- 审计日志展示

### Local Auth / Persistence 层

- [core/auth_db.py](/home/y/llm/llm/core/auth_db.py)

职责：

- 用户
- 角色
- 本地权限
- 聊天线程
- 聊天消息
- 审计日志

本地库默认是 SQLite，通过 `LOCAL_DB_URI` 控制。

### Router 层

- [core/router/intent_router.py](/home/y/llm/llm/core/router/intent_router.py)
- [core/router/filter_extractor.py](/home/y/llm/llm/core/router/filter_extractor.py)

职责：

- 领域路由
- 跨域判定
- 共享过滤器抽取
- 相对时间口径抽取

当前主要路由结果：

- `production`
- `planning`
- `inventory`
- `demand`
- `sales`
- `cross_domain`
- `legacy` / `general`

### Orchestrator 层

- [core/workflow/orchestrator.py](/home/y/llm/llm/core/workflow/orchestrator.py)

职责：

- 主调度入口
- 单域 / 跨域执行编排
- 状态汇总
- 技能结果回传

### Skill 层

- [core/skills/base.py](/home/y/llm/llm/core/skills/base.py)
- [core/skills/production/skill.py](/home/y/llm/llm/core/skills/production/skill.py)
- [core/skills/planning/skill.py](/home/y/llm/llm/core/skills/planning/skill.py)
- [core/skills/inventory/skill.py](/home/y/llm/llm/core/skills/inventory/skill.py)
- [core/skills/demand/skill.py](/home/y/llm/llm/core/skills/demand/skill.py)
- [core/skills/sales/skill.py](/home/y/llm/llm/core/skills/sales/skill.py)
- [core/skills/generic/skill.py](/home/y/llm/llm/core/skills/generic/skill.py)
- [core/skills/prompting.py](/home/y/llm/llm/core/skills/prompting.py)

职责：

- 业务域边界约束
- guard
- schema 选择
- text2sql prompt
- SQL 反思修复
- answer prompt

### Composer 层

- [core/composer/cross_domain.py](/home/y/llm/llm/core/composer/cross_domain.py)

职责：

- 拆解跨域问题
- 生成域内子任务问题
- 汇总多域执行结果

### Runtime 层

- [core/runtime/skill_runtime.py](/home/y/llm/llm/core/runtime/skill_runtime.py)
- [core/runtime/state.py](/home/y/llm/llm/core/runtime/state.py)

职责：

- LLM 调用
- SQL 清洗
- SQL 硬化
- SQL lint
- SQL 执行
- 回答生成

### Schema / Config 层

- [core/config/tables.json](/home/y/llm/llm/core/config/tables.json)
- [core/config/intents.json](/home/y/llm/llm/core/config/intents.json)
- [core/config/heuristics.json](/home/y/llm/llm/core/config/heuristics.json)
- [core/config/lexicon.json](/home/y/llm/llm/core/config/lexicon.json)

职责：

- 表结构
- 业务词典
- 路由辅助规则
- 简单启发式

## 3. 当前 5-Skill 与主表

### `production`

职责：

- 只回答生产执行实际发生了什么

主表：

- `production_actuals`

辅助表：

- `product_attributes`
- `product_mapping`

### `planning`

职责：

- 只回答计划体系问题

主表：

- `daily_PLAN`
- `weekly_rolling_plan`
- `monthly_plan_approved`

辅助表：

- `product_attributes`
- `product_mapping`

### `inventory`

职责：

- 只回答库存与供应保障问题

主表：

- `daily_inventory`
- `oms_inventory`

辅助表：

- `product_attributes`
- `product_mapping`

### `demand`

职责：

- 只回答 V版/P版需求与承诺问题

主表：

- `v_demand`
- `p_demand`

辅助表：

- `product_attributes`
- `product_mapping`

### `sales`

职责：

- 只回答销售与财务业绩问题

主表：

- `sales_financial_perf`

辅助表：

- `product_attributes`
- `product_mapping`

## 4. 跨域模式

跨域问题不会直接交给一个大 skill 硬做，而是：

1. router 判断是 `cross_domain`
2. composer 拆成多个域内子任务
3. 每个 skill 只回答本域事实
4. orchestrator 汇总结果

当前典型组合：

- `inventory + planning`
- `demand + planning`
- `production + planning`
- `demand + inventory`
- `production + sales`
- `planning + sales`

## 5. SQL 保护链

当前 SQL 不是“生成后直接执行”，而是：

1. LLM 生成 SQL
2. `sanitize_sql`
3. `harden_sql`
4. `lint_sql`
5. 通过后才执行
6. 若 lint 或数据库报错，则走 reflect 重写

已覆盖的典型问题：

- 伪月份占位
- 横表伪字段
- `SELECT *`
- 越界表
- 缺失版本过滤
- 无意义维表 join
- 库存固定阈值
- 占位字面值
- 带空格列名未加反引号

## 6. 数据流

一次正常聊天请求的数据流：

1. 用户在 `/threads/{public_id}` 发问
2. `/api/chat/{public_id}` 写入用户消息
3. workflow 流式执行
4. 前端收到状态事件和最终答案
5. assistant 答案写回 `chat_messages`
6. 审计写入 `audit_logs`

## 7. 文档维护原则

后续如果再调生产库字段或 skill：

1. 先改真实表结构认知
2. 再改 `tables.json`
3. 再改对应 skill prompt / sql rule
4. 再改 router / heuristics
5. 最后补 `goldens` 和测试

不要反过来先靠 prompt 猜字段。
