# BOE Data Copilot 架构说明

## 1. 当前主架构

当前分支已切到前后端分离形态：

- 后端入口：`backend/app/main.py`
- 前端入口：`frontend/src/main.tsx`
- 业务能力复用层：`core/`

运行主链路：

`frontend SPA -> backend API -> backend services/run lifecycle -> core router/workflow/runtime -> db/answer`

## 2. 分层结构

### Frontend 层

- `frontend/src/main.tsx`
  SPA 挂载入口
- `frontend/src/App.tsx`
  当前主容器
- `frontend/src/components.tsx`
  共享界面组件
- `frontend/src/api.ts`
  API 调用封装
- `frontend/src/view-models.ts`
  运行态导出逻辑

职责：

- 登录注册
- 线程列表与聊天工作区
- Run 状态展示
- 重新生成 / 停止运行
- SQL 详情与表格结果
- 个人设置、管理员页、审计页

### Backend API 层

- `backend/app/main.py`
  FastAPI 应用入口
- `backend/app/api/routes.py`
  HTTP 路由
- `backend/app/schemas/*`
  请求/响应契约

职责：

- 认证
- 线程 / 消息 / run API
- 管理员与审计 API
- 生命周期驱动的运行状态返回

### Application Service 层

- `backend/app/services/chat_execution_service.py`
- `backend/app/services/run_service.py`
- `backend/app/services/thread_service.py`
- `backend/app/services/thread_query_service.py`
- `backend/app/services/auth_service.py`

职责：

- 启动 run
- 后台执行 workflow
- 持久化 run/turn/message 状态
- 查询线程详情与管理数据

### Domain / Persistence 层

- `backend/app/models/*`
- `backend/app/repositories/*`
- `backend/app/db.py`

职责：

- `Thread / Turn / Run / Message / AuditLog` 建模
- 数据库 session 与持久化
- 新后端本地状态存储

### Router 层

- `core/router/intent_router.py`
- `core/router/filter_extractor.py`

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

- `core/workflow/orchestrator.py`

职责：

- 主调度入口
- 单域 / 跨域执行编排
- 状态汇总
- 技能结果回传

### Skill 层

- `core/skills/base.py`
- `core/skills/production/skill.py`
- `core/skills/planning/skill.py`
- `core/skills/inventory/skill.py`
- `core/skills/demand/skill.py`
- `core/skills/sales/skill.py`
- `core/skills/generic/skill.py`
- `core/skills/prompting.py`

职责：

- 业务域边界约束
- guard
- schema 选择
- text2sql prompt
- SQL 反思修复
- answer prompt

### Composer 层

- `core/composer/cross_domain.py`

职责：

- 拆解跨域问题
- 生成域内子任务问题
- 汇总多域执行结果

### Runtime 层

- `core/runtime/skill_runtime.py`
- `core/runtime/state.py`

职责：

- LLM 调用
- SQL 清洗
- SQL 硬化
- SQL lint
- SQL 执行
- 回答生成

### Schema / Config 层

- `core/config/tables.json`
- `core/config/intents.json`
- `core/config/heuristics.json`
- `core/config/lexicon.json`

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

1. route / filter 提取
2. schema 选择
3. SQL 生成
4. SQL 清洗
5. SQL 硬化
6. SQL lint
7. SQL 执行
8. 结果反思
9. 回答生成

## 6. 说明

- 根目录旧的 `app.py` + `templates/` + `static/` 单体页面壳层已废弃，不再作为当前主运行入口。
- `core/` 不是废弃代码；当前 rewrite backend 仍通过桥接层复用它的 router/workflow/runtime。
- `manage_users.py` 与 `core/auth_db.py` 目前仍保留为独立的本地运维链路，不应与旧页面壳层混为一谈。
