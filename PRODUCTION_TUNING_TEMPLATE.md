# 生产库精调模板

用于把当前工程从“现有字段版本”继续精调到正式生产库字段。

当前模板已经对齐到现在的 5 个技能架构与 11 张业务表，不再沿用旧版的 3 技能 / 12 表假设。

## 1. 使用原则

1. 先确认真实表和字段
2. 再改 [backend/app/config/tables.json](/home/y/llm/llm/backend/app/config/tables.json)
3. 再改对应技能
4. 再改 router / heuristics / lexicon
5. 最后补 tests / goldens

不要先改 prompt 再去猜表字段。

## 2. 当前技能

### `production`

- 主表：`production_actuals`
- 辅助表：`product_attributes`、`product_mapping`

### `planning`

- 主表：`daily_PLAN`、`weekly_rolling_plan`、`monthly_plan_approved`
- 辅助表：`product_attributes`、`product_mapping`

### `inventory`

- 主表：`daily_inventory`、`oms_inventory`
- 辅助表：`product_attributes`、`product_mapping`

### `demand`

- 主表：`v_demand`、`p_demand`
- 辅助表：`product_attributes`、`product_mapping`

### `sales`

- 主表：`sales_financial_perf`
- 辅助表：`product_attributes`、`product_mapping`

### `general`

- 兜底技能
- 不应该承接高频正式业务问题

## 3. 当前 11 张业务表

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

## 4. 环境信息

### 基础连接信息

- 环境名称：
- 数据库类型：
- Host：
- Port：
- Database / Schema：
- 账号权限范围：
- 是否只读：

### 运行参数

- `DB_URI`：
- `BACKEND_DB_URI`：
- `OPENAI_BASE_URL`：
- `LLM_MODEL`：

### 风险说明

- 是否存在视图：
- 是否存在历史表：
- 是否存在字段同名异义：
- 是否存在敏感字段：
- 是否存在带空格列名：

## 5. 表级确认模板

每张表复制一份。

### 表名：`<table_name>`

- 中文名称：
- 所属技能：
- 表类型：明细 / 汇总 / 维表 / 视图
- 用途说明：
- 主键：
- 唯一键：
- 时间字段：
- 月份字段：
- 版本字段：
- 默认排序字段：
- 典型过滤字段：
- 典型分组字段：
- 典型聚合字段：
- 是否允许全表明细：
- 是否必须默认带时间过滤：
- 备注：

#### 真实关联关系

- `<field>` -> `<target_table>.<target_field>`

#### 禁止或高风险事项

-

## 6. 字段模板

### 表名：`<table_name>`

| 字段名 | 中文含义 | 类型 | 示例值 | 可空 | 可筛选 | 可分组 | 可聚合 | 业务别名 / 黑话 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |

## 7. 技能精调清单

### 生产技能

对应文件：

- [backend/app/skills/production.py](/home/y/llm/llm/backend/app/skills/production.py)

需要确认：

- 实际投入口径
- 实际产出口径
- 报废 / 不良口径
- `act_type` 真实枚举值
- 是否存在工厂字段别名

### 计划技能

对应文件：

- [backend/app/skills/planning.py](/home/y/llm/llm/backend/app/skills/planning.py)

需要确认：

- 日 / 周 / 月三层计划边界
- 周版本口径
- `daily_PLAN.target_qty` 是投入还是产出
- `monthly_plan_approved` 的四个 target 字段真实含义

### 库存技能

对应文件：

- [backend/app/skills/inventory.py](/home/y/llm/llm/backend/app/skills/inventory.py)

需要确认：

- TTL / Hold 真实业务定义
- OMS 中客户仓 / hub 的判断字段
- 库龄桶是否固定
- `report_date` / `report_month` 最新值规则

### 需求技能

对应文件：

- [backend/app/skills/demand.py](/home/y/llm/llm/backend/app/skills/demand.py)

需要确认：

- V版 / P版是否只是表口径
- `PM_VERSION` 格式
- `MONTH` / `NEXT_REQUIREMENT` / `LAST_REQUIREMENT` 真实月份映射
- 多月汇总口径

### 销售技能

对应文件：

- [backend/app/skills/sales.py](/home/y/llm/llm/backend/app/skills/sales.py)

需要确认：

- `sales_qty` 与 `FINANCIAL_qty` 的真实定义
- `report_month` 的格式
- `FGCODE` 与产品维表的真实连接方式

## 8. Router 与过滤器精调

对应文件：

- [backend/app/workflow/router.py](/home/y/llm/llm/backend/app/workflow/router.py)
- [backend/app/semantic/filters.py](/home/y/llm/llm/backend/app/semantic/filters.py)

需要确认：

- 各域关键词
- 黑话 / 缩写 / 别名
- 相对时间词
- 版本号格式
- 工厂编码格式

## 9. SQL 保护链精调

对应文件：

- [backend/app/execution/sql_guard.py](/home/y/llm/llm/backend/app/execution/sql_guard.py)

需要确认是否新增规则：

- 伪月份占位
- 伪字段别名
- `SELECT *`
- 缺失版本 / 时间过滤
- 占位字面值
- 不必要的 JOIN
- 带空格列名
