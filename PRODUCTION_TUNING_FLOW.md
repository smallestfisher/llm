# 生产库字段精调流程

这份文档描述的是：

当你已经拿到正式生产库字段后，应该按什么顺序把当前系统从“能跑”继续调到“更准、更稳、更贴业务”。

它不是字段模板，而是执行流程。

配套模板见：

- [PRODUCTION_TUNING_TEMPLATE.md](/home/y/llm/llm/PRODUCTION_TUNING_TEMPLATE.md)

## 1. 目标

生产库字段精调的目标不是改大架构，而是把当前这套已经稳定的：

- `router`
- `skills`
- `composer`
- `orchestrator`
- `sql harden / lint`

继续对齐到正式生产数据库的真实字段、真实口径和真实问法。

最终目标：

1. 路由更准
2. 首发 SQL 更准
3. 跨域结果更可靠
4. 业务口径更贴近实际使用
5. 回归样例更贴近真实业务问题

## 2. 总原则

执行顺序固定为：

1. 先确认真实表和字段
2. 先改 schema/config
3. 再改 skill 边界和 SQL 规则
4. 再改 router / filter / lexicon
5. 再改 SQL 保护链
6. 最后补回归测试

不要反过来先靠 prompt 猜字段。

## 3. 推荐执行阶段

### Phase 0: 冻结当前基线

目的：

- 保证你知道“改之前系统是什么状态”

动作：

1. 跑一遍静态测试
2. 跑一遍 live regression
3. 记录当前通过率
4. 保留当前 `tests/goldens.json`

