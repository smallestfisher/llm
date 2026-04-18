# Real-Issue Tuning Playbook

目标：基于真实用户问题，稳定提升路由准确率、SQL 成功率、答案可信度与端到端时延。

适用范围：
- 已经具备基础可用能力，开始进入线上迭代优化阶段。
- 不追求一次“大重构”，而是追求可回溯、可归因的小步快跑。

---

## 1. 调优原则

1. 先提准，再提速  
先压低错误率，再优化时延和成本。

2. 单轮只改 1-2 个变量  
一次改太多无法归因，回滚也困难。

3. 高频优先  
优先解决影响面最大的前 20% 问题。

4. 全程留痕  
每次调优都记录：输入问题、改动点、验证结果、回滚条件。

---

## 2. 一轮调优标准流程

### Step 0: 固定基线（Before）

先记录当前版本核心指标：
- `route_top1_accuracy`
- `first_sql_success_rate`
- `no_data_guard_rate`
- `answer_rule_case_pass_rate`
- 线上 `p95_run_ms`、失败率、缓存命中率

建议执行：

```bash
PYTHONPATH=. python3 tests/eval_runner.py --no-strict --max-cases 20 --case-timeout-sec 10
PYTHONPATH=. python3 tests/metrics_snapshot.py --output tests/evals/metrics_snapshot.json
python3 tests/generate_acceptance_report.py
```

### Step 1: 采样真实问题（20-50 条）

来源优先级：
1. 用户反馈“答非所问/错误答案”
2. 失败运行（`run.status=failed`）
3. 耗时异常（高延迟）

每条问题至少记录以下字段：
- `question`
- `actual_route`、`actual_skill`
- `sql_query`、`sql_error`
- `final_answer`
- `runtime_ms`
- `user_feedback`（可选）

### Step 2: 问题分桶

必须先分桶再改：

- `R` 路由错误：域/技能选错
- `S` SQL 问题：语法、字段、过滤、空结果、慢查询
- `A` 答案问题：结论与数据不一致、空结果乱答、表达不完整
- `P` 性能/稳定性：超时、重试、多域并发抖动

每桶按“频次 x 影响”排序，先拿 Top 5。

### Step 3: 根因归类（只选一个主因）

常见主因：
- 路由规则覆盖不足（同义词/负向词缺失）
- SQL 候选不足或候选扩展过度
- SQL 执行保护策略不匹配（`LIMIT`、预估计数等）
- 答案生成缺少证据绑定
- 并发和超时配置不匹配模型规模

### Step 4: 设计最小改动

改动优先顺序：
1. 配置参数（最快验证）
2. 路由规则 / prompt 文案
3. 执行策略逻辑
4. 结构性代码重构（最后手段）

### Step 5: 轻量验证（After）

先做冒烟，再做目标桶回归：

```bash
PYTHONPATH=. python3 tests/eval_runner.py --no-strict --max-cases 1 --case-timeout-sec 8
PYTHONPATH=. python3 tests/eval_runner.py --no-strict --max-cases 20 --case-timeout-sec 10
python3 -m unittest discover -s tests -p 'test_*.py'
```

### Step 6: 小流量观察

观察窗口建议：
- 至少 1 个业务日
- 重点看 `failed`、`p95_run_ms`、`alerts`、用户负反馈

### Step 7: 回滚判定

任一条件满足立即回滚：
- 失败率升高超过 `+3%`
- `p95_run_ms` 恶化超过 `+20%`
- 高价值问题正确率下降

---

## 3. 调优杠杆速查表

| 问题类型 | 优先调整 | 代码/配置位置 |
|---|---|---|
| 路由错误 | 负向词、冲突权重、路由模型 | `backend/app/workflow/router.py`、`LLM_MODEL_ROUTER` |
| SQL 首轮失败高 | 候选数、扩展阈值、探测 limit | `SQL_CANDIDATE_COUNT`、`SQL_CANDIDATE_EXPAND_SCORE`、`SQL_CANDIDATE_PROBE_LIMIT` |
| SQL 慢 | 并发上限、预估计数、自动截断 | `CROSS_DOMAIN_MAX_PARALLEL`、`SQL_ENABLE_PRECOUNT`、`SAMPLE_LIMIT` |
| 答案幻觉 | 证据绑定、空结果模板、答案模型 | `backend/app/presentation/answer_builder.py`、`LLM_MODEL_ANSWER` |
| 不稳定超时 | 请求超时、重试次数、缓存 | `LLM_TIMEOUT_SECONDS`、`LLM_MAX_RETRIES`、`QUERY_CACHE_*` |

---

## 4. 上下文专项调优（新增）

当前建议先不做复杂追问分流，统一保持完整查询流程；优化重点放在“上下文控制”。

建议灰度顺序：
1. 默认关闭窗口压缩：`CHAT_HISTORY_WINDOW_TURNS=0`
2. 小流量开启窗口裁剪：例如 `CHAT_HISTORY_WINDOW_TURNS=6`
3. 再开启摘要：`CHAT_HISTORY_SUMMARY_ENABLED=1`
4. 根据准确率与时延继续调 `CHAT_HISTORY_SUMMARY_*`

