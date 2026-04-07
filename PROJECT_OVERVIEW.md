# 项目架构与部署说明（BOE 生产计划查询助手）

## 一、整体架构

### 1. Chainlit 前端与入口
- 入口文件：`app.py`
- 作用：
  - 启动 Chainlit 应用
  - 用户认证（账号/密码）
  - 展示模板命中、SQL、数据库结果预览
  - 输出执行耗时、路由信息

### 2. LangGraph 后端流程
- 核心文件：`core/graph.py`
- 流程节点：
  1. `get_schema`：获取表结构
  2. `normalize_question`：黑话归一化
  3. `extract_intent`：意图与条件抽取
  4. `refine_filters`：补全单表统计维度/指标
  5. `render_template`：模板 SQL 生成（优先）
  6. `write_sql`：LLM 兜底生成 SQL
  7. `execute_sql`：执行查询
  8. `generate_answer`：生成自然语言回答

### 3. 数据库访问
- 连接文件：`core/database.py`
- 使用 `langchain_community.utilities.SQLDatabase`
- 通过 `.env` 中的 `DB_URI` 连接 MySQL 8.0
- 只暴露业务表（排除业务无关表）

### 4. 查询与意图配置
- 配置：`core/config/intents.json`、`core/config/tables.json`
- 当前运行模式：LLM 直接生成 SQL（无模板）

### 5. 黑话归一化
- 文件：`core/lexicon.py`
- 词表配置：`core/config/lexicon.json`
- 常见“黑话/简称/模糊词” -> 标准表/字段映射
- 模糊匹配：`difflib.SequenceMatcher`

### 6. 单表查询增强
- 文件：`core/heuristics.py`
- 规则配置：`core/config/heuristics.json`
- 作用：
  - 自动补全 `group_by`（例如“按工厂/按产品”）
  - 自动补全 `metric`（例如“总量/可用库存/良率”）
  - 自动识别“最近N天”并转为时间过滤

### 7. 本地历史记录
- 文件：`core/local_data.py`
- 作用：
  - 保存聊天线程/步骤/元素/反馈
  - 支持对话历史列表与删除同步

---

## 二、部署方式

### 1. 依赖安装
```bash
pip install -r requirements.txt
```

### 2. 数据库配置
在项目根目录配置 `.env`：
```env
DB_URI=mysql+pymysql://root:021598@172.17.0.2:3306/boe_planner_db?charset=utf8mb4
```

### 3. 启动服务
```bash
python3 -m chainlit run app.py -w --headless --host 0.0.0.0 --port 8000
```

### 4. 开发调试日志（可选）
```bash
DEBUG_TRACE=1 python3 -m chainlit run app.py -w --headless --host 0.0.0.0 --port 8000
```

---

## 三、后续新增/修改功能需要改哪些文件

### 1. 扩展意图清单
- 配置：`core/config/intents.json`
- 改法：新增意图描述
- 注意：
  - 统计类不加 `LIMIT`
  - 明细类才加 `LIMIT`

### 2. 扩展意图识别
- 文件：`core/prompts.py`
- 配置：`core/config/intents.json`
- 改法：新增意图描述即可，Prompt 会动态生成

### 3. 扩展黑话/同义词
- 文件：`core/lexicon.py`
- 配置：`core/config/lexicon.json`
- 改法：增加映射项即可

### 4. 强化单表统计能力
- 文件：`core/heuristics.py`
- 配置：`core/config/heuristics.json`
- 改法：扩展 `group_by_keywords` / `metric_keywords`

### 5. SQL 安全控制
- 文件：`core/graph.py`
- 改法：
  - 只允许 `SELECT/CTE`
  - 明细类自动追加 `LIMIT`

### 6. 可视化中间过程
- 文件：`app.py`
- 改法：
  - 展示 Template Match
  - 展示 Refined Filters
  - 展示 SQL & DB Result 预览

### 7. 历史记录问题
- 文件：`core/local_data.py`
- 改法：
  - 检查 thread/step/elements 的一致性
  - 删除对话级联清理

---

## 四、当前支持的主表清单
- daily_inventory
- daily_schedule
- monthly_plan_approved
- oms_inventory
- p_demand
- product_attributes
- product_mapping
- production_actuals
- sales_financial_perf
- v_demand
- weekly_rolling_plan
- work_in_progress

## 七、配置文件一览
- `core/config/intents.json`：意图列表与说明
- `core/config/tables.json`：表与字段白名单
- `core/config/lexicon.json`：黑话/同义词映射
- `core/config/heuristics.json`：单表统计关键词规则

---

## 五、常见操作建议
- 如果“最新月份”无数据：
  - 系统会优先用当前月
  - 无当前月则回退数据库最大月份
- 如果单表统计只返回维度不返回数值：
  - 优先看 `Refined Filters` 是否补全了 `metric/metric_field`

---

## 六、扩展建议（可选）
- 增加更多统计类模板（缺口、达成率、库存覆盖天数）
- 增加结果后处理（TopN、占比、同比环比）
- 引入知识库/文档问答（业务口径说明）
