# 架构重构说明

当前分支已经从旧的单体 Web 壳层切换为前后端分离架构。

## 当前运行形态

- **后端**：`backend/app/main.py` 提供的 FastAPI API 服务
- **前端**：`frontend/src/main.tsx` 启动的 SPA
- **业务层**：`backend/app` 下的 `workflow`、`skills`、`semantic`、`execution`、`config` 模块

根目录旧的 `templates/`、`static/` 页面壳层已经不再是当前分支的主运行架构。

## 为什么要重构

旧版应用虽然积累了不少产品能力，但执行生命周期、消息状态、界面状态和线程历史之间耦合过重。重构的目标是把这些职责拆开，使得：

- 后端可以显式建模 `Run`
- 前端可以展示真实的运行进度
- assistant 消息成为运行结果，而不是运行本身
- 管理与审计能力继续作为正式产品能力保留

## 目标架构

### 后端领域模型

当前重构版后端把以下对象视为一等持久化对象：

- `Thread`
- `Turn`
- `Run`
- `Message`
- `AuditLog`

### 前端状态模型

SPA 通过后端返回的线程详情派生界面状态，核心包括：

- 当前线程
- 当前活动运行
- 运行步骤
- 最新 assistant 消息
- 管理页 / 个人页状态

## 设计原则

1. `Run` 是一等对象。
   - stop = 取消运行
   - regenerate = 基于既有 turn 新建运行
   - progress = 可查询的运行状态
2. assistant 消息是运行产物，而不是运行本身。
3. `Thread`、`Turn`、`Run`、`Message` 应当可以被独立查询。
4. 管理与审计能力仍然属于产品本体，不作为外挂功能存在。
5. `backend/app/config/tables.json` 是表结构的唯一事实来源。
6. 当前后端不再依赖平行存在的旧 `core` 业务树。

## 当前架构地图

### 后端

- `backend/app/main.py`
  - FastAPI 入口
- `backend/app/api/routes.py`
  - 认证、线程、运行、管理员、审计接口
- `backend/app/services/*`
  - 运行生命周期、线程查询、认证与管理员编排
- `backend/app/services/followup/*`
  - 追问三态分类与处理器（改写 / 同域补查 / 新问题）
- `backend/app/models/*`
  - 重构版持久化模型
- `backend/app/workflow/*`
  - 编排、路由、历史整理
- `backend/app/semantic/*`
  - 过滤器提取、启发式、领域映射
- `backend/app/execution/*`
  - LLM、SQL 硬化 / lint、SQL 执行
- `backend/app/config/*`
  - 表结构与路由配置

### 前端

- `frontend/src/main.tsx`
  - SPA 挂载入口
- `frontend/src/App.tsx`
  - 顶层应用容器
- `frontend/src/api.ts`
  - 后端 API 调用封装
- `frontend/src/components.tsx`
  - 线程 / 运行 / 管理 / 个人页 / 消息界面组件
- `frontend/src/view-models.ts`
  - 运行与消息的派生状态

## 当前重构进度

已完成：

- 前后端分离结构落地
- 重构版后端入口与 API 路由
- `Thread / Turn / Run / Message / AuditLog` 持久化模型
- 认证、管理员、审计 API
- `pending / running / cancelling / completed / failed / cancelled` 运行生命周期
- 与 `Run` 对齐的发送 / 重新生成 / 取消 API
- SPA 登录、注册、聊天、个人页、管理员页、审计页
- 基于轮询的运行进度展示
- SPA 中的 SQL 详情与结果表格展示
- 后端原生的 `workflow / semantic / execution / config` 技术栈
- 旧模板 / 静态页面壳层退出主架构
- 旧 `core` 业务树退出主运行链路
- 追问三态分流（开关控制，默认关闭）
  - `rewrite_only`：仅改写上一轮回答，不走 SQL
  - `same_scope_query`：继承上一轮 route/filter，补字段或补维度后重跑 SQL
  - `new_query`：按原流程走完整路由与工作流
- `regenerate` 缓存绕过开关（默认关闭）
- 历史窗口与摘要开关（默认关闭）

仍在演进：

- 继续瘦身前端顶层容器
- 除轮询外更丰富的进度反馈机制
- 结合真实生产数据进一步优化 prompt 与路由
- 追问分类从规则向“规则 + 轻量模型置信度”演进

## 追问分流架构（新增）

目标：在不破坏主流程稳定性的前提下，降低“改写类追问”token 成本，并让“补字段追问”走正确的数据重查路径。

### 模块边界

- `backend/app/services/followup/types.py`
  - 定义三态协议：`FollowupMode = REWRITE_ONLY / SAME_SCOPE_QUERY / NEW_QUERY`
- `backend/app/services/followup/classifier.py`
  - 追问分类器，输入 `question + previous_answer + previous_route_snapshot`
- `backend/app/services/followup/handlers.py`
  - 各模式处理器
  - `rewrite_only` 只调用答案模型，不触发 SQL
  - `same_scope_query` 生成 `RouteDecision` 覆用上一轮路由上下文
- `backend/app/services/chat_execution_service.py`
  - 仅负责分发与编排，不承载分类细节

### 执行顺序

1. 创建 `Run` 后，先获取上一轮 assistant 上下文（内容 + route metadata）。
2. 若开启 `FOLLOWUP_CLASSIFIER_ENABLED=1`，执行三态分类。
3. 分类结果分发：
   - `REWRITE_ONLY` -> 直接产出回答并结束 run
   - `SAME_SCOPE_QUERY` -> 继承上一轮 route/filter，继续执行 workflow
   - `NEW_QUERY` -> 原始完整流程
4. 任何异常或判定不稳，回退 `NEW_QUERY`（安全路径）。

### 兼容与回滚

- 默认开关关闭：`FOLLOWUP_CLASSIFIER_ENABLED=0`，行为与历史版本一致。
- 保留旧开关别名兼容：`FOLLOWUP_LIGHT_ROUTE_ENABLED`。
- 回滚方式：仅关闭开关，无需回退代码。

## 运行链路（更新版）

1. 前端把问题发给重构版 API
2. 后端创建 `Turn` 与 `Run`
3. （可选）追问三态分流
4. 后台任务推动运行经过 `route / workflow / answer` 阶段
5. 前端在运行激活期间持续轮询线程详情
6. 只有运行成功完成后才会写入最终 assistant 消息
7. cancel / regenerate 都围绕 `Run` 工作，而不是围绕页面壳层工作

## 本地开发形态

### 启动后端

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

`frontend` 中的 Vite 开发服务器会把 `/api` 代理到 `8000` 端口的后端。

## 验证要求

一次重构改动至少应验证：

- 后端导入与启动正常
- `/api/health` 可访问
- 前端可以成功构建
- send / regenerate / cancel 能走到终态
- 管理数据仍然可用，包括 `last_login_at`
- `FOLLOWUP_CLASSIFIER_ENABLED=0` 时行为与旧流程一致
- `FOLLOWUP_CLASSIFIER_ENABLED=1` 时三态分流行为正确：
  - 改写追问不走 SQL
  - 补字段追问走同域重查
  - 模糊追问回退完整流程

## 当前保留下来的关键资产

- `backend/app/config/tables.json`
  - 当前后端使用的表结构唯一事实来源
