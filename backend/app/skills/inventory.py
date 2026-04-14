from app.skills.base import BaseSkill


class InventorySkill(BaseSkill):
    domain = "inventory"
    skill_name = "inventory_skill"
    node_name = "inventory_skill"
    domain_label = "库存与供应保障"
    guard_scope = "库存、在途、客户仓、安全库存、齐套、备货和供应保障分析"
    focus_areas = (
        "关注TTL库存、Hold库存、OMS库存和客户侧库存覆盖",
        "处理库存充足性、库龄结构、客户仓与缺料风险",
        "区分日库存快照与月度 OMS 库龄/期初库存口径",
    )
    field_conventions = (
        "daily_inventory 是日级库存快照，核心指标是 TTL_Qty 与 HOLD_Qty，不要误写 available_qty 或 safety_stock",
        "daily_inventory 的工厂与库位字段是 factory_code、ERP_FACTORY、ERP_LOCATION，可结合 PRODUCTION_TYPE、GRADE、CHECKINCODE 过滤",
        "oms_inventory 是月级库存表，核心指标是 glass_qty、panel_qty 以及各库龄桶，不存在 in_transit_qty、hub_qty、customer_hub_qty 这些旧字段",
        "oms_inventory 适合回答期初库存、客户库存、库龄分布、OMS库存覆盖等问题",
        "当用户问库存能否支撑计划时，库存域只提供库存侧结论，计划侧对比交给跨域编排",
    )
    sql_rules = (
        "涉及TTL库存、Hold库存、工厂库存或库位时优先检查 daily_inventory",
        "涉及在途、客户仓、hub、OMS、期初库存或库龄时优先检查 oms_inventory",
        "涉及齐套、支撑能力或缺料风险时，先基于库存表给出库存侧判断，不要直接跨到计划表",
        "如果原问题是跨域影响分析，库存域只输出库存基线指标和风险线索，不要自行构造覆盖率阈值或跨表推导公式",
        "如果问题只问月份、客户、工厂、库位、产品或等级，请优先使用这些字段过滤",
        "涉及库龄时优先汇总 ONE_AGE_panel_qty 到 EUGHT_AGE_panel_qty，不要错误引用旧 in_transit_qty 字段",
        "除非用户明确要求全部明细，否则优先输出聚合或风险聚焦结果",
    )
    answer_rules = (
        "先说明库存是否充足，以及是否存在缺口或风险",
        "若涉及OMS库存、客户仓或库龄，优先说明期初覆盖和老化结构",
        "若结果为空，明确说明当前条件下未发现库存异常或相关记录",
    )
    default_tables = (
        "daily_inventory",
        "oms_inventory",
    )
    helper_tables = ("product_attributes", "product_mapping")
    keyword_table_map = (
        (("在途", "hub", "客户仓", "oms", "库龄", "期初"), "oms_inventory"),
        (("ttl", "hold", "checkincode", "库位", "erp"), "daily_inventory"),
        (("库存", "安全库存", "可用库存", "仓库", "齐套", "支撑", "缺料"), "daily_inventory"),
    )
