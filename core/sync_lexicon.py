import json
from core.semantic_cache import add_mapping

def sync_lexicon_to_db():
    """将 lexicon.json 中的所有词条同步到向量库"""
    try:
        with open('core/config/lexicon.json', 'r', encoding='utf-8') as f:
            lexicon = json.load(f)
        
        count = 0
        for term, field in lexicon.items():
            # 这里将描述留空或者根据 field 生成简单的说明
            description = f"映射字段: {field}"
            add_mapping(term, field, description)
            count += 1
            
        print(f"成功同步 {count} 条语义映射至向量库。")
    except Exception as e:
        print(f"同步失败: {e}")

if __name__ == "__main__":
    sync_lexicon_to_db()
