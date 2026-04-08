# 核心业务术语映射
# 格式: "用户口语/模糊术语": ["标准字段/逻辑表达"]
LEXICON_MAP = {
    # 产出与良率
    "产出": "output_qty",
    "良率": "yield_rate",
    "不良率": "(100 - yield_rate)",
    "产线情况": "input_qty, output_qty, yield_rate",
    
    # 异常与停机
    "停线": "downtime_hours > 0",
    "异常": "defect_qty > 0 OR downtime_hours > 0",
    "瓶颈": "priority >= 4 AND process_entry_time < DATE_SUB(NOW(), INTERVAL 12 HOUR)",
    "积压": "wip_qty > 1000",
    "不良": "defect_type_code",
    
    # 计划与需求
    "齐套": "available_qty + in_transit_qty",
    "紧急": "priority = 5 OR status = 'Urgent'",
    "任务": "target_qty",
    
    # 时间缩写
    "上周": "WEEK(work_date) = WEEK(NOW()) - 1",
    "本月": "DATE_FORMAT(work_date, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
}

def normalize_question(question: str):
    """对用户问题中的口语进行标准化替换，并返回匹配的词条列表"""
    hits = []
    for colloquial, formal in LEXICON_MAP.items():
        if colloquial in question:
            hits.append(colloquial)
            question = question.replace(colloquial, formal)
    return question, hits
