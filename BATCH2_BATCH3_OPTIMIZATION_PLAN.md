# Batch 2 & 3 Optimization Plan

目标：在现有 Batch 1 基础上，继续提升模型输出效率和准确度。

## 执行进展（2026-04-17）

1. [x] Batch 2.1 路由置信校准（负向关键词、top2 近似复核、置信拆解输出）
2. [x] Batch 2.2 SQL 候选重排（默认 2 候选，lint + 轻执行评分选优）
3. [x] Batch 2.3 回答证据绑定（空结果强制“未查到数据”，补充证据映射）
4. [x] Batch 3.1 查询缓存层（TTL 内存缓存首版，命中跳过工作流执行）
5. [x] Batch 3.2 评测闭环（`tests/eval_runner.py` + `tests/evals/thresholds.json` + `answer_cases.json`）
6. [x] Batch 3.3 可观测性面板（窗口统计 + 告警 + 历史趋势接口 + 前端趋势展示）
7. [x] Batch 3.3 Phase 1：节点耗时/失败率/缓存命中内存聚合 + `/api/admin/metrics` 查询接口
8. [x] Batch 3.3 Phase 2：`window_sec` 窗口统计（run/cache/route）+ 节点 `p95_ms/failure_rate` + 前端指标看板自动刷新
9. [x] Batch 3 收尾工具：`metrics_snapshot.py`、`generate_acceptance_report.py`、`tuning_advisor.py`
10. [x] Batch 3 收尾稳态化：`metrics_service` 单测补齐 + 评测运行产物忽略策略落地

### 2026-04-17 增补（面向 26B 混合模型）

1. [x] SQL 候选按需扩展：首条候选评分足够高时不再生成额外候选，降低 token 与时延。
2. [x] 跨域并发上限：新增 `CROSS_DOMAIN_MAX_PARALLEL`，避免大模型并发导致吞吐抖动。
3. [x] LLM 侧超时与重试：新增 `LLM_TIMEOUT_SECONDS` + `LLM_MAX_RETRIES`，降低瞬时失败率。

## 全局 KPI

1. 路由准确率：提升到 `>= 90%`
2. 首次 SQL 成功率（无需 reflect）：提升到 `>= 80%`
3. 最终回答可追溯率（结论可映射到 SQL 结果）：提升到 `>= 95%`
4. 跨域问题端到端延迟 p95：在 Batch 1 基础上再降 `15%+`

## Batch 2（提准优先）

周期：`1-2 周`

### 2.1 路由置信校准

范围：
1. `backend/app/workflow/router.py`

动作：
1. 为高混淆域增加负向关键词和冲突权重（如 `inventory` vs `demand`、`planning` vs `production`）。
2. 输出 route 时增加可解释因子：`positive_hits`、`negative_hits`、`confidence_breakdown`。
3. 当 top2 置信接近时，优先触发轻量 LLM 复核。

验收：
1. 路由离线集 top-1 准确率提升 `>= 8%`。
2. 错分集中在可解释边界问题，不出现大面积单域偏置。

### 2.2 SQL 候选重排

范围：
1. `backend/app/skills/base.py`
2. `backend/app/execution/sql_guard.py`
3. `backend/app/execution/sql_executor.py`

动作：
1. `write_sql` 阶段生成 `2-3` 个候选 SQL（低开销模式）。
2. 候选先过 lint，再做轻执行验证（limit 小样本），按评分选择最佳 SQL。
3. 仅当候选全失败时才进入 reflect。

验收：
1. 首次 SQL 成功率提升 `>= 12%`。
2. reflect 触发率下降 `>= 25%`。

### 2.3 回答证据绑定

范围：
1. `backend/app/presentation/answer_builder.py`
2. `backend/app/execution/prompts.py`

动作：
1. 在答案生成 prompt 增加“证据绑定”约束：每条关键结论必须对应返回结果字段/数值。
2. 当结果为空时强制返回“未查到数据”，禁止猜测性表达。
3. 输出结构统一为：结论 -> 关键数字 -> 风险/建议。

验收：
1. 回答可追溯率 `>= 95%`。
2. 人工抽检 hallucination 明显下降。

## Batch 3（稳定与持续优化）

周期：`1-2 周`

### 3.1 查询缓存层

范围：
1. `backend/app/services/chat_execution_service.py`
2. `backend/app/execution/sql_executor.py`
3. 新增 `backend/app/services/cache_service.py`（建议）

动作：
1. 建立 cache key：`normalized_question + filters + domain + schema_version`。
2. 对稳定查询优先读缓存，命中后跳过 SQL 执行与答案重生成。
3. 缓存 TTL 分层：短期热点短 TTL，静态口径长 TTL。

验收：
1. 热点查询端到端延迟下降 `>= 40%`。
2. 缓存命中率稳定在目标区间（按业务场景设阈值）。

### 3.2 评测闭环

范围：
1. `tests/`
2. `tests/eval_runner.py`
3. 新增 `tests/evals/`（建议）

动作：
1. 建立三层评测：`route`、`sql`、`answer`。
2. 每次规则或 prompt 变更自动触发离线评测。
3. 固化回归门槛，未达标不允许合并。

验收：
1. 评测覆盖核心高频问法。
2. 版本间质量波动可量化可追踪。

### 3.3 可观测性面板

范围：
1. `backend/app/logging_config.py`
2. `backend/app/services/thread_event_*`
3. 新增 metrics 聚合模块（建议）

动作：
1. 记录节点级指标：`router/guard/sql/reflect/answer` 的耗时、失败率、重试率、token 消耗。
2. 输出按 domain、query_type、user_segment 的质量视图。
3. 引入告警阈值：失败率、延迟突增、缓存异常。

验收：
1. 关键指标可在一个面板查看。
2. 异常可以在分钟级定位到节点与域。

## 风险与回滚

1. 候选 SQL 增多会推高 token 和执行成本。  
   处理：默认 `N=2`，通过配置开关动态调整。
2. 缓存可能引入陈旧数据。  
   处理：按业务域设 TTL，关键报表提供强制绕缓存开关。
3. 并行策略可能导致日志顺序混乱。  
   处理：统一 trace_id + node_id。

## 交付清单

1. 代码改造 PR（Batch 2）
2. 代码改造 PR（Batch 3）
3. 离线评测报告（每批次）
4. 上线观察报告（每批次 T+3 工作日）
