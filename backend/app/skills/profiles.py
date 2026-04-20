from __future__ import annotations

from dataclasses import dataclass

from app.semantic.schema_registry import load_tables


@dataclass(frozen=True)
class SkillProfile:
    domain_label: str
    guard_scope: str
    focus_areas: tuple[str, ...]
    field_conventions: tuple[str, ...]
    sql_rules: tuple[str, ...]
    answer_rules: tuple[str, ...]
    default_tables: tuple[str, ...]
    helper_tables: tuple[str, ...]
    keyword_table_map: tuple[tuple[tuple[str, ...], str], ...]


COMMON_CONCISE_ANSWER_RULES = (
    "输出 3 段：结论(1-2句) -> 关键数字(<=3条) -> 风险/建议(可选1条)",
    "短句、去重，不铺陈大段明细",
)


SKILL_PROFILES: dict[str, SkillProfile] = {
    "production": SkillProfile(
        domain_label="生产执行",
        guard_scope="生产实绩、投入、产出、报废、不良分析",
        focus_areas=(
            "仅回答生产实际结果",
            "优先按工厂/产品/日期输出",
        ),
        field_conventions=(
            "production_actuals 主表，act_type=IN/OUT/SCRAP",
            "投入看 GLS_qty，产出看 Panel_qty，报废看 defect_qty",
            "核心维度：work_date/FACTORY/product_ID/act_type",
        ),
        sql_rules=(
            "实绩/投入/产出/报废优先 production_actuals",
            "默认先聚合，用户要明细再下钻",
            "本域不处理计划/库存/需求/销售口径",
        ),
        answer_rules=(
            "先给总量，再点名波动最大工厂或产品",
            *COMMON_CONCISE_ANSWER_RULES,
        ),
        default_tables=("production_actuals",),
        helper_tables=("product_attributes", "product_mapping"),
        keyword_table_map=(
            (("不良", "报废", "scrap", "实绩", "产出", "投入"), "production_actuals"),
        ),
    ),
    "planning": SkillProfile(
        domain_label="计划与排产",
        guard_scope="月计划、周滚、日排产、版本与偏差分析",
        focus_areas=(
            "明确日/周/月口径与版本",
            "优先回答排产量、计划量、版本差异",
        ),
        field_conventions=(
            "daily_PLAN: PLAN_date/factory_code/product_ID/target_qty",
            "weekly_rolling_plan: PM_VERSION/plan_date/factory/product_ID/plan_qty",
            "monthly_plan_approved: plan_month/PLAN_date 与投入产出指标",
        ),
        sql_rules=(
            "日计划用 daily_PLAN，周滚用 weekly_rolling_plan，月计划用 monthly_plan_approved",
            "默认先按时间/工厂/产品聚合",
            "本域不下结论实际产出或库存覆盖",
        ),
        answer_rules=(
            "先说明口径(日/周/月)+版本，再给结论",
            *COMMON_CONCISE_ANSWER_RULES,
        ),
        default_tables=(
            "daily_PLAN",
            "weekly_rolling_plan",
            "monthly_plan_approved",
            "product_attributes",
            "product_mapping",
        ),
        helper_tables=("product_attributes", "product_mapping"),
        keyword_table_map=(
            (("周计划", "周排产", "周滚", "滚动计划", "版本"), "weekly_rolling_plan"),
            (("月计划", "月度计划", "审批版"), "monthly_plan_approved"),
            (("排产", "日计划", "日排产"), "daily_PLAN"),
        ),
    ),
    "inventory": SkillProfile(
        domain_label="库存与供应保障",
        guard_scope="库存、在途、客户仓、库龄、齐套与保障分析",
        focus_areas=(
            "关注 TTL/HOLD/OMS 与覆盖风险",
            "区分快照库存(daily)与月度库龄(OMS)",
        ),
        field_conventions=(
            "daily_inventory: TTL_Qty/HOLD_Qty/factory_code/ERP_FACTORY/ERP_LOCATION",
            "oms_inventory: glass_qty/panel_qty/ONE_AGE_panel_qty~EUGHT_AGE_panel_qty",
            "仅输出库存事实，不替代计划/需求结论",
        ),
        sql_rules=(
            "TTL/HOLD/库位用 daily_inventory；OMS/客户仓/库龄用 oms_inventory",
            "默认先聚合并标风险点，用户要明细再下钻",
            "跨域仅给库存基线，不做业务裁决",
        ),
        answer_rules=(
            "先判断是否充足，再给缺口/老化风险",
            *COMMON_CONCISE_ANSWER_RULES,
        ),
        default_tables=("daily_inventory", "oms_inventory"),
        helper_tables=("product_attributes", "product_mapping"),
        keyword_table_map=(
            (("在途", "hub", "客户仓", "oms", "库龄", "期初"), "oms_inventory"),
            (("ttl", "hold", "checkincode", "库位", "erp"), "daily_inventory"),
            (("库存", "安全库存", "可用库存", "仓库", "齐套", "支撑", "缺料"), "daily_inventory"),
        ),
    ),
    "demand": SkillProfile(
        domain_label="需求与承诺",
        guard_scope="V版、P版、forecast、commit 与缺口分析",
        focus_areas=(
            "关注 forecast/commit 与版本口径",
            "优先回答需求规模、承诺规模、缺口",
        ),
        field_conventions=(
            "V版优先v_demand;P版/commit 优先 p_demand",
            "用户给完整版本号时按PM_VERSION精确过滤",
            "用户只给月粒度时间时，不要臆造某一周PM_VERSION,必须按横表月份口径统计",
        ),
        sql_rules=(
            "多月查询需正确展开横表月份字段",
            "默认先按版本/客户/产品/月份聚合",
            "跨域仅给需求事实，不替代库存/计划结论",
        ),
        answer_rules=(
            "先说需求/承诺/缺口方向，并明确月份口径",
            *COMMON_CONCISE_ANSWER_RULES,
        ),
        default_tables=("v_demand", "p_demand", "product_attributes", "product_mapping"),
        helper_tables=("product_attributes", "product_mapping"),
        keyword_table_map=(
            (("v版", "forecast", "原始需求", "客户需求"), "v_demand"),
            (("p版", "commit", "承诺", "承诺需求"), "p_demand"),
            (("需求", "覆盖", "缺口"), "p_demand"),
        ),
    ),
    "sales": SkillProfile(
        domain_label="销售与财务",
        guard_scope="销售业绩、财务业绩、客户表现分析",
        focus_areas=(
            "关注 sales_qty 与 FINANCIAL_qty",
            "优先回答客户/SBU/BU/产品表现",
        ),
        field_conventions=(
            "sales_financial_perf: report_month/SBU_DESC/BU_DESC/CUSTOMER/FGCODE/sales_qty/FINANCIAL_qty",
            "本表不含 revenue/gross_margin 等口径",
            "销售看 sales_qty，财务看 FINANCIAL_qty",
        ),
        sql_rules=(
            "销售问题优先 sales_qty；财务问题优先 FINANCIAL_qty",
            "非必要不做维表关联",
            "默认先按月份/客户/SBU/BU/产品聚合",
        ),
        answer_rules=(
            "先给销售或财务结论，并标明口径",
            *COMMON_CONCISE_ANSWER_RULES,
        ),
        default_tables=("sales_financial_perf",),
        helper_tables=("product_attributes", "product_mapping"),
        keyword_table_map=(
            (("财务", "财务业绩", "经营结果"), "sales_financial_perf"),
            (("销售", "销量", "出货"), "sales_financial_perf"),
        ),
    ),
    "general": SkillProfile(
        domain_label="通用企业数据",
        guard_scope="生产、库存、排产、需求、销售、财务相关查询",
        focus_areas=(
            "在可用表范围内完成检索与统计",
            "优先用用户给定时间和对象收敛范围",
        ),
        field_conventions=(),
        sql_rules=(
            "优先单表；必要时再关联",
            "避免无界返回，必要时 LIMIT",
        ),
        answer_rules=(
            "先说明是否命中数据及规模",
            *COMMON_CONCISE_ANSWER_RULES,
        ),
        default_tables=tuple(load_tables().keys()),
        helper_tables=(),
        keyword_table_map=(),
    ),
}
