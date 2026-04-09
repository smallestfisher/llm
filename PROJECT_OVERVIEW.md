# BOE Data Copilot (V2.0 生产级架构文档)

## 1. 系统架构
本项目采用意图驱动的 Agentic 工作流。系统核心基于 `langgraph` 构建，通过统一语义解析、SQL 生成与结果解读，实现从自然语言到数据洞察的自动化闭环。

### 核心处理链路
1. **Query Parsing (统一语义解析)**: `core/graph.py` 中的 `parse_query` 节点先调用 `core/lexicon.py` 做轻量业务别名归一化，再交给 LLM 一次性完成问题标准化、意图识别和筛选器抽取。
2. **Guard Check (安全守卫)**: `node_check_guard` 通过通用 Guard Prompt 模板结合业务域配置，拦截闲聊、无关问题和攻击性输入。
3. **Filter Refinement (条件修正)**: 基于规则补充最近 N 天、显式日期、单表猜测等结构化过滤条件。
4. **Dynamic Schema Loading (动态 Schema 加载)**: 根据意图和过滤条件，从当前业务域配置中的 `tables.json` 中筛选相关表元数据，降低上下文噪声。
5. **SQL Generation (SQL 生成)**: 通过通用 Text2SQL Prompt 模板结合业务域注入约束，生成 MySQL 8.0 只读查询。
6. **Self-Correction (纠错反思)**: `reflect_sql` 节点在 SQL 执行失败时根据报错进行自动修复，最多重试 3 次。
7. **Insight Generation (洞察生成)**: 使用 Pandas 汇总结果；聚合统计场景可生成自然语言回答，明细查询优先直接返回记录数量和结果表。

### 关键模块
- `app.py`: Chainlit 入口，处理登录、会话恢复、消息流转和思考状态展示。
- `core/graph.py`: LangGraph 工作流定义，包含解析、守卫、SQL 执行、纠错和回答生成。
- `core/prompts.py`: 维护通用 Prompt 模板与构建函数，业务约束由域配置注入。
- `core/lexicon.py`: 通用归一化逻辑，业务别名由当前业务域配置驱动。
- `core/config/loader.py`: 统一解析当前业务域配置，默认域为 `boe`，可通过 `APP_DOMAIN` 切换。
- `core/config/domains/boe/intents.json`: BOE 域的意图定义，包含 `desc`、`aliases`、`examples`。
- `core/config/domains/boe/tables.json`: BOE 域的表结构、字段说明和表间关系。
- `core/config/domains/boe/lexicon.json`: BOE 域的术语映射与业务别名。
- `core/config/domains/boe/normalize_aliases.json`: BOE 域的轻量语义归一化别名配置。
- `core/config/domains/boe/prompt_context.json`: BOE 域注入到通用 Prompt 模板中的业务约束和角色定义。

---

## 2. 部署指南

### 环境依赖
- **Python 3.10+**
- **MySQL 8.0+**
- 依赖项安装: `pip install -r requirements.txt`

### 部署步骤
1. **数据库配置**: 修改 `.env` 文件，配置 `DB_URI`、`OPENAI_BASE_URL`、`OPENAI_API_KEY` 等运行参数。
2. **初始化环境**: 运行初始化脚本创建表结构及测试数据。
   ```bash
   python3 init_sql.py
   ```
3. **启动前端服务**:
   ```bash
   python3 -m chainlit run app.py -w --host 0.0.0.0 --port 8000
   ```

---

## 3. 维护与扩展流程

### 如何新增一张业务表？
1. **定义表结构**: 在当前业务域目录下的 `tables.json` 中添加表名、字段信息和中文说明。默认路径为 `core/config/domains/boe/tables.json`。
2. **建立关联**: 在 `relationships` 中显式定义 JOIN 规则，例如 `product_code` 关联到产品属性或工厂映射表。
3. **补充意图或示例**: 如果新表承载新的查询场景，更新当前业务域下的 `intents.json`，至少补充对应意图的 `desc`、`aliases`、`examples`。
4. **同步物理数据库**: 确保实际数据库已有该表及必要测试数据。
5. **回归测试**: 运行评测脚本验证典型问句。
   ```bash
   python3 tests/eval_runner.py
   ```

### 如何优化语义识别准确性？
- **扩充意图定义**: 优先维护当前业务域下的 `intents.json`，为每个意图补充更丰富的 `aliases` 和真实业务问句 `examples`。
- **维护轻量别名库**: 在当前业务域下的 `normalize_aliases.json` 中补充高频黑话、缩写和常见同义表达，但不要把它设计成主分类器。
- **调优解析 Prompt**: 调整 `core/prompts.py` 中的通用 prompt 构建函数，必要时补充业务域下 `prompt_context.json` 的约束信息。

