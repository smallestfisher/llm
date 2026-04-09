import chromadb
from chromadb.utils import embedding_functions

# 初始化 ChromaDB 客户端
client = chromadb.PersistentClient(path="./core/config/semantic_db")

# 使用默认的句子嵌入函数（如果需要更细粒度控制，后续可替换）
sentence_transformer_ef = embedding_functions.DefaultEmbeddingFunction()

# 创建或获取 collection
collection = client.get_or_create_collection(
    name="lexicon_mapping",
    embedding_function=sentence_transformer_ef
)

def add_mapping(term: str, field: str, description: str):
    """添加词条映射到向量库"""
    collection.upsert(
        documents=[f"用户询问: {term}, 对应字段: {field}"],
        metadatas=[{"field": field, "description": description}],
        ids=[term]
    )

def query_mapping(query: str, n_results=1):
    """查询语义最相似的映射"""
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    if results['documents'] and results['distances'][0][0] < 0.5: # 设定距离阈值
        return results['metadatas'][0][0]
    return None

# 示例初始化
if __name__ == "__main__":
    add_mapping("产出", "output_qty", "生产产出的数量")
    add_mapping("不良率", "defect_rate", "生产过程中的产品不良率")
    print("向量库初始化完成。")