关键开关：

| 变量 | 作用 | 建议 |
|---|---|---|
| `REGENERATE_BYPASS_CACHE` | regenerate 是否绕过缓存 | 质量优先开 `1`，成本优先保 `0` |
| `CHAT_HISTORY_WINDOW_TURNS` | 历史窗口轮数 | 先 `0`，再灰度到 `4-8` |
| `CHAT_HISTORY_SUMMARY_ENABLED` | 历史摘要开关 | 与窗口配套 |
| `CHAT_HISTORY_SUMMARY_MAX_ITEMS` | 摘要包含的历史问答条数上限 | `4-8` |
| `CHAT_HISTORY_SUMMARY_ITEM_MAX_CHARS` | 摘要单条字符上限 | `100-200` |

上线后重点观察：
- 长对话场景的失败率和时延
- 回答连贯性（是否因裁剪丢关键信息）
- token 消耗变化（长会话是否明显下降）

---

## 5. 三个完整示例

### 示例 A：路由错到 `demand`，实际应走 `inventory`

现象：
- 用户问题：`“查询 Samsung 在途库存”`
- 系统频繁路由到 `demand`
- SQL 与库存表无关，答案偏差

分析：
- `inventory` 与 `demand` 语义重叠词较多
- “在途”权重不足，冲突消解不够

改动（最小）：
1. 在 router 增加 `inventory` 正向词：`在途/库存可用/库龄`
2. 在 `demand` 增加负向抑制：遇到 `在途库存` 时减分
3. 保持模型不变，只改规则

验证：
- 选 10 条同类问题回归：路由命中率从 `60% -> 90%`
- SQL 成功率同步提升

复盘：
- 先改规则不改模型，收益高且风险低

### 示例 B：SQL 首轮成功率低，Reflect 压力大

现象：
- `first_sql_success_rate` 只有 `68%`
- `reflect` 触发过多，整体时延上升

分析：
- 候选只生成 1 条时，经常卡在字段别名或过滤条件细节
- 候选扩展策略过保守

改动（最小）：
1. `SQL_CANDIDATE_COUNT=2`
2. `SQL_CANDIDATE_EXPAND_SCORE=90`（保留按需扩展）
3. `SQL_CANDIDATE_PROBE_LIMIT=1`（轻探测降低成本）

验证：
- 20 条目标样本：`first_sql_success_rate` 从 `68% -> 82%`
- p95 小幅上升可接受（+6%）

复盘：
- “2 候选 + 轻探测”常是 26B 场景的性价比甜点

### 示例 C：空结果时答案“乱猜”

现象：
- 问题：`“查询 A1 产线 2026-04-01 的报废率”`
- SQL 返回空结果
- 最终回答却给出具体百分比

分析：
- 答案阶段未严格绑定结果证据
- 空结果保护语不够强制

改动（最小）：
1. 强化 answer prompt：空结果必须输出“未查到数据”
2. 在 `answer_builder` 中保留空结果短路逻辑，禁止猜测性语句
3. 不改 SQL 逻辑，先控制回答可信度

验证：
- 20 条空结果样本：`no_data_guard_rate` 从 `85% -> 100%`
- 用户“胡乱回答”反馈明显下降

复盘：
- 在真实业务中，保守正确优先于“看起来聪明但不可信”

## 6. 建议的调优记录模板

可直接复制到每轮调优记录：

```md
# Round <日期-编号>

## 目标
- 例如：提升 SQL 首轮成功率，目标 >= 80%

## 基线
- route_top1_accuracy:
- first_sql_success_rate:
- no_data_guard_rate:
- p95_run_ms:

## 样本
- 总样本数：
- R/S/A/P 分布：
- Top 5 高频 case：

## 改动
1. 改动项：
2. 影响范围：
3. 回滚方式：

## 结果
- 指标对比（Before vs After）：
- 风险与副作用：

## 结论
- 保留/继续观察/回滚
```

---

## 7. 常见反模式（避免）

1. 同时改模型、prompt、规则、参数  
结果无法归因。

2. 只看离线不看线上  
离线准确率提升不代表线上稳定性提升。

3. 只看平均值不看长尾  
平均时延变好，但 p95/p99 变差会直接影响体验。

4. 不做回滚预案  
出现退化时恢复慢，影响面扩大。

---

## 8. 推荐起步节奏（两周）

第 1 周：
1. 建立真实问题样本池
2. 完成第一轮 R/S 高影响修复
3. 小流量观察与回滚机制演练

第 2 周：
1. 持续两轮小步优化
2. 固化阈值与验收标准
3. 输出阶段复盘（收益、风险、下一轮目标）

---

执行重点：`真实问题分桶 -> 高频优先 -> 单轮小改 -> 快速验证 -> 可回滚`。  
这是当前架构下最稳、性价比最高的调优路径。
