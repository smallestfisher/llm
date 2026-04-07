# BOE Data Copilot (V2.0 生产级架构)

## 项目简介
本项目是一个基于 **Chainlit** 和 **LangGraph** 构建的智能生产计划查询助手。它专门为 BOE 生产管理（PMC）设计，能够将复杂的自然语言查询转化为精准的 SQL 并在 12 张核心业务表上执行，提供从需求到实绩的全链路数据洞察。

## 核心架构与优化
1.  **意图驱动的 Schema 加载 (Efficiency)**:
    *   流程先识别用户查询的表意图，仅加载相关的表结构（DDL），大幅降低 LLM 上下文 Token 消耗，提升生成速度。
2.  **业务感知的 Few-Shot SQL (Accuracy)**:
    *   在提示词中注入了 PMC 核心业务逻辑（如达成率计算、跨粒度汇总、库存缺口分析），引导 LLM 生成符合 BOE 业务逻辑的 SQL。
3.  **自反思重试机制 (Reliability)**:
    *   引入 `reflect_sql` 节点。当 SQL 执行报错时，系统会自动捕获错误信息，结合上下文进行自诊断并尝试修复（最高重试 3 次），极大提高了复杂查询的成功率。
4.  **元数据增强 (Context)**:
    *   `tables.json` 中定义了详尽的字段业务描述和粒度说明，确保 LLM 理解“日产出”与“月计划”的区别。

## 业务覆盖 (12 张核心表)
- **需求端**: `v_demand` (客户), `p_demand` (工厂承诺)
- **计划端**: `monthly_plan_approved`, `weekly_rolling_plan`, `daily_schedule`
- **实绩端**: `production_actuals`, `work_in_progress` (WIP)
- **库存端**: `daily_inventory`, `oms_inventory`
- **维表与财务**: `product_attributes`, `product_mapping`, `sales_financial_perf`

## 快速开始
1.  **环境安装**: `pip install -r requirements.txt`
2.  **配置**: 确保 `.env` 中的 `OPENAI_API_KEY` 和 `DB_URI` 正确。
3.  **启动 Web UI**: `chainlit run app.py`
4.  **启动命令行测试**: `python3 test_cli.py`

## 技术栈
- **Orchestration**: LangGraph
- **LLM**: Qwen/GPT (通过 ChatOpenAI 接口)
- **Frontend**: Chainlit
- **Database**: MySQL (Business) + SQLite (Memory)
