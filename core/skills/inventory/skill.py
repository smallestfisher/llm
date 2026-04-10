from core.skills.base import BaseSkill


class InventorySkill(BaseSkill):
    domain = "inventory"
    skill_name = "inventory_skill"
    node_name = "inventory_skill"
    domain_label = "库存与供应保障"
    guard_scope = "库存、在途、客户仓、安全库存、齐套、备货和供应保障分析"
    focus_areas = (
        "关注可用库存、安全库存、在途与客户侧库存覆盖",
        "处理库存对排产、交付与缺料风险的影响",
        "必要时结合在制与排产信息评估供应保障",
    )
    sql_rules = (
        "涉及库存、安全库存或仓库时优先检查 daily_inventory",
        "涉及在途、客户仓、hub 或 OMS 时优先检查 oms_inventory",
        "涉及齐套、支撑排产或缺料风险时可结合 daily_schedule 与 work_in_progress",
        "除非用户明确要求全部明细，否则优先输出聚合或风险聚焦结果",
    )
    answer_rules = (
        "先说明库存是否充足，以及是否存在缺口或风险",
        "若涉及在途或客户仓，优先说明覆盖情况",
        "若结果为空，明确说明当前条件下未发现库存异常或相关记录",
    )
    default_tables = (
        "daily_inventory",
        "oms_inventory",
        "work_in_progress",
        "daily_schedule",
        "product_attributes",
        "product_mapping",
    )
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("在途", "hub", "客户仓", "oms"), "oms_inventory"),
        (("在制", "wip"), "work_in_progress"),
        (("排产", "齐套", "支撑"), "daily_schedule"),
        (("库存", "安全库存", "可用库存", "仓库"), "daily_inventory"),
    )
