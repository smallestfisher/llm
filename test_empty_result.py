
import os
import sys
from unittest.mock import MagicMock

# 模拟环境
os.environ["OPENAI_API_KEY"] = "fake-key"
os.environ["DB_URI"] = "sqlite:///:memory:"

# 将 llm 目录加入 path
sys.path.append(os.path.join(os.getcwd(), "llm"))

from core.graph import node_generate_answer

def test_empty_result_hallucination():
    state = {
        "question": "查询 2024年1月1日 产品代码为 'NON_EXISTENT' 的产出实绩",
        "sql_query": "SELECT * FROM production_actuals WHERE product_code = 'NON_EXISTENT' AND work_date = '2024-01-01';",
        "db_result": [], # 模拟空结果
        "columns": ["work_date", "product_code", "output_qty"],
        "retry_count": 0,
        "sql_error": ""
    }
    
    # 我们需要实际运行一下，但为了不消耗真实 Token 且能复现逻辑，
    # 我们可以看看 Prompt 是如何构建的，或者直接看输出。
    # 这里我们运行它（假设本地有环境可以跑 Qwen 或 Mock LLM）
    
    # 实际上，我可以直接修改 prompt.py 来解决。
    # 但为了确认，我先看看现有代码在 db_result 为空时的处理。
    
    print("Testing with empty db_result...")
    result = node_generate_answer(state)
    print(f"Final Answer: {result['final_answer']}")

if __name__ == "__main__":
    # 由于环境限制（无法调用真实 LLM），我将直接进行代码修复
    pass
