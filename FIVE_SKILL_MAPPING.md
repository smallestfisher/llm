# 12 张表到 5-Skill 的推荐映射方案

这份文档用于回答一个核心问题：

> 当前这 12 张业务表，长期来看应该如何拆成更合理的 skill，而不是继续把所有问题塞进少数几个大 skill 里。

目标不是一次性把代码全部拆完，而是先形成一版清晰、可执行、可扩展的业务分层方案，后续无论是调 router、调 prompt，还是拆 skill，都有统一参考。

---

## 1. 为什么推荐从 3-Skill 走向 5-Skill

当前系统里的 `production_skill + inventory_skill + generic_skill`，更适合做：

- 架构迁移期的稳定承接
- 先把主运行链路从旧单体流程迁出来
- 先覆盖大部分常见问答

但如果后面要接真实生产库，并追求更高精度，这种划分会越来越吃力，原因是：

1. `production_skill` 现在包得太宽  
   生产实绩、日排产、周计划、月计划、需求承诺、财务表现、在制，严格说不是一个自然业务域。

2. `generic_skill` 不适合长期承接专业场景  
   它适合兜底，不适合成为高频正式业务问题的主入口。

3. 跨域问题的前提是单域边界清晰  
   如果单域内部已经混得过宽，跨域编排就很难做出真正可控的结果。

所以更推荐的长期形态是：

- 5 个明确业务 skill
- 1 个 generic fallback skill

也就是：

1. `production_execution_skill`
2. `planning_skill`
3. `inventory_supply_skill`
4. `demand_commit_skill`
5. `sales_finance_skill`
6. `generic_skill` 作为兜底

---

## 2. 12 张表总览

当前 `core/config/tables.json` 中的 12 张表如下：

1. `daily_inventory`
2. `daily_schedule`
3. `monthly_plan_approved`
4. `oms_inventory`
5. `p_demand`
6. `product_attributes`
7. `product_mapping`
8. `production_actuals`
9. `sales_financial_perf`
10. `v_demand`
11. `weekly_rolling_plan`
12. `work_in_progress`

其中：

- `product_attributes`
- `product_mapping`

本质上更像共享维表/辅助表，不适合单独承担太多主查询，但会被多个 skill 复用。

---

## 3. 推荐 5-Skill 方案

### Skill 1: `production_execution_skill`

**核心职责**

- 回答生产执行层面的实际发生了什么
- 聚焦实绩、良率、不良、停机、产出、产线表现
- 处理“计划 vs 实际”的执行侧分析

**主表**

- `production_actuals`
- `daily_schedule`

**辅助表**

- `product_attributes`
- `product_mapping`

**适合承接的问题**

- 最近一周各产线良率怎么样
- 哪些线别停机时长最高
- A 产线昨天实际产出是多少
- 按产品看投料和产出差异
- 哪些产品不良数量异常
- 日排产和实际达成偏差有多大

**不建议放进这个 skill 的问题**

- 月计划基准和周计划变更
- 需求 forecast / commit 覆盖率
- 销量、营收、毛利
- 库存与客户侧在途分析

**对应业务对象**

- 线别 / 机台
- 生产日期
- 投料 / 产出
- 良率 / 不良 / 停机

---

### Skill 2: `planning_skill`

**核心职责**

- 回答计划体系本身的问题
- 处理月计划、周滚动计划、日排产之间的关系
- 关注“计划是什么、如何调整、是否兑现”

**主表**

- `monthly_plan_approved`
- `weekly_rolling_plan`
- `daily_schedule`

**辅助表**

- `product_attributes`
- `product_mapping`

**适合承接的问题**

- 本月计划量是多少
- 周计划调整的主要原因是什么
- 哪些产品周计划多次变更
- 月计划和周计划差异有哪些
- 周计划和日排产是否一致
- 不同工厂本周排产结构如何

**不建议放进这个 skill 的问题**

- 实际产出、良率、不良异常
- 库存够不够支撑计划
- 需求满足率
- 财务结果

**对应业务对象**

- 月 / 周 / 日计划
- 工厂
- 调整原因
- 计划版本

---

### Skill 3: `inventory_supply_skill`

**核心职责**

