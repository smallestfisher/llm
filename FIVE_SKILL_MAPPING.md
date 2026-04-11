# 当前 11 张表到 5-Skill 的映射

这份文档描述的是当前工程真实落地后的映射，不再使用旧版本里已经失效的 `daily_schedule`、`work_in_progress`、12 表假设。

## 1. 当前技能划分

当前运行时的 5 个主业务 skill：

1. `production`
2. `planning`
3. `inventory`
4. `demand`
5. `sales`

另有：

- `general`
  兜底 skill
- `cross_domain`
  不是独立业务表 skill，而是编排模式

## 2. 表到 Skill 的归属

| 表名 | 主归属 Skill | 说明 |
|---|---|---|
| `production_actuals` | `production` | 生产执行主表 |
| `daily_PLAN` | `planning` | 日排产主表 |
| `weekly_rolling_plan` | `planning` | 周滚计划主表 |
| `monthly_plan_approved` | `planning` | 审批版月计划主表 |
| `daily_inventory` | `inventory` | 日库存主表 |
| `oms_inventory` | `inventory` | OMS/月库存主表 |
| `v_demand` | `demand` | V版 forecast 主表 |
| `p_demand` | `demand` | P版 commit 主表 |
| `sales_financial_perf` | `sales` | 销量/财务业绩主表 |
| `product_attributes` | 共享辅助表 | 多 skill 共用维表 |
| `product_mapping` | 共享辅助表 | 多 skill 共用映射表 |

## 3. 每个 Skill 的职责边界

### `production`

只回答：

- 实际投入
- 实际产出
- 报废
- 不良
- 工厂/产品/日期范围内的执行结果

不要放进来：

- 月计划
- 周滚计划
- 库存覆盖
- V/P 需求承诺
- 销量和财务业绩

### `planning`

只回答：

- 日排产
- 周滚版本
- 审批版月计划
- 计划结构
- 计划版本

不要放进来：

- 实际产出达成
- 库存是否足够
- forecast / commit
- 销量和财务结果

### `inventory`

只回答：

- TTL/Hold 库存
- OMS
- 客户仓 / hub
- 库龄
- 库位与库存结构

不要放进来：

- 计划值
- 实际产出值
- 需求承诺值
- 销量财务值

库存域在跨域问题里只给库存侧事实，不自己代替其他域做最终判断。

### `demand`

只回答：

- V版 forecast
- P版 commit
- 横表月份字段
- 缺口与覆盖的需求侧事实

不要放进来：

- 库存支撑
- 计划兑现
- 销量财务

### `sales`

只回答：

- `sales_qty`
- `FINANCIAL_qty`
- 客户 / SBU / BU / 产品维度业绩

不要放进来：

- 计划达成
- 实际生产
- 需求承诺
- 库存支撑

## 4. 典型问法归属

### 应落到 `production`

- 昨天报废实绩
- 最近 7 天各工厂 panel 实际产出
- 最近三天不良最多的是哪个产品

### 应落到 `planning`

- 今天 B4_BJ 的日排产是多少
- 2026W03 版本周滚计划
- 本月审批版月计划里的 panel 产出目标

### 应落到 `inventory`

- 今天各厂 TTL 库存还有多少
- Hold 库存主要压在哪些料号
- 客户仓和 hub 库存先看一下

### 应落到 `demand`

- 2026W03 这版 forecast 需求是多少
- 2026W03 这版 P版承诺需求
- 未来第三个月的 P版承诺

### 应落到 `sales`

- 上个月各客户销量
- 上月财务业绩前十客户
- 按 BU 看这个月销售量

## 5. 典型跨域组合

### `inventory + planning`

问题类型：

- 库存能否支撑下周排产
- 结合库存和排产看哪些产品会缺料

### `demand + planning`

问题类型：

- 需求能不能被月计划覆盖

### `production + planning`

问题类型：

- 对比本月审批版计划和实际产出差多少

### `demand + inventory`

问题类型：

- forecast 增长会影响哪些产品库存

### `production + sales`

问题类型：

- 销售和生产实绩对照一下，看看有没有背离

### `planning + sales`

问题类型：

- 对比月计划和销量差异

## 6. 当前建议

如果后续继续做精调，原则不是再拆更多 skill，而是：

1. 保持这 5 个域边界稳定
2. 让每个域 first-shot SQL 更稳
3. 增加真实问题集
4. 用生产字段继续收窄 prompt 和 lint

当前这版 5-skill 已经足够覆盖主问题类型，不建议再回退到大而混的 skill。
