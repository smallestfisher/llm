# BOE Data Copilot (V2.0 生产级架构)

## 项目架构深度解析
本项目采用 **意图驱动 (Intent-Driven) 的 Agentic 工作流**，核心理念是通过 LLM 对用户查询进行语义理解，按需加载 Schema 以优化 Token 消耗，并具备自动重试纠错能力。

### 1. 核心工作流 (State Graph)
系统基于 `langgraph` 构建，状态流转如下：
- **`normalize_question`**: 对用户口语化表达进行归一化（Lexicon 字典映射）。
- **`extract_intent`**: 意图识别，解析过滤器（Filters），确定目标表。
- **`refine_filters`**: 增强过滤器逻辑（如识别“最近N天”）。
- **`get_schema`**: **动态加载** 仅相关的 DDL（表结构）。
- **`write_sql`**: 基于业务感知的 SQL 生成（注入 PMC 核心业务逻辑）。
- **`execute_sql`**: 数据库查询，包含自动限流（LIMIT）与统计。
- **`reflect_sql`**: 自动纠错机制（SQL 执行失败时，注入报错信息反思并重写）。
- **`generate_answer`**: 基于结果生成专业回答（支持可视化生成）。

### 2. 关键目录与扩展指南

| 模块 | 路径 | 扩展重点 |
| :--- | :--- | :--- |
| **工作流逻辑** | `core/graph.py` | 新增 Agent 节点或优化路由逻辑 |
| **业务语义/提示词** | `core/prompts.py` | 调整 SQL 生成策略或 Answer 风格 |
| **数据库/连接** | `core/database.py` | 适配新数据库或修改执行机制 |
| **配置/元数据** | `core/config/` | **最常用：** 新增/修改表结构描述 (tables.json) |
| **业务字典** | `core/lexicon.py` | 新增同义词、行业黑话映射 |

---

### 3. 开发扩展示例

#### 示例：新增一张“设备故障日志表 (`equipment_logs`)”
如果需要支持“查询设备故障”的新需求，请遵循以下步骤：

1.  **更新元数据 (`core/config/tables.json`)**:
    添加表定义，确保包含业务描述，辅助 LLM 理解：
    ```json
    "equipment_logs": {
      "desc": "记录产线设备故障、停机时间及原因",
      "columns": {
        "log_id": "主键",
        "equipment_id": "设备唯一编码",
        "fault_time": "故障发生日期时间",
        "downtime_minutes": "停机时长"
      }
    }
    ```

2.  **更新意图定义 (`core/config/intents.json`)**:
    如果需要识别特定的故障查询意图：
    ```json
    {
      "id": "query_equipment_fault",
      "desc": "查询产线设备故障情况或停机时间"
    }
    ```

3.  **验证**:
    系统会自动通过 `node_get_schema` 加载新表结构。如果模型生成 SQL 报错，可以在 `core/prompts.py` 中对应的 `TEXT2SQL_PROMPT` 增加关联逻辑（如果需要与其他表关联）。

---

## 注意事项
- **Anti-Hallucination**: 若发现模型在查询空结果时依然虚构，优先检查 `core/graph.py` 中的 `node_generate_answer` 逻辑与 `core/prompts.py` 中的 `ANSWER_PROMPT` 指导。
- **Token 优化**: 尽量在 `tables.json` 中保持表描述简洁精炼，过长的 DDL 会导致模型注意力分散。
- **测试**: 修改核心逻辑后，必须运行 `test_e2e_engine.py` 等现有测试用例进行回归验证。
