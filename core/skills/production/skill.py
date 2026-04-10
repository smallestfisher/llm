from core.skills.base import BaseSkill


class ProductionSkill(BaseSkill):
    domain = "production"
    skill_name = "production_skill"
    node_name = "production_skill"
    domain_label = "生产与计划"
    guard_scope = "生产实绩、排产、计划、需求承诺、良率、不良、停机、在制和产销相关分析"
    focus_areas = (
        "关注产线产出、良率、不良、停机与计划达成",
        "处理月计划、周计划、日排产与实际执行偏差",
        "必要时关联产品属性与产品工厂映射信息",
    )
    sql_rules = (
        "涉及产线、良率、不良、停机时优先检查 production_actuals",
        "涉及周计划或调整原因时优先检查 weekly_rolling_plan",
        "涉及月计划或计划基准时优先检查 monthly_plan_approved",
        "涉及需求承诺或 forecast/commit 时优先检查 p_demand 与 v_demand",
        "除非用户要求明细，否则优先按时间、工厂、产线或产品聚合",
    )
    answer_rules = (
        "先给出计划达成、产出或异常的核心结论",
        "若有良率、不良、停机等异常指标，优先指出波动最大的对象",
        "明细结果只提示查看表格，不要在回答中重复铺开",
    )
    default_tables = (
        "daily_schedule",
        "production_actuals",
        "weekly_rolling_plan",
        "monthly_plan_approved",
        "product_attributes",
        "product_mapping",
    )
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("良率", "不良", "停机", "实绩", "产出"), "production_actuals"),
        (("周计划", "周排产", "调整原因"), "weekly_rolling_plan"),
        (("月计划", "月度计划"), "monthly_plan_approved"),
        (("需求", "forecast", "commit"), "p_demand"),
        (("在制", "wip", "批次", "工序"), "work_in_progress"),
        (("排产", "日计划", "班次"), "daily_schedule"),
    )