建议命令：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall core tests
PYTHONPATH=. python3 tests/eval_runner.py
```

交付物：

- 当前通过率
- 当前已知误差点

### Phase 1: 表结构确认

目的：

- 把“真实字段是什么”确认清楚

动作：

1. 按表确认字段名、主键、时间字段、月份字段、版本字段
2. 确认关联关系
3. 确认哪些字段只是显示字段，哪些字段可以筛选、分组、聚合
4. 确认是否存在带空格列名、保留字列名、视图字段

应更新：

- [core/config/tables.json](/home/y/llm/llm/core/config/tables.json)

判断标准：

- `tables.json` 已经能独立描述真实 schema
- 不再依赖“口头约定”

### Phase 2: 业务口径确认

目的：

- 把“字段有了，但业务上怎么解释”确认清楚

动作：

按 skill 分别确认：

#### `production`

- 实际投入看哪个字段
- 实际产出看哪个字段
- 报废 / 不良怎么定义
- `act_type` 的真实枚举值是什么

#### `planning`

- `daily_PLAN.target_qty` 到底是投入还是产出
- `weekly_rolling_plan.plan_qty` 的业务口径
- `monthly_plan_approved` 四个 target 字段分别代表什么

#### `inventory`

- TTL / Hold 的业务定义
- OMS 中客户仓 / hub / 在途怎么判断
- 库龄桶是否固定

#### `demand`

- V版 / P版是否只是表口径
- `MONTH` / `NEXT_REQUIREMENT` / `LAST_REQUIREMENT` 怎么映射自然语言“第二个月/第三个月”

#### `sales`

- `sales_qty` 和 `FINANCIAL_qty` 代表什么
- `report_month` 是自然月还是结算月

交付物：

- 每个 skill 的字段口径清单

### Phase 3: Skill 精调

目的：

- 让每个 skill 只做自己的事，并且按真实字段写 SQL

动作：

逐个更新：

- [core/skills/production/skill.py](/home/y/llm/llm/core/skills/production/skill.py)
- [core/skills/planning/skill.py](/home/y/llm/llm/core/skills/planning/skill.py)
- [core/skills/inventory/skill.py](/home/y/llm/llm/core/skills/inventory/skill.py)
- [core/skills/demand/skill.py](/home/y/llm/llm/core/skills/demand/skill.py)
- [core/skills/sales/skill.py](/home/y/llm/llm/core/skills/sales/skill.py)

重点改：

1. `field_conventions`
2. `sql_rules`
3. `default_tables`
4. `keyword_table_map`

判断标准：

- skill 不再跨域脑补字段
- 首发 SQL 更贴真实字段

### Phase 4: Router / Filter / Lexicon 精调

目的：

- 让真实业务问法能更稳定地路到正确 skill

动作：

更新：

- [core/router/intent_router.py](/home/y/llm/llm/core/router/intent_router.py)
- [core/router/filter_extractor.py](/home/y/llm/llm/core/router/filter_extractor.py)
- [core/config/lexicon.json](/home/y/llm/llm/core/config/lexicon.json)
- [core/config/heuristics.json](/home/y/llm/llm/core/config/heuristics.json)

重点补：

- 工厂黑话
- 版本格式
- 客户简称
- 业务口头表达
- 相对时间表达

判断标准：

- 真实问法不需要“改写后才识别”

### Phase 5: SQL 保护链精调

目的：

- 让错误 SQL 在执行前被修正或拦住

动作：

更新：

- [core/runtime/skill_runtime.py](/home/y/llm/llm/core/runtime/skill_runtime.py)

关注：

1. 伪字段别名
2. 伪时间占位
3. `SELECT *`
4. 缺失版本/时间过滤
5. 占位字面值
6. 不必要的 JOIN
7. 带空格列名

判断标准：

- 首发 SQL 即使不完美，也尽量不直接报错
- 常见错误能自动被硬化或 lint 拦住

### Phase 6: 跨域精调

目的：

- 让跨域问题按“单域事实 + 汇总”稳定输出

动作：

重点看：

- [core/composer/cross_domain.py](/home/y/llm/llm/core/composer/cross_domain.py)
- [core/workflow/orchestrator.py](/home/y/llm/llm/core/workflow/orchestrator.py)

关注：

- 子任务问题是否收束
- 哪些组合最常见
- 哪些组合需要更严格的执行顺序

典型组合：

- `inventory + planning`
- `demand + planning`
- `production + planning`
- `demand + inventory`
- `production + sales`
- `planning + sales`

判断标准：

- 跨域 skill 不再互相脑补字段

### Phase 7: 回归测试补齐

目的：

- 让调优结果可验证，而不是只靠手工问几句

动作：

更新：

- [tests/goldens.json](/home/y/llm/llm/tests/goldens.json)
- [tests/eval_runner.py](/home/y/llm/llm/tests/eval_runner.py)
- `tests/test_*.py`

每个 skill 至少补：

- 典型单域问题
- 容易歧义的问题
- 跨域组合问题
- 黑话 / 缩写问题
- 时间 / 版本问题

判断标准：

- goldens 不再只是样板句
- 能覆盖真实业务问法

## 4. 推荐节奏

不要一次把所有表全部调完。

推荐顺序：

1. `planning`
2. `inventory`
3. `demand`
4. `production`
5. `sales`

原因：

- `planning` 和 `inventory` 最容易牵动跨域
- `demand` 紧跟其后
- `production` 和 `sales` 边界相对清楚

## 5. 每轮精调的标准动作

每做完一轮，都执行：

1. 改代码
2. 跑静态测试
3. 跑 live regression
4. 看失败题
5. 只修高价值失败模式
6. 再回归

建议不要在一轮里同时：

- 改 schema
- 改 5 个 skill
- 改所有测试

这样很难定位问题来源。

## 6. 推荐交付物

每一轮精调建议都留下这些东西：

1. 本轮变更范围
2. 修改了哪些表/字段认知
3. 修改了哪些 skill
4. 修改了哪些保护规则
5. 回归通过率
6. 剩余未解决问题

## 7. 结束条件

一轮精调可以认为完成，当同时满足：

- 目标表结构已对齐
- 目标 skill 已收口
- 静态测试通过
- live regression 通过
- 新增规则不再明显提升质量

到这时就不应该继续堆运行时规则了，而应该转向：

- 增加真实问题集
- 做首发 SQL 命中率统计
- 做生产库监控与观察

## 8. 配套文档

- [README.md](/home/y/llm/llm/README.md)
- [PROJECT_OVERVIEW.md](/home/y/llm/llm/PROJECT_OVERVIEW.md)
- [FIVE_SKILL_MAPPING.md](/home/y/llm/llm/FIVE_SKILL_MAPPING.md)
- [PRODUCTION_TUNING_TEMPLATE.md](/home/y/llm/llm/PRODUCTION_TUNING_TEMPLATE.md)

这四份文档分别负责：

- 项目入口
- 当前架构
- 当前技能映射
- 生产精调模板

本文件负责：

- 生产精调的执行流程
