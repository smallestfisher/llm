# BOE Data Copilot

面向制造业数据问答场景的 Web 应用。

当前主运行架构已经稳定在：

`FastAPI Web + Local Auth DB + Router + Skills + Cross-domain Composer + Orchestrator`

前端是正常 Web 应用，后端已经完全切换到新的分层编排架构。

## 当前能力

- Web 注册、登录、登出
- 首个注册用户自动成为管理员
- 本地用户、角色、禁用/启用、密码修改、管理员重置密码
- 聊天线程、消息历史、本地审计日志
- 单域问答
- 跨域问答
- 基于真实表结构的 5-skill 分域
- SQL 执行前硬化与 lint

## 当前 5-Skill

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
  由 composer 拆成多个 skill 子任务后汇总
- `general`
  低置信度或兜底问题使用

## 数据库说明

系统依赖两套数据库。

1. 业务数据库
   由 `DB_URI` 指定。
   用于执行业务查询 SQL。

2. 本地应用数据库
   由 `LOCAL_DB_URI` 指定。
   默认可用 SQLite。
   用于保存：
   - 用户
   - 角色
   - 账号状态
   - 聊天线程
   - 聊天消息
   - 审计日志

## 当前业务表

当前运行时以 [core/config/tables.json](/home/y/llm/llm/core/config/tables.json) 为准，共 11 张表：

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

## 核心运行链路

1. Web 请求进入 [app.py](/home/y/llm/llm/app.py)
2. [core/router/intent_router.py](/home/y/llm/llm/core/router/intent_router.py) 判断路由
3. [core/router/filter_extractor.py](/home/y/llm/llm/core/router/filter_extractor.py) 提取共享过滤条件
4. [core/workflow/orchestrator.py](/home/y/llm/llm/core/workflow/orchestrator.py) 调度 skill 或跨域编排
5. skill 通过 [core/skills/base.py](/home/y/llm/llm/core/skills/base.py) 统一执行：
   - guard
   - filter refine
   - schema select
   - SQL generate
   - SQL harden / lint
   - execute
   - reflect
   - answer
6. 跨域问题由 [core/composer/cross_domain.py](/home/y/llm/llm/core/composer/cross_domain.py) 拆子任务并汇总
7. 最终答案写回聊天历史和审计日志

## SQL 保护机制

当前运行时已包含一层执行前保护，位于 [core/runtime/skill_runtime.py](/home/y/llm/llm/core/runtime/skill_runtime.py)。

会自动处理或拦截：

- `CURRENT_MONTH` / `PREVIOUS_MONTH` 这类伪占位
- `MONTH3` -> `LAST_REQUIREMENT` 这类横表伪字段
- 单表 `SELECT *`
- 未由用户指定的库存固定阈值
- `your_factory_code` 这类占位值
- `FACTORY001` / `PRODUCT123` 这类明显伪造过滤值
- `Cell No` / `Array No` / `CF No` 这类带空格列名的反引号问题

## 启动

建议先准备 Python 虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

启动服务：

```bash
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

默认访问：

- `http://127.0.0.1:8000/login`
- `http://127.0.0.1:8000/register`

## 环境变量

建议在项目根目录放 `.env`。

示例：

```env
DB_URI=mysql+pymysql://root:password@127.0.0.1:3306/boe_planner_db
LOCAL_DB_URI=sqlite:///./app_local.db

OPENAI_BASE_URL=http://127.0.0.1:8001/v1
OPENAI_API_KEY=your-api-key
LLM_MODEL=Qwen/Qwen3-14B
LLM_TEMPERATURE=0

SESSION_SECRET=change-this-session-secret
DEBUG_TRACE=0
MAX_TABLE_ROWS=200
SAMPLE_LIMIT=5000
AUTO_TRUNCATE_ROWS=50000
```

## 注册与权限

- 不再自动内置默认管理员
- 首个通过 `/register` 注册成功的账号自动获得 `admin,user`
- 后续注册账号默认获得 `user`
- 管理员可在 Web 后台或 CLI 管理用户

## 主要页面

- `/login`
- `/register`
- `/threads/new`
- `/threads/{public_id}`
- `/profile/password`
- `/admin/users`
- `/admin/audit`

## CLI

[manage_users.py](/home/y/llm/llm/manage_users.py) 仍保留，适合本地运维或应急管理。

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

说明：

- 该脚本面向当前 11 张业务表
- 主要用于本地验证，不是生产建表脚本

## 测试

静态测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall core tests
```

Live regression：

```bash
PYTHONPATH=. python3 tests/eval_runner.py
```

说明：

- `eval_runner.py` 依赖 `.env` 中可用的 LLM 和业务数据库
- 当前回归样例位于 [tests/goldens.json](/home/y/llm/llm/tests/goldens.json)

## 文档

- [PROJECT_OVERVIEW.md](/home/y/llm/llm/PROJECT_OVERVIEW.md)
  当前架构说明
- [FIVE_SKILL_MAPPING.md](/home/y/llm/llm/FIVE_SKILL_MAPPING.md)
  当前 11 张表到 5-skill 的映射
- [PRODUCTION_TUNING_FLOW.md](/home/y/llm/llm/PRODUCTION_TUNING_FLOW.md)
  生产库字段精调流程
- [PRODUCTION_TUNING_TEMPLATE.md](/home/y/llm/llm/PRODUCTION_TUNING_TEMPLATE.md)
  生产库字段精调模板

## 当前结论

仓库当前只保留新架构主链路，不再保留旧兼容运行入口。