- 回答库存与供应保障问题
- 处理可用库存、安全库存、在途、客户仓、在制、齐套、缺料风险
- 更关注“能不能支撑排产或交付”

**主表**

- `daily_inventory`
- `oms_inventory`
- `work_in_progress`

**辅助表**

- `daily_schedule`
- `product_attributes`
- `product_mapping`

**适合承接的问题**

- 当前哪些产品库存低于安全库存
- 在途库存有多少
- 客户仓和 hub 库存覆盖情况如何
- 哪些产品会影响下周排产
- 在制和现有库存能否支撑本周计划
- 哪些产品存在缺料风险

**不建议放进这个 skill 的问题**

- 需求预测与承诺满足率
- 月计划或周计划基准分析
- 毛利、营收类问题

**对应业务对象**

- 可用库存
- 安全库存
- 在途 / hub / 客户仓
- 在制
- 缺料 / 齐套 / 供应风险

---

### Skill 4: `demand_commit_skill`

**核心职责**

- 回答需求与承诺层面的关系
- 处理 forecast、客户需求、生产承诺、覆盖率、缺口
- 更关注“市场/客户需求和制造承诺之间的差异”

**主表**

- `v_demand`
- `p_demand`

**辅助表**

- `product_attributes`
- `product_mapping`

**适合承接的问题**

- 未来三个月 forecast 和 commit 差多少
- 哪些产品承诺满足率低于 90%
- 某客户未来两个月需求覆盖情况怎么样
- 需求缺口最大的产品有哪些
- forecast 与实际 commit 的偏差趋势如何

**不建议放进这个 skill 的问题**

- 当前实际库存与在途
- 当前良率或停机异常
- 销售收入、毛利表现

**对应业务对象**

- 客户需求
- 生产承诺
- 覆盖率 / 缺口
- 客户 / 产品 / 月份

---

### Skill 5: `sales_finance_skill`

**核心职责**

- 回答产销和财务表现问题
- 处理销量、收入、单价、毛利及其与计划的关系
- 更偏经营结果解读

**主表**

- `sales_financial_perf`

**辅助表**

- `monthly_plan_approved`
- `product_attributes`
- `product_mapping`

**适合承接的问题**

- 本月哪些产品收入最高
- 哪些产品毛利率最低
- 销量和计划达成差异如何
- 按技术族看营收结构
- 按产品看单价和毛利变化

**不建议放进这个 skill 的问题**

- 实际生产异常
- 库存和缺料
- 需求承诺覆盖

**对应业务对象**

- 销量
- 单价
- 营收
- 毛利
- 经营达成

---

## 4. 两张共享维表怎么处理

### `product_attributes`

建议定位为：

- 所有 skill 的共享维表
- 用于补充技术族、应用领域、生命周期等属性

更适合被这样使用：

- 作为 join 辅助表
- 用来做按技术族/应用/生命周期分组
- 用来做维度过滤

不建议把它做成单独高频主 skill，原因是：

- 用户通常不会只问“属性表本身”
- 他们更常问“某类产品在计划/库存/销量上的表现”

### `product_mapping`

建议定位为：

- 共享映射表
- 用于补充推荐工厂、替代工厂、切割效率、基板世代等制造映射信息

更适合被这样使用：

- 作为生产、计划、库存、需求 skill 的辅助 join
- 用于解释产品适合在哪个工厂生产
- 用于补充切割效率或工厂偏好

如果未来“产品选厂 / 切割效率 / 工厂推荐”问题很多，也可以再单独拆出：

- `product_master_skill`

但在当前 12 张表规模下，还不一定有必要独立成第 6 个正式 skill。

---

## 5. 表到 Skill 的推荐映射表

| 表名 | 推荐归属 Skill | 角色 |
|---|---|---|
| `production_actuals` | `production_execution_skill` | 主表 |
| `daily_schedule` | `production_execution_skill` / `planning_skill` / `inventory_supply_skill` | 共享主表 |
| `weekly_rolling_plan` | `planning_skill` | 主表 |
| `monthly_plan_approved` | `planning_skill` / `sales_finance_skill` | 主表 / 辅助表 |
| `daily_inventory` | `inventory_supply_skill` | 主表 |
| `oms_inventory` | `inventory_supply_skill` | 主表 |
| `work_in_progress` | `inventory_supply_skill` | 主表 |
| `v_demand` | `demand_commit_skill` | 主表 |
| `p_demand` | `demand_commit_skill` | 主表 |
| `sales_financial_perf` | `sales_finance_skill` | 主表 |
| `product_attributes` | 全部 skill | 共享维表 |
| `product_mapping` | 全部 skill | 共享映射表 |

