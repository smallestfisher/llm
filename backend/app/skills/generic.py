from app.semantic.schema_registry import load_tables
from app.skills.base import BaseSkill


class GenericSkill(BaseSkill):
    domain = "general"
    skill_name = "generic_skill"
    node_name = "generic_skill"
    domain_label = "通用企业数据"
    guard_scope = "生产、库存、排产、需求、销售、财务以及相关经营数据的查询和分析"
    focus_areas = (
        "在可用表范围内完成通用企业数据检索与统计",
        "优先复用用户问题里出现的显式表、时间和业务对象",
        "当用户问题不够精确时，尽量先给出安全、收敛的查询",
    )
    sql_rules = (
        "尽量选择最贴近问题的单表；确有必要时再关联",
        "如果问题涉及最近、最新或时间趋势，优先使用日期字段",
        "避免无条件返回过大结果集，必要时使用合理 LIMIT",
    )
    answer_rules = (
        "优先说明是否查到数据以及记录规模",
        "若结果为空，明确说明未查到数据，不要猜测",
        "若结果为明细结果，避免重复输出大段表格",
    )
    default_tables = tuple(load_tables().keys())
    helper_tables = ()
    keyword_table_map = ()
