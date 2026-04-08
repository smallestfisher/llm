# BOE Data Copilot (V2.0 生产级架构文档)

## 1. 系统架构
本项目采用 **意图驱动 (Intent-Driven) 的 Agentic 工作流**。系统核心基于 `langgraph` 构建，实现从自然语言到数据洞察的自动化闭环。

### 核心处理链路
1.  **Normalization (标准化)**: 使用 `core/lexicon.py` 进行业务口语归一化（如：“产出” -> `output_qty`）。
2.  **Intent Analysis (意图识别)**: 识别查询意图与筛选器（`core/graph.py` -> `extract_intent`）。
3.  **Dynamic Schema Loading (动态加载)**: 根据意图动态加载 `core/config/tables.json` 中的相关表元数据，降低 Token 噪声。
4.  **SQL Generation (SQL 生成)**: 利用思维链 (CoT) 注入业务约束，生成标准 MySQL 8.0 SQL。
5.  **Self-Correction (纠错反思)**: 具备 `reflect_sql` 节点，当 SQL 执行失败时，自动解析报错并重写。
6.  **Insight Generation (洞察生成)**: 集成 Pandas 进行数据分析，并支持 Plotly 可视化展示。

---

## 2. 部署指南

### 环境依赖
- **Python 3.10+**
- **MySQL 8.0+**
- 依赖项安装: `pip install -r requirements.txt`

### 部署步骤
1.  **数据库配置**: 修改 `.env` 文件，配置 `DB_URI`（例如：`mysql+pymysql://root:password@localhost/boe_planner_db`）。
2.  **初始化环境**: 运行初始化脚本以创建表结构及测试数据：
    ```bash
    python3 init_sql.py
    ```
3.  **启动前端服务**:
    ```bash
    python3 -m chainlit run app.py -w --host 0.0.0.0 --port 8000
    ```

---

## 3. 维护与扩展流程

### 如何新增一张业务表？
1.  **定义表结构**: 在 `core/config/tables.json` 中添加表名及其字段信息（注意：字段描述必须包含中文对照，以提升 LLM 理解能力）。
2.  **建立关联**: 在 `relationships` 字段中显式定义关联规则（例如：`product_code` 关联至 `product_attributes`），确保 SQL 生成时能正确 JOIN。
3.  **配置意图**: 若需要支持新的查询类型，请更新 `core/config/intents.json`。
4.  **注册与测试**: 确保物理数据库已同步该表，并运行回归测试用例：
    ```bash
    python3 test.py
    ```

### 如何优化 SQL 准确性？
*   **语义层扩展**: 编辑 `core/lexicon.py`，将一线产线的特定“黑话”或缩写映射为对应的字段逻辑。
*   **Prompt 调优**: 维护 `core/prompts.py` 中的 `TEXT2SQL_PROMPT`，通过增强约束提示词引导模型行为。
*   **思维链反馈**: 通过控制台观察流式思维链日志 `>>> [思维链]`，若发现逻辑路径错误，重点审查 `get_schema` 加载的表元数据是否完整。

---

## 4. 开发规范
*   **严禁硬编码**: 所有业务规则优先配置化（JSON），避免在 Python 代码中埋入业务逻辑。
*   **安全防御**: Agent 已内置 `node_check_guard`，非业务相关查询会被自动拦截，请勿随意更改 `GUARD_PROMPT` 配置。
*   **流式输出**: 节点执行日志均已实现流式打印，调试时请优先观察控制台输出。
