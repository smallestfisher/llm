import argparse
from core.semantic_cache import add_mapping

def main():
    parser = argparse.ArgumentParser(description="快速向向量库添加语义映射样本")
    parser.add_argument("--term", required=True, help="用户的口语词汇")
    parser.add_argument("--field", required=True, help="对应的数据库标准字段")
    parser.add_argument("--desc", required=True, help="字段的业务解释")

    args = parser.parse_args()

    try:
        add_mapping(args.term, args.field, args.desc)
        print(f"✅ 成功添加样本: '{args.term}' -> '{args.field}'")
    except Exception as e:
        print(f"❌ 添加失败: {e}")

if __name__ == "__main__":
    main()
