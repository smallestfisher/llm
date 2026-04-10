# BOE Data Copilot

一个面向制造业数据问答场景的 Web 应用。

当前版本已经完成后端主链路迁移，运行架构为 `Router + Skills + Composer + Orchestrator`。前端基于 `FastAPI + Jinja2`，内置本地账号、角色控制、密码修改、禁用账号、聊天历史和审计日志。

## 功能概览

- 自然语言转 SQL 查询
- 基于 `Router + Skills` 的领域编排
- 支持单域查询与跨域组合查询
- FastAPI Web 前端
- 本地注册、登录、登出
- 角色控制：`admin` / `user`
- 首个注册账号自动成为管理员
- 管理员后台：创建用户、改角色、禁用/启用、重置密码
- 审计日志：登录、注册、查询、用户运维都会记录
- 本地聊天线程与消息持久化

## 技术栈

- Python 3.10+
- FastAPI
- Jinja2
- SQLAlchemy
- OpenAI 兼容接口
- MySQL 8.0+
- SQLite

## 系统架构

系统分为两套数据库：

1. `DB_URI`
   业务数据库，供技能执行 SQL 查询使用。

2. `LOCAL_DB_URI`
   本地应用数据库，默认是 SQLite，用于存储：
   - 用户
   - 角色
   - 账号状态
   - 聊天线程
   - 聊天消息
   - 审计日志

问答主链路：

1. 用户输入自然语言问题
2. `router` 判断问题属于 `production`、`inventory`、`cross_domain` 或 `general`
3. 对应 skill 执行守卫、过滤修正、Schema 选择、SQL 生成、SQL 执行和回答生成
4. 如果是跨域问题，`composer` 会拆成多个 skill plan 并汇总结果
5. 返回自然语言答案和表格结果
6. 查询行为写入审计日志和聊天历史

运行时核心模块：

- [app.py](/home/y/llm/llm/app.py): FastAPI Web 应用入口
- [core/workflow/orchestrator.py](/home/y/llm/llm/core/workflow/orchestrator.py): 主编排器
- [core/router/intent_router.py](/home/y/llm/llm/core/router/intent_router.py): 问题路由
- [core/router/filter_extractor.py](/home/y/llm/llm/core/router/filter_extractor.py): 共享过滤器抽取
- [core/skills/base.py](/home/y/llm/llm/core/skills/base.py): skill 基类
- [core/skills/production/skill.py](/home/y/llm/llm/core/skills/production/skill.py): 生产域技能
- [core/skills/inventory/skill.py](/home/y/llm/llm/core/skills/inventory/skill.py): 库存域技能
- [core/skills/generic/skill.py](/home/y/llm/llm/core/skills/generic/skill.py): 通用兜底技能
- [core/composer/cross_domain.py](/home/y/llm/llm/core/composer/cross_domain.py): 跨域拆分与结果汇总
- [core/runtime/skill_runtime.py](/home/y/llm/llm/core/runtime/skill_runtime.py): skill 公共运行时

兼容说明：

- [core/graph.py](/home/y/llm/llm/core/graph.py) 仍保留在仓库中，作为历史兼容实现
- 当前 Web 应用主运行路径已经不再依赖 `core.graph`

## Web 注册规则

- 系统不再自动生成默认管理员账号
- 首个通过 `/register` 注册成功的用户自动获得 `admin,user` 角色
- 后续注册用户默认获得 `user` 角色
- 管理员仍可在后台创建用户并调整角色

## 安装依赖

```bash
pip install -r requirements.txt
```

## 环境变量

建议在项目根目录创建 `.env`。

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
```

说明：

- `DB_URI`: 业务查询数据库连接串
- `LOCAL_DB_URI`: 本地应用数据库连接串，不填时默认为 `sqlite:///./app_local.db`
- `OPENAI_BASE_URL`: OpenAI 兼容接口地址
- `OPENAI_API_KEY`: 模型服务密钥
- `SESSION_SECRET`: FastAPI Session Cookie 密钥

## 初始化业务样例数据

如果你需要一套本地样例 MySQL 数据，可以运行：

```bash
python3 init_sql.py
```

注意：这个脚本会创建并重建样例业务表。

## 启动应用

```bash
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：

- `http://127.0.0.1:8000/login`
- `http://127.0.0.1:8000/register`

## 主要页面

- `/login`: 登录页
- `/register`: 注册页
- `/threads/{id}`: 聊天工作台
- `/profile/password`: 修改密码
- `/admin/users`: 用户管理
- `/admin/audit`: 审计日志

## 用户管理 CLI

项目仍保留一个本地管理脚本：

```bash
python3 manage_users.py list
python3 manage_users.py add alice yourpassword --roles user
python3 manage_users.py roles alice admin,user
python3 manage_users.py disable alice
python3 manage_users.py enable alice
python3 manage_users.py reset-password alice newpassword
```

## 目录说明

```text
.
├── app.py                  # FastAPI Web 应用入口
├── README.md
├── PROJECT_OVERVIEW.md     # 详细架构说明
├── manage_users.py         # 本地用户管理 CLI
├── init_sql.py             # 样例业务数据初始化
├── requirements.txt
├── templates/              # Jinja2 页面模板
├── static/                 # CSS / JS 静态资源
├── core/
│   ├── auth_db.py          # 本地账号/角色/审计/聊天持久化
│   ├── database.py         # 业务数据库访问
│   ├── graph.py            # 历史兼容工作流，主流程已不依赖
│   ├── workflow/
│   │   └── orchestrator.py # 主编排入口
│   ├── router/             # 路由与共享过滤器
│   ├── skills/             # 领域技能
│   ├── composer/           # 跨域汇总
│   ├── runtime/            # skill 公共运行时
│   ├── lexicon.py          # 轻量术语归一化
│   ├── heuristics.py       # 规则修正
│   └── config/             # intents / tables / heuristics 配置
└── tests/
    ├── eval_runner.py      # 新架构评测入口
    ├── goldens.json
    ├── test_intent_router.py
    ├── test_cross_domain_composer.py
    └── test_filter_extractor.py
```

## 测试与校验

语法检查：

```bash
python3 -m compileall app.py core manage_users.py
```

评测脚本：

```bash
python3 tests/eval_runner.py
```

说明：

- `eval_runner.py` 会通过新 orchestrator 执行用例
- 支持校验 `route`、`skill`、`sql_query` 中的字段命中
- 仍依赖模型服务和业务数据库可用

## 当前实现说明

- 前端已不再依赖 Chainlit
- 聊天历史由本地库保存
- 查询接口默认只支持业务数据问答，不处理闲聊和无关问题
- 主系统已经完成从单体图流程到 `router + skills + composer` 的迁移
- 当前跨域查询是“多 skill 顺序执行 + 汇总”，后续可继续升级为更细粒度编排

## 后续可继续优化

- 增加正式的 API 文档页说明
- 为用户管理与注册补自动化测试
- 将跨域汇总从顺序编排升级为并行执行
- 将技能级 SQL 规则继续按正式生产库字段细化