---

## 6. 典型跨域问题会怎么拆

### 场景 1: 库存是否能支撑下周排产

建议拆分为：

- `inventory_supply_skill`
  - 当前库存、在途、在制情况
- `planning_skill`
  - 下周排产目标

最后由 `composer` 汇总：

- 哪些产品库存可支撑
- 哪些产品缺口大
- 是否需要优先调度

---

### 场景 2: 需求 forecast 是否能被计划与承诺覆盖

建议拆分为：

- `demand_commit_skill`
  - forecast vs commit
- `planning_skill`
  - 月计划 / 周计划承接情况

最后汇总：

- 哪些产品需求缺口大
- 哪些产品虽有 commit，但计划承接不足

---

### 场景 3: 良率问题是否导致交付风险

建议拆分为：

- `production_execution_skill`
  - 良率、不良、停机、产出异常
- `inventory_supply_skill`
  - 当前库存与在制缓冲
- `demand_commit_skill`
  - 承诺覆盖压力

这是比较典型的三 skill 跨域问题。

---

### 场景 4: 产品经营结果为什么不达预期

建议拆分为：

- `sales_finance_skill`
  - 收入、毛利、销量
- `planning_skill`
  - 计划基准
- `production_execution_skill`
  - 实际执行问题

最后汇总经营表现、计划偏差和执行原因。

---

## 7. Router 后续应该怎么跟着拆

如果走 5-skill 方案，router 也应该同步从当前的粗粒度升级成：

- `production_execution`
- `planning`
- `inventory_supply`
- `demand_commit`
- `sales_finance`
- `cross_domain`
- `general`

这样做的好处是：

1. skill 边界更清晰  
2. prompt 更容易写硬  
3. SQL 规则更容易收敛  
4. 跨域编排时更容易解释“为什么要调哪些 skill”

---

## 8. 推荐迁移顺序

如果后面真的要从当前 3-skill 升级到 5-skill，建议按这个顺序做：

### 第一步：先保留现有生产/库存 skill 不动

目标：

- 不打断现有系统运行
- 先把新增 skill 的边界画出来

### 第二步：从 `production_skill` 中拆出 `planning_skill`

优先拆它的原因是：

- 计划类问题和执行类问题天然不同
- `daily_schedule / weekly_rolling_plan / monthly_plan_approved` 边界相对清楚

### 第三步：从 `production_skill` 中拆出 `demand_commit_skill`

把：

- `v_demand`
- `p_demand`

单独拿出来，避免需求承诺逻辑继续混在生产执行逻辑里。

### 第四步：把 `sales_financial_perf` 单独变成 `sales_finance_skill`

这是一个非常适合单独做成经营分析 skill 的表，不建议长期混在生产 skill 里。

### 第五步：保留 `generic_skill` 作为兜底

不要删。

它仍然有价值，用来承接：

- router 低置信度问题
- 新增域还没拆完的问题
- 模糊查询或一次性临时问题

---

## 9. 最终推荐结论

如果你想要一个简洁但足够稳定的长期方案，我建议：

### 正式业务 skill

1. `production_execution_skill`
2. `planning_skill`
3. `inventory_supply_skill`
4. `demand_commit_skill`
5. `sales_finance_skill`

### 兜底 skill

6. `generic_skill`

这比当前的 3-skill 更适合真实生产环境，原因是：

- 更符合业务问题天然边界
- 更利于后续精调字段和 prompt
- 更利于跨域编排
- 更利于做测试与回归

---

## 10. 对当前代码的落地建议

如果按这份方案继续推进，后续代码层面建议这样改：

1. 保留现有：
   - [core/skills/production/skill.py](/home/y/llm/llm/core/skills/production/skill.py)
   - [core/skills/inventory/skill.py](/home/y/llm/llm/core/skills/inventory/skill.py)
   - [core/skills/generic/skill.py](/home/y/llm/llm/core/skills/generic/skill.py)