### 如何优化 SQL 准确性？
- **Schema 质量优先**: 保持当前业务域下 `tables.json` 的字段说明、中文语义和关系定义完整。
- **Prompt 调优**: 优先维护业务域下的 `prompt_context.json`，必要时再调整 `core/prompts.py` 中的通用模板。
- **关注纠错链路**: 通过控制台日志观察 `reflect_sql` 的触发频率和报错模式，反向修正 schema 或 prompt。

### 表结构变更适配 Checklist
当数据库表结构发生变化时，建议严格按以下顺序适配，避免 SQL 输出和实际库结构脱节：

1. **确认变更类型**: 先判断是新增字段、字段重命名、字段删除、时间字段变更、表拆分合并，还是关联键变化。字段重命名、时间语义变化和关系变化的适配成本最高。
2. **先改物理数据库**: 在实际 MySQL 中完成 DDL 变更，并准备一批可用于调试的真实或测试数据。
3. **同步 `tables.json`**: 立即更新当前业务域下 `tables.json` 中的字段列表、中文说明、表用途和 `relationships`。如果时间字段或主关联键变化，这一步必须和数据库变更同步完成。
4. **检查意图影响面**: 如果用户问法会因表结构变化而受影响，补充当前业务域下 `intents.json` 中的 `aliases` 和 `examples`，确保新问法、新字段名和旧业务口径都能被识别。
5. **检查术语映射**: 如果一线仍沿用旧字段叫法或黑话，更新当前业务域下的 `normalize_aliases.json` 和 `lexicon.json`，保证解析阶段还能把用户说法归到新结构上。
6. **调优 SQL Prompt**: 如果变更会影响 JOIN 路径、时间过滤规则、默认分组方式或业务口径，优先更新业务域下的 `prompt_context.json`，不要只依赖模型自行猜测。
7. **回归跑典型问句**: 执行 `python3 tests/eval_runner.py`，重点观察涉及新字段、旧字段别名、时间过滤和多表 JOIN 的问题是否仍能生成正确 SQL。
8. **针对失败样例补测试**: 每出现一次错误 SQL，就把对应问句补进 `tests/goldens.json` 或扩充评测集，避免同类问题回归。
9. **最后再看纠错链路**: 如果大量请求都依赖 `reflect_sql` 才能成功，说明前面的 schema、prompt 或语义解析还没配到位，不要把纠错节点当作主适配手段。

### 推荐调试顺序
如果改表后发现 SQL 质量下降，建议按这个顺序排查：

1. 先看当前业务域下的 `tables.json` 是否和真实库一致。
2. 再看 `parse_query` 输出的 `intent`、`filters`、`normalized_question` 是否已经偏了。
3. 再看当前业务域下的 `prompt_context.json` 是否缺少关键业务约束，必要时再调整 `core/prompts.py` 的通用模板。
4. 最后才看 `reflect_sql` 是否只是掩盖了前面的配置问题。

---

## 4. 开发规范
- **严禁硬编码**: 所有业务规则优先配置化，意图、表结构和术语别名尽量沉淀到 JSON 或独立模块。
- **安全防御**: Agent 已内置 `node_check_guard`，非业务相关查询会被自动拦截，请勿随意放宽业务域中的守卫范围定义。
- **流式输出**: 节点执行日志支持流式打印，调试时优先观察控制台中的 `>>> [思维链]`。
- **配置优先于代码**: 新增业务问法时，优先补当前业务域下的 `intents.json`、`lexicon.json`、`normalize_aliases.json`，再考虑修改工作流逻辑。

## 5. 业务域隔离
- 默认业务域为 `boe`，配置目录为 `core/config/domains/boe/`。
- 可通过环境变量 `APP_DOMAIN` 切换到其它业务域，`core/config/loader.py` 会优先从 `core/config/domains/<APP_DOMAIN>/` 加载 `tables.json`、`intents.json`、`lexicon.json`、`normalize_aliases.json`、`prompt_context.json`。
- 如果指定业务域缺少某个配置文件，loader 会自动回退到 `core/config/` 下的旧路径，保证现有脚本和增量迁移不被一次性打断。
- 如果后续需要接入新的业务线，建议直接新增 `core/config/domains/<domain_name>/`，先复用现有通用流程，不要先改 `graph.py`。
