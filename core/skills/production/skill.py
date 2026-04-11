from core.skills.base import BaseSkill


class ProductionSkill(BaseSkill):
    domain = "production"
    skill_name = "production_skill"
    node_name = "production_skill"
    domain_label = "生产执行"
    guard_scope = "生产实绩、投入、产出、报废、不良和执行结果分析"
    focus_areas = (
        "只关注生产实际发生了什么，包括投入、产出、报废和不良",
        "优先回答某工厂、某产品、某日期范围内的执行结果问题",
        "只有在用户明确要求产品维度补充说明时，才关联产品属性或映射表",
    )
    field_conventions = (
        "production_actuals 是生产执行唯一主表，act_type 区分 IN/OUT/SCRAP，不要虚构 line_code、yield_rate、downtime_hours 等不存在字段",
        "production_actuals 的投入优先看 GLS_qty，产出优先看 Panel_qty，报废优先看 defect_qty",
        "production_actuals 的核心维度是 work_date、FACTORY、product_ID、act_type",
        "生产执行域只负责实际结果，不负责月计划、周计划、需求承诺、库存覆盖或销售财务问题",
    )
    sql_rules = (
        "涉及投入、产出、报废或实绩时优先检查 production_actuals",
        "如果问题只问工厂、产品或日期范围，请优先使用 FACTORY、product_ID、work_date 过滤，不要无条件扫全表",
        "act_type 如果未明确指定，可根据问题含义推断 IN/OUT/SCRAP，但不要同时混淆多个口径",
        "除非用户要求明细，否则优先按时间、工厂或产品聚合",
        "不要为了回答计划达成、库存支撑或需求缺口而跨到其他业务表；这类问题应由跨域编排处理",
    )
    answer_rules = (
        "先给出投入、产出或报废的核心结论",
        "若有报废或异常指标，优先指出波动最大的工厂或产品",
        "明细结果只提示查看表格，不要在回答中重复铺开",
    )
    default_tables = ("production_actuals",)
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("不良", "报废", "scrap", "实绩", "产出", "投入"), "production_actuals"),
    )
