from app.skills.base import BaseSkill


class PlanningSkill(BaseSkill):
    domain = "planning"
    skill_name = "planning_skill"
    node_name = "planning_skill"
    domain_label = "计划与排产"
    guard_scope = "月计划、周滚计划、日排产、计划版本、计划兑现和计划偏差分析"
    focus_areas = (
        "关注月计划、周滚计划、日排产之间的承接关系",
        "优先回答计划版本、计划数量、工厂排产和计划兑现问题",
        "必要时结合产品属性和产品映射补充产品维度解释",
    )
    field_conventions = (
        "daily_PLAN 只有 PLAN_date、factory_code、product_ID、target_qty，适合回答日排产和日计划问题",
        "weekly_rolling_plan 带 PM_VERSION、plan_date、factory、product_ID、plan_qty，适合回答版本化周滚计划问题",
        "monthly_plan_approved 同时有 plan_month 和 PLAN_date，并区分投入/产出的 glass 与 panel 指标",
        "planning 域只负责计划目标，不负责实际达成；实际投入/产出必须来自 production_actuals，不要把 daily_PLAN 当实际表",
        "月计划问题优先使用 monthly_plan_approved，周计划问题优先使用 weekly_rolling_plan，日排产问题优先使用 daily_PLAN",
    )
    sql_rules = (
        "涉及日排产、日计划、每日投入目标时优先检查 daily_PLAN",
        "涉及周计划、周滚、计划版本或版本比较时优先检查 weekly_rolling_plan",
        "涉及月计划、审批版计划、月度投入/产出时优先检查 monthly_plan_approved",
        "如果原问题是跨域比较、覆盖或差异分析，planning 域只返回计划侧基础指标，不要在本域 SQL 中拼接实际/销售/库存/需求口径",
        "daily_PLAN 只有 target_qty，不存在 actual_out_glass_qty、target_out_panel_qty、target_IN_panel_qty 等字段",
        "如果问题包含月份，优先使用 plan_month 或 PLAN_date 过滤；如果包含版本，优先使用 PM_VERSION 过滤",
        "除非用户明确要求明细，否则优先按工厂、产品、日期或月份聚合",
    )
    answer_rules = (
        "先给出计划量、排产量、计划偏差或版本差异的核心结论",
        "如果同时存在日/周/月计划口径，明确指出结果基于哪一层口径",
        "明细结果只提示查看表格，不要在回答中铺开大段数据",
    )
    default_tables = (
        "daily_PLAN",
        "weekly_rolling_plan",
        "monthly_plan_approved",
        "product_attributes",
        "product_mapping",
    )
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("周计划", "周排产", "周滚", "滚动计划", "版本"), "weekly_rolling_plan"),
        (("月计划", "月度计划", "审批版"), "monthly_plan_approved"),
        (("排产", "日计划", "日排产"), "daily_PLAN"),
    )
