# 工作流层说明

这一层负责当前运行中的核心工作流能力，包括：

- 领域路由
- 歧义澄清
- 执行编排
- 跨域拆解与汇总
- 聊天历史整理
- 工作流执行入口

它会与 `backend/app/semantic`、`backend/app/skills`、`backend/app/execution`、`backend/app/config` 协同，组成完整的后端执行链路。

## 各模块职责

- `router.py`
  - 基于规则 + LLM fallback 的路由，产出单域、`cross_domain` 或 `legacy` 结果
- `disambiguation.py`
  - 在 route 已确定后判断是否还需要澄清表/口径；输出 `resolved / clarify / not_needed`
- `composer.py`
  - 跨域问题拆解与结果合并
- `orchestrator.py`
  - 技能分发、`legacy -> general` 兜底映射、澄清早停与最终结果汇总
- `executor.py`
  - 后台运行使用的异步工作流入口
- `history.py`
  - send / regenerate 场景下的聊天历史整理
- `state.py`
  - 工作流状态对象与序列化更新载荷

## 当前主链路

单域查询通常按以下顺序推进：

1. `route`
2. `check_guard`
3. `refine_filters`
4. `disambiguate`
5. `get_schema`
6. `write_sql`
7. `execute_sql`
8. `reflect_sql`（如需要）
9. `generate_answer`

如果 `disambiguate` 判定当前信息不足，会直接返回澄清问题，不继续进入 SQL 阶段。
