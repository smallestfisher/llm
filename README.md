# BOE Data Copilot

一个面向制造业数据问答场景的 Web 应用。

这版工程保留了原有的 `LangGraph + Text2SQL + SQL` 后端链路，同时将前端替换为基于 `FastAPI + Jinja2` 的普通 Web 应用，内置本地账号、角色控制、密码修改、禁用账号、聊天历史和审计日志。

## 功能概览

- 自然语言转 SQL 查询
- 基于 `LangGraph` 的工作流编排
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
- LangGraph
- OpenAI 兼容接口
- MySQL 8.0+
- SQLite

## 系统架构

系统分为两套数据存储：

1. `DB_URI`
   业务数据库，供 `Text2SQL` 查询使用。

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
2. `LangGraph` 执行语义解析、守卫、过滤修正、Schema 装载
3. LLM 生成只读 SQL
4. SQL 执行业务查询
5. 返回自然语言答案和表格结果
6. 查询行为写入审计日志和聊天历史

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
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
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
│   ├── graph.py            # LangGraph 工作流
│   ├── prompts.py          # 提示词
│   ├── lexicon.py          # 轻量术语归一化
│   ├── heuristics.py       # 规则修正
│   └── config/             # intents / tables / heuristics 配置
└── tests/
    ├── eval_runner.py
    └── goldens.json
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

注意：评测脚本依赖模型服务和业务数据库可用。

## 当前实现说明

- 前端已不再依赖 Chainlit
- 聊天历史由本地库保存
- LangGraph checkpoint 仍保存在本地 SQLite 文件 `langgraph_memory.db`
- 查询接口默认只支持业务数据问答，不处理闲聊和无关问题

## 后续可继续优化

- 增加正式的 API 文档页说明
- 为用户管理与注册补自动化测试
- 将审计日志增加筛选、搜索和导出
- 为聊天页增加流式响应和更细的执行状态提示

