from app.skills.base import BaseSkill


class DemandSkill(BaseSkill):
    domain = "demand"
    skill_name = "demand_skill"
    node_name = "demand_skill"
    domain_label = "需求与承诺"
    guard_scope = "V版需求、P版需求、forecast、commit、客户需求覆盖和需求缺口分析"
    focus_areas = (
        "关注客户需求、V版预测、P版承诺和需求覆盖关系",
        "优先回答版本需求、客户需求、需求缺口和承诺满足问题",
        "必要时结合产品属性和产品映射解释产品维度差异",
    )
    field_conventions = (
        "v_demand 和 p_demand 都是横向月度需求表，MONTH 是起始月，NEXT_REQUIREMENT/LAST_REQUIREMENT/MONTH4~MONTH7 是后续月份",
        "v_demand 更适合回答 forecast、原始客户需求、V版问题",
        "p_demand 更适合回答 commit、承诺需求、P版问题",
        "两个表都使用 PM_VERSION、FGCODE、CUSTOMER 等业务字段，不要误写 product_code 或 commit_month",
        "用户说“第二个月/第三个月”时，通常应映射到 NEXT_REQUIREMENT/LAST_REQUIREMENT，不要把“未来第三个月”当作 MONTH 的字面值",
        "用户说“V版”或“P版”时，通常是在指表口径，不等于 PM_VERSION 的具体值；只有出现 2026W03 这类版本号时才过滤 PM_VERSION",
        "如果需要按产品关联，优先通过 FGCODE 关联 product_attributes.product_ID 或 product_mapping.FGCODE",
    )
    sql_rules = (
        "涉及 V版、forecast、原始需求或客户预测时优先检查 v_demand",
        "涉及 P版、commit、承诺需求或承接量时优先检查 p_demand",
        "当用户问未来多个月份需求时，要正确使用横表结构，不要把 NEXT_REQUIREMENT/LAST_REQUIREMENT 当作独立维表",
        "如果原问题是跨域覆盖或影响分析，demand 域只返回需求/承诺侧基础量，不要在本域 SQL 中替代计划或库存做最终判断",
        "如果问题包含版本号、客户、月份或产品，请优先在 SQL 中准确过滤",
        "除非用户明确要求明细，否则优先按版本、客户、产品或月份聚合",
    )
    answer_rules = (
        "先说明需求规模、承诺规模和缺口方向",
        "若问题涉及多个月份，明确说明是起始月还是后续月份口径",
        "若问题涉及版本，优先指出结论对应的 PM_VERSION",
    )
    default_tables = (
        "v_demand",
        "p_demand",
        "product_attributes",
        "product_mapping",
    )
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("v版", "forecast", "原始需求", "客户需求"), "v_demand"),
        (("p版", "commit", "承诺", "承诺需求"), "p_demand"),
        (("需求", "覆盖", "缺口"), "p_demand"),
    )
