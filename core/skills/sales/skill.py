from core.skills.base import BaseSkill


class SalesSkill(BaseSkill):
    domain = "sales"
    skill_name = "sales_skill"
    node_name = "sales_skill"
    domain_label = "销售与财务"
    guard_scope = "销售业绩、财务业绩、客户销售表现和经营结果分析"
    focus_areas = (
        "关注 sales_qty 和 FINANCIAL_qty 两类经营结果指标",
        "优先回答客户、SBU、BU、产品维度的销售和财务表现",
        "必要时结合产品属性和产品映射补充维度解释",
    )
    field_conventions = (
        "sales_financial_perf 只有 report_month、SBU_DESC、BU_DESC、CUSTOMER、FGCODE、sales_qty、FINANCIAL_qty",
        "当前表没有单价、营收、毛利率字段，不要虚构 revenue、gross_margin 等不存在字段",
        "销售问题优先看 sales_qty，财务业绩问题优先看 FINANCIAL_qty",
        "如果按产品关联，优先用 FGCODE 对 product_attributes.product_ID 或 product_mapping.FGCODE",
        "销售财务域不直接承担计划达成分析；计划对比应走销售与计划跨域编排",
    )
    sql_rules = (
        "涉及销售业绩、销量、出货时优先检查 sales_financial_perf.sales_qty",
        "涉及财务业绩、经营结果时优先检查 sales_financial_perf.FINANCIAL_qty",
        "如果原问题是跨域比较，sales 域只返回销量/财务侧基础事实，不要虚构 sales_actual 或把 sales_qty 映射到其他维表",
        "除非有明确业务过滤，不要无意义联接 product_attributes 或 product_mapping，以免引入歧义字段",
        "如果问题包含月份、客户、SBU、BU 或产品，请优先在 SQL 中准确过滤",
        "除非用户明确要求明细，否则优先按 report_month、CUSTOMER、SBU_DESC、BU_DESC 或 FGCODE 聚合",
    )
    answer_rules = (
        "先给出销售或财务业绩的核心结论",
        "如果同时涉及销售和财务口径，明确区分 sales_qty 与 FINANCIAL_qty",
        "避免使用毛利率、营收等当前表并不存在的财务口径",
    )
    default_tables = ("sales_financial_perf",)
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("财务", "财务业绩", "经营结果"), "sales_financial_perf"),
        (("销售", "销量", "出货"), "sales_financial_perf"),
    )
