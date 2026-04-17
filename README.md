# BOE Data Copilot

面向制造业数据问答场景的重构版 Web 应用。

当前分支以分离式架构运行为主：

- 后端：`backend/app/main.py`
- 前端：`frontend/` SPA
- 业务能力：由 `backend/app` 下的 `workflow / skills / semantic / execution / config` 模块承载

## 当前能力

- 注册、登录、个人密码修改
- 首个注册用户自动成为管理员
- 用户启用/禁用、角色调整、管理员重置密码
- 线程、消息、运行状态、重新生成、停止运行
- 审计日志
- 5 个技能的单域问答与跨域问答
- SQL 执行前硬化与 lint

## 当前 5 个技能

1. `production`
   生产执行，只看实际投入、产出、报废、不良
2. `planning`
   日排产、周滚、审批版月计划
3. `inventory`
   日库存、OMS、库龄、客户仓、供应保障
4. `demand`
   V版 forecast、P版 commit、需求缺口
5. `sales`
   销量、财务业绩

另有：

- `cross_domain`
  由 composer 拆成多个技能子任务后汇总
- `general`
  低置信度、非结构化或兜底问题使用

说明：router 内部仍可能返回 `legacy`，但在 orchestrator 中会统一映射到 `general` 技能执行，并不是一个独立业务技能。

## 当前业务表

当前运行时以 [backend/app/config/tables.json](/home/y/llm/llm/backend/app/config/tables.json) 为准，共 11 张表：

- `v_demand`
- `p_demand`
- `daily_inventory`
- `daily_PLAN`
- `monthly_plan_approved`
- `oms_inventory`
- `product_attributes`
- `product_mapping`
- `production_actuals`
- `sales_financial_perf`
- `weekly_rolling_plan`

## 架构说明

当前主链路：

1. 前端 SPA 请求进入 `/api`
2. `backend/app/api/routes.py` 处理认证、线程、运行、管理员接口
3. `backend/app/services/*` 维护 `Thread / Turn / Run / Message / AuditLog`
4. `backend/app/workflow/executor.py` 驱动 `backend/app/workflow/orchestrator.py`
5. `backend/app/workflow/*`、`backend/app/semantic/*`、`backend/app/execution/*`、`backend/app/config/*` 负责领域路由、跨域编排、SQL 运行时以及表结构 / 路由配置；其中表结构唯一事实来源为 `backend/app/config/tables.json`

说明：

- 根目录旧的单体页面壳层已不再是当前分支主运行入口
- 旧业务实现已退场，当前以 `backend/app` 为唯一业务实现

## 环境准备

建议先准备 Python 虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

前端依赖：

```bash
cd frontend
npm install
```

## 启动

### 启动后端

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 启动前端

```bash
cd frontend
npm run dev
```

默认开发访问：

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/api/health`

`frontend/vite.config.ts` 已把 `/api` 代理到 `127.0.0.1:8000`。

## 环境变量

建议在项目根目录放 `.env`。

示例：

```env
DB_URI=mysql+pymysql://root:password@127.0.0.1:3306/boe_planner_db
BACKEND_DB_URI=sqlite:////absolute/path/to/backend/app_rewrite.db

OPENAI_BASE_URL=http://127.0.0.1:8001/v1
OPENAI_API_KEY=your-api-key
LLM_MODEL=Qwen/Qwen3-14B
LLM_MODEL_ROUTER=Qwen/Qwen3-14B
LLM_MODEL_GUARD=Qwen/Qwen3-14B
LLM_MODEL_SQL=Qwen/Qwen3-14B
LLM_MODEL_REFLECT=Qwen/Qwen3-14B
LLM_MODEL_ANSWER=Qwen/Qwen3-14B
LLM_TEMPERATURE=0
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=2

SESSION_SECRET=change-this-session-secret
DEBUG_TRACE=0
MAX_TABLE_ROWS=200
SAMPLE_LIMIT=5000
AUTO_TRUNCATE_ROWS=50000
SQL_ENABLE_PRECOUNT=0
SQL_CANDIDATE_COUNT=2
SQL_CANDIDATE_EXPAND_SCORE=90
SQL_CANDIDATE_PROBE_LIMIT=1
CROSS_DOMAIN_MAX_PARALLEL=2
QUERY_CACHE_ENABLED=1
QUERY_CACHE_MAX_SIZE=2000
QUERY_CACHE_TTL_SHORT=180
QUERY_CACHE_TTL_LONG=600
QUERY_CACHE_SCHEMA_VERSION=v1
```

### 26B 混合模型推荐参数

如果 SQL/Reflect 使用 26B，建议先从以下配置起步：

```env
LLM_MODEL_ROUTER=<7b_or_14b>
LLM_MODEL_GUARD=<7b_or_14b>
LLM_MODEL_SQL=<26b>
LLM_MODEL_REFLECT=<26b>
LLM_MODEL_ANSWER=<14b_or_26b>

SQL_CANDIDATE_COUNT=2
SQL_CANDIDATE_EXPAND_SCORE=90
CROSS_DOMAIN_MAX_PARALLEL=1
QUERY_CACHE_ENABLED=1
```

说明：

- SQL 候选采用“按需扩展”，首条候选评分高时不会继续扩展，优先省 token。
- 跨域并发可通过 `CROSS_DOMAIN_MAX_PARALLEL` 控制；单卡 26B 建议设为 `1`。
- 缓存 key 包含标准化问题、结构化过滤、路由和 schema 版本，可通过 `QUERY_CACHE_SCHEMA_VERSION` 做失效切换。

## 管理与运维

[manage_users.py](/home/y/llm/llm/manage_users.py) 目前仍保留，适合本地运维或应急管理。

```bash
python3 manage_users.py list
python3 manage_users.py add alice strong-password --roles user
python3 manage_users.py roles alice admin,user
python3 manage_users.py disable alice
python3 manage_users.py enable alice
python3 manage_users.py reset-password alice new-password
```

## 初始化样例业务表

如果需要一套样例业务表，可以运行：

```bash
python3 init_sql.py
```

## 测试与验证

后端静态检查：

```bash
python3 -m compileall backend/app
```

前端构建：

```bash
npm run build --prefix frontend
```

核心逻辑测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

在线回归：

```bash
PYTHONPATH=. python3 tests/eval_runner.py
```

## 文档

- [ARCHITECTURE_REWRITE.md](/home/y/llm/llm/ARCHITECTURE_REWRITE.md)
  当前重构目标与设计原则
- [PROJECT_OVERVIEW.md](/home/y/llm/llm/PROJECT_OVERVIEW.md)
  当前项目结构说明
- [FIVE_SKILL_MAPPING.md](/home/y/llm/llm/FIVE_SKILL_MAPPING.md)
  当前 11 张表到 5 个技能的映射
- [BATCH2_BATCH3_OPTIMIZATION_PLAN.md](/home/y/llm/llm/BATCH2_BATCH3_OPTIMIZATION_PLAN.md)
  Batch 2/3 效率与准确度优化计划
- [PRODUCTION_TUNING_FLOW.md](/home/y/llm/llm/PRODUCTION_TUNING_FLOW.md)
  生产库字段精调流程
- [PRODUCTION_TUNING_TEMPLATE.md](/home/y/llm/llm/PRODUCTION_TUNING_TEMPLATE.md)
  生产库字段精调模板
