# BOE Data Copilot 架构说明

## 1. 当前主架构

当前分支已切到前后端分离形态：

- 后端入口：`backend/app/main.py`
- 前端入口：`frontend/src/main.tsx`
- 业务能力主实现：`backend/app`

运行主链路：

`前端 SPA -> 后端 API -> 后端 services / run 生命周期 -> 后端 workflow / semantic / execution -> 数据库 / 回答`

## 2. 分层结构

### 前端层

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
- 运行状态展示
- 重新生成 / 停止运行
- SQL 详情与表格结果
- 个人设置、管理员页、审计页

### 后端 API 层

- `backend/app/main.py`
  FastAPI 应用入口
- `backend/app/api/routes.py`
  HTTP 路由
- `backend/app/schemas/*`
  请求/响应契约

职责：

- 认证
- 线程 / 消息 / 运行 API
- 管理员与审计 API
- 生命周期驱动的运行状态返回

### 应用服务层

- `backend/app/services/chat_execution_service.py`
- `backend/app/services/run_service.py`
- `backend/app/services/thread_service.py`
- `backend/app/services/thread_query_service.py`
- `backend/app/services/auth_service.py`

职责：

- 启动 initial / regenerate 运行
- 后台执行工作流并推进 `route -> workflow -> answer`
- 持久化 thread / turn / run / message 状态
- 查询线程详情、用户列表与审计列表

### 领域 / 持久化层

- `backend/app/models/*`
- `backend/app/repositories/*`
- `backend/app/db.py`

职责：

- `Thread / Turn / Run / Message / AuditLog` 建模
- 数据库 session 与持久化
- 后端本地状态存储

### 语义层

- `backend/app/workflow/router.py`
- `backend/app/semantic/filters.py`
- `backend/app/semantic/heuristics.py`
- `backend/app/semantic/domains.py`

职责：

- 领域路由
- 跨域判定
- 共享过滤器抽取
- 相对时间口径抽取
- 目标表推断

当前主要路由结果：

- `production`
- `planning`
- `inventory`
- `demand`
- `sales`
- `cross_domain`
- `legacy`

说明：`legacy` 是 router 的低置信度或非结构化兜底结果，进入 orchestrator 后会统一转成 `general` 技能执行。

### 编排层

- `backend/app/workflow/orchestrator.py`

职责：

- 主调度入口
- 单域 / 跨域执行编排
- `legacy -> general` 兜底映射
- 技能结果回传与最终答案汇总

### 技能层

- `backend/app/skills/base.py`
- `backend/app/skills/production.py`
- `backend/app/skills/planning.py`
- `backend/app/skills/inventory.py`
- `backend/app/skills/demand.py`
- `backend/app/skills/sales.py`
- `backend/app/skills/generic.py`
- `backend/app/execution/prompts.py`

职责：

- 业务域边界约束
- guard
- schema 选择
- text2sql prompt
- SQL 反思修复
- answer prompt

### 跨域组合层

- `backend/app/workflow/composer.py`

职责：

- 拆解跨域问题
- 生成域内子任务问题
- 汇总多域执行结果

### 运行 / 执行层

- `backend/app/execution/llm_client.py`
- `backend/app/execution/sql_guard.py`
- `backend/app/execution/sql_executor.py`
- `backend/app/presentation/answer_builder.py`
- `backend/app/workflow/state.py`

职责：

- LLM 调用
- SQL 清洗
- SQL 硬化
- SQL lint
- SQL 执行
- 回答生成
- 工作流状态对象定义

### 表结构 / 配置层

- `backend/app/config/tables.json`
- `backend/app/config/intents.json`
- `backend/app/config/heuristics.json`
- `backend/app/config/lexicon.json`

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

跨域问题不会直接交给一个大技能硬做，而是：

1. router 判断是 `cross_domain`
2. composer 拆成多个域内子任务
3. 每个技能只回答本域事实
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
- `backend/app` 已经承接完整业务主链路。
- `manage_users.py` 走后端模型与本地状态库，不再依赖旧 `core` 运维链路。
