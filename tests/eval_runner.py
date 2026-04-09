import json
import sys
import re
import asyncio
from core.graph import get_compiled_workflow

def is_field_in_sql(sql: str, expected_field: str) -> bool:
    """升级版验证：支持别名匹配"""
    if '.' in expected_field:
        table, col = expected_field.split('.', 1)
        pattern_full = rf"\b{table}\.{col}\b"
        alias_match = re.search(rf"\bFROM\s+{table}\s+(\w+)\b", sql, re.IGNORECASE)
        if alias_match:
            alias = alias_match.group(1)
            pattern_alias = rf"\b{alias}\.{col}\b"
            return bool(re.search(pattern_full, sql, re.IGNORECASE) or re.search(pattern_alias, sql, re.IGNORECASE))
        return bool(re.search(pattern_full, sql, re.IGNORECASE))
    return bool(re.search(rf"\b{expected_field}\b", sql, re.IGNORECASE))

async def run_evaluation():
    with open('tests/goldens.json', 'r', encoding='utf-8') as f:
        goldens = json.load(f)
    
    workflow = await get_compiled_workflow()
    passed = 0
    
    print(f"🚀 开始回归测试，共 {len(goldens)} 条用例...\n")
    
    for case in goldens:
        question = case['question']
        expected = case['expected_field']
        
        # 🔴 关键修复：加入 thread_id 配置
        config = {"configurable": {"thread_id": f"test_{question[:5]}"}}
        result = await workflow.ainvoke({"question": question, "chat_history": []}, config=config)
        
        sql = result.get("sql_query", "")
        
        if is_field_in_sql(sql, expected):
            print(f"✅ PASSED: '{question}' -> 匹配成功")
            passed += 1
        else:
            print(f"❌ FAILED: '{question}'")
            print(f"   预期语义: {expected}")
            print(f"   实际 SQL: {sql}")
    
    print(f"\n测试完成: {passed}/{len(goldens)} 通过。")
    sys.exit(0 if passed == len(goldens) else 1)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
