# 后端重构说明

该目录是 BOE Data Copilot 的 FastAPI 后端实现。

## 在系统中的角色

后端是当前应用唯一的服务端入口，负责：

- 认证接口
- 线程 / 轮次 / 运行 / 消息接口
- 运行取消与重新生成
- 管理员与审计接口
- 持久化后端状态
- 在 `backend/app` 内执行路由、编排、SQL 硬化、SQL 执行和答案生成

## 当前目录结构

- `app/main.py`：FastAPI 入口
- `app/api`：HTTP 路由
- `app/models`：ORM 模型
- `app/repositories`：持久化辅助层
- `app/schemas`：请求 / 响应契约
- `app/services`：应用服务层
- `app/workflow`：路由、编排、历史整理
- `app/semantic`：启发式、过滤器、领域映射
- `app/execution`：LLM、SQL guard、SQL executor
- `app/config`：表结构与路由配置
- `app/presentation`：最终答案载荷整理

## 运行时模型

后端把下面这些对象当作一等对象处理：

- `Thread`
- `Turn`
- `Run`
- `Message`
- `AuditLog`

发送消息或重新生成回复时，系统会先启动一个 `Run`，而不是同步阻塞等待最终答案。

## 当前运行生命周期

一个 `Run` 可以处于以下状态：

- `pending`
- `running`
- `cancelling`
- `completed`
- `failed`
- `cancelled`

当前暴露给前端的粗粒度运行阶段有：

- `route`
- `workflow`
- `answer`

其中 `workflow` 阶段内部还可能继续推进以下节点：

- 路由结果输出
- 跨域拆解 / 汇总
- `check_guard`
- `refine_filters`
- `get_schema`
- `write_sql`
- `execute_sql`
- `reflect_sql`
- 最终答案生成

## 本地运行

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 环境变量

后端使用 `BACKEND_DB_URI` 作为本地状态存储连接串。

示例：

```env
BACKEND_DB_URI=sqlite:////absolute/path/to/backend/app_rewrite.db
```

如果未设置，后端会退回到 `backend/` 目录下的重构版本地 SQLite 文件。

## 验证建议

后端改动后建议至少执行：

```bash
python3 -m compileall backend/app
curl http://127.0.0.1:8000/api/health
```

行为验证建议覆盖：

- 注册 / 登录
- 创建线程
- 发送消息
- 重新生成回复
- 取消运行中的 `Run`
- 校验管理员用户列表与审计接口

## 当前状态

当前后端已经可以独立支撑重构版 UI 的完整链路，不再依赖平行存在的旧业务树。
