# 前端重构说明

该目录包含 BOE Data Copilot 重构版的 SPA 前端。

## 在系统中的角色

前端替代了旧的服务端模板 / 静态页面壳层，负责：

- 认证流程
- 线程导航
- 聊天工作区
- 运行进度展示
- 重新生成 / 取消交互
- SQL 详情展示
- 个人页
- 管理员用户页
- 审计页

## 当前目录结构

- `src/main.tsx`：SPA 挂载入口
- `src/App.tsx`：顶层容器
- `src/api.ts`：后端 API 调用辅助
- `src/components.tsx`：共享 UI 组件
- `src/view-models.ts`：派生状态辅助逻辑
- `src/styles.css`：重构版界面样式

## UI 状态模型

前端的大部分行为都基于后端返回的线程详情派生，主要包括：

- 当前线程
- 当前活动运行
- 运行步骤
- 最新 assistant 消息
- 管理页 / 个人页状态

这样界面就能反映真实的运行生命周期，而不是假设一次同步阻塞的请求-响应过程。

## 当前运行行为

发送或重新生成后：

1. SPA 调用重构版 API
2. 后端返回运行启动信息
3. SPA 刷新线程详情
4. 只要运行仍在进行，就持续轮询
5. UI 展示 `pending / running / cancelling / completed / failed / cancelled`

运行面板和消息操作现在完全由后端 `Run` 状态驱动，而不是依赖旧页面壳层中的 DOM 事件拼装。

## 本地运行

```bash
cd frontend
npm install
npm run dev
```

## 构建

```bash
npm run build
```

## 开发代理

`vite.config.ts` 会把 `/api` 代理到 `http://127.0.0.1:8000`，因此本地开发时需要重构版后端运行在该端口。

## 当前状态

当前前端已经支持登录 / 注册、线程、聊天、重新生成、停止运行、SQL 详情、个人页、管理员页和审计页。结构上仍在继续收敛，后续会进一步瘦身 `App.tsx`，但它已经是当前分支的正式 UI 架构。