2. 下一步新增：
   - `core/skills/planning/skill.py`
   - `core/skills/demand/skill.py`
   - `core/skills/sales/skill.py`

3. 然后逐步调整：
   - [core/router/intent_router.py](/home/y/llm/llm/core/router/intent_router.py)
   - [core/composer/cross_domain.py](/home/y/llm/llm/core/composer/cross_domain.py)
   - [tests/goldens.json](/home/y/llm/llm/tests/goldens.json)

这样迁移风险最小，也最符合现在这套系统的演进方向。

---

## 11. 问题应该落到哪个 Skill

这一节用于后面做 router 精调时直接参考。

### 应该落到 `production_execution_skill` 的问题

关键词特征：

- 良率
- 不良
- 停机
- 实际产出
- 投料
- 线别
- 机台
- 达成率
- 昨天 / 今天 / 最近几天的实绩

典型问法：

- 最近 7 天哪些线别良率最低
- A1 产线昨天实际产出多少
- 停机时长最高的产线有哪些
- 不良数量异常的产品有哪些
- 今日排产与实际产出差异多大

### 应该落到 `planning_skill` 的问题

关键词特征：

- 月计划
- 周计划
- 周滚动
- 日排产
- 调整原因
- 计划版本
- 计划兑现
- 计划差异

典型问法：

- 本月计划量是多少
- 本周计划为什么调整
- 哪些产品周计划变化最大
- 月计划和周计划是否一致
- 排产结构按工厂怎么分布

### 应该落到 `inventory_supply_skill` 的问题

关键词特征：

- 库存
- 安全库存
- 在途
- 客户仓
- hub
- 齐套
- 缺料
- 覆盖
- 在制
- 备货

典型问法：

- 哪些产品低于安全库存
- 目前在途库存有多少
- 客户仓覆盖几天
- 哪些产品下周会缺料
- 在制和库存能不能支撑本周排产

### 应该落到 `demand_commit_skill` 的问题

关键词特征：

- forecast
- demand
- commit
- 承诺
- 需求覆盖
- 满足率
- 需求缺口
- 客户需求

典型问法：

- 未来三个月需求满足率是多少
- 哪些产品 commit 覆盖不足
- 某客户 forecast 和 commit 差多少
- 哪些产品需求缺口最大

### 应该落到 `sales_finance_skill` 的问题

关键词特征：

- 销量
- 营收
- 收入
- 毛利
- 单价
- 财务
- 经营结果
- 达成

典型问法：

- 哪些产品毛利率最低
- 本月收入最高的产品有哪些
- 不同技术族的营收结构如何
- 销量和计划差异多大

### 应该落到 `cross_domain` 的问题

同时出现两个或多个业务域信号，且用户在做组合判断、影响分析、支撑关系分析时，建议进入 `cross_domain`。

典型问法：

- 库存能否支撑下周排产
- 良率异常会不会影响交付承诺
- 需求增长是否有库存和计划保障
- 为什么这个产品毛利差，是执行问题还是计划问题

### 应该落到 `generic_skill` 的问题

适用场景：

- 问题不够清晰
- 路由置信度低
- 用户直接点名某张表
- 某个新业务域还没正式拆 skill

典型问法：

- 查询某张表最近 7 天数据
- 帮我看看这个表里有没有异常
- 按产品列一下最近记录

---

## 12. Router 后续建议怎么改

如果正式推进 5-skill，router 建议不再只返回：

- `production`
- `inventory`
- `cross_domain`
- `general`

而是升级成：

- `production_execution`
- `planning`
- `inventory_supply`
- `demand_commit`
- `sales_finance`
- `cross_domain`
- `general`

### 推荐的 router 关键词分组

#### `production_execution`
- 良率
- 不良
- 停机
- 产出
- 投料
- 实绩
- 线别
- 机台

#### `planning`
- 月计划
- 周计划
- 日排产
- 计划调整
- 调整原因
- 计划版本
- 兑现

#### `inventory_supply`
- 库存
- 安全库存
- 在途
- hub
- 客户仓
- 覆盖
- 缺料
- 齐套
- 备货

#### `demand_commit`
- forecast
- demand
- commit
- 承诺
- 满足率
- 缺口
- 客户需求

#### `sales_finance`
- 销量
- 营收
- 毛利
- 单价
- 财务
- 收入

### 共享过滤器建议

建议统一在 router 层抽出来，再下发给多个 skill：

- `recent_days`
- `latest`
- `date_from/date_to`
- `month/month_from/month_to`
- `factory_code`
- `line_code`
- `product_code`
- `customer_name`
- `tech_family`
- `application`
- `life_cycle`

---

## 13. 从当前代码迁移到 5-Skill 的实施顺序

这一节是最关键的执行顺序。

### Phase 1: 保持现有 3-skill 运行不动

目标：

- 不影响当前系统可用性
- 继续使用现有 `production_skill / inventory_skill / generic_skill`

### Phase 2: 拆出 `planning_skill`

原因：

- 它是最容易从当前 `production_skill` 中拆出来的
- `daily_schedule / weekly_rolling_plan / monthly_plan_approved` 本身边界相对清楚

建议动作：

1. 新建 `core/skills/planning/skill.py`
2. 把 `weekly_rolling_plan`、`monthly_plan_approved` 的规则迁过去
3. router 加 `planning` route
4. composer 开始支持 `planning + inventory` 组合

### Phase 3: 拆出 `demand_commit_skill`

原因：

- `v_demand` 和 `p_demand` 的业务语义非常集中
- 不适合继续留在宽泛的生产 skill 里

建议动作：

1. 新建 `core/skills/demand/skill.py`
2. router 增加 `forecast / demand / commit` 专门分支
3. composer 支持 `demand + planning`、`demand + inventory`

### Phase 4: 拆出 `sales_finance_skill`

原因：

- `sales_financial_perf` 本身就是经营结果表
- 跟生产执行的分析口径不同

建议动作：

1. 新建 `core/skills/sales/skill.py`
2. 把营收、毛利、销量问题从生产 skill 中迁出
3. composer 支持 `sales + planning`、`sales + production_execution`

### Phase 5: 收缩旧 `production_skill`

这一步完成后，原来的 `production_skill` 可以正式收缩成：

- 只保留生产执行问题
- 或者直接重命名成 `production_execution_skill`

---

## 14. 每个 Skill 需要改哪些代码

### 新增 `planning_skill` 时

至少会碰这些文件：

- `core/skills/planning/skill.py`
- `core/router/intent_router.py`
- `core/composer/cross_domain.py`
- `tests/goldens.json`

### 新增 `demand_commit_skill` 时

至少会碰这些文件：

- `core/skills/demand/skill.py`
- `core/router/intent_router.py`
- `core/composer/cross_domain.py`
- `tests/goldens.json`

### 新增 `sales_finance_skill` 时

至少会碰这些文件：

- `core/skills/sales/skill.py`
- `core/router/intent_router.py`
- `core/composer/cross_domain.py`
- `tests/goldens.json`

### 如果要进一步做精调

还会碰：

- [core/config/tables.json](/home/y/llm/llm/core/config/tables.json)
- [core/router/filter_extractor.py](/home/y/llm/llm/core/router/filter_extractor.py)
- [core/skills/prompting.py](/home/y/llm/llm/core/skills/prompting.py)
- [PRODUCTION_TUNING_TEMPLATE.md](/home/y/llm/llm/PRODUCTION_TUNING_TEMPLATE.md)

---

## 15. 推荐的目录形态

如果后面正式升级到 5-skill，建议目录大致变成：

```text
core/
├── skills/
│   ├── base.py
│   ├── prompting.py
│   ├── generic/
│   │   └── skill.py
│   ├── production/
│   │   └── skill.py
│   ├── planning/
│   │   └── skill.py
│   ├── inventory/
│   │   └── skill.py
│   ├── demand/
│   │   └── skill.py
│   └── sales/
│       └── skill.py
```

这样每个 skill 的边界和文件归属都比较明确。

---

## 16. 一句话结论

如果只是为了“先跑起来”，3-skill 足够。

如果是为了“长期稳定覆盖这 12 张表的大多数高质量问题”，推荐演进到：

- `production_execution_skill`
- `planning_skill`
- `inventory_supply_skill`
- `demand_commit_skill`
- `sales_finance_skill`
- `generic_skill`

这是当前这套库结构下，复杂度和可维护性比较平衡的一版方案。
