"""记忆系统 - 使用 ChromaDB 向量数据库存储，支持语义检索（RAG）。"""

import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import chromadb

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
EMBEDDING_MODEL = "text-embedding-v3"

# ── 初始化 ───────────────────────────────────────────────

_client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL"),
)
_chroma = chromadb.PersistentClient(path=DATA_DIR)
_collection = _chroma.get_or_create_collection(
    name="memories",
    metadata={"hnsw:space": "cosine"},
)


def _get_embedding(text: str) -> list[float]:
    """调用 DashScope embedding API 获取文本向量。"""
    resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding


def _next_id() -> str:
    """生成下一个递增 ID。"""
    existing = _collection.get()
    if not existing["ids"]:
        return "1"
    max_id = max(int(i) for i in existing["ids"])
    return str(max_id + 1)


# ── 公开接口（与原来保持一致）────────────────────────────

def save_memory(content: str, category: str = "general") -> str:
    """保存一条记忆到向量数据库。"""
    memory_id = _next_id()
    embedding = _get_embedding(content)
    _collection.add(
        ids=[memory_id],
        embeddings=[embedding],
        documents=[content],
        metadatas=[{
            "category": category,
            "created_at": datetime.now().isoformat(),
        }],
    )
    return f"已记住: {content}"


def delete_memory(memory_id: int) -> str:
    """删除一条记忆。"""
    str_id = str(memory_id)
    existing = _collection.get(ids=[str_id])
    if not existing["ids"]:
        return f"未找到记忆 #{memory_id}"
    _collection.delete(ids=[str_id])
    return f"已删除记忆 #{memory_id}"


def update_memory(memory_id: int, content: str = None, category: str = None) -> str:
    """更新一条记忆的内容或分类。"""
    str_id = str(memory_id)
    existing = _collection.get(ids=[str_id], include=["documents", "metadatas"])
    if not existing["ids"]:
        return f"未找到记忆 #{memory_id}"
    old_content = existing["documents"][0]
    old_meta = existing["metadatas"][0]
    new_content = content if content is not None else old_content
    new_meta = dict(old_meta)
    if category is not None:
        new_meta["category"] = category
    new_embedding = _get_embedding(new_content)
    _collection.update(
        ids=[str_id],
        embeddings=[new_embedding],
        documents=[new_content],
        metadatas=[new_meta],
    )
    return f"已更新记忆 #{memory_id}"


def search_memories(keyword: str = "") -> list[dict]:
    """搜索记忆。有关键词时使用语义检索，否则返回全部。"""
    if not keyword:
        result = _collection.get(include=["documents", "metadatas"])
        return [
            {"id": int(id_), "content": doc, **meta}
            for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ]
    # 语义检索：用 embedding 找最相关的记忆
    embedding = _get_embedding(keyword)
    result = _collection.query(
        query_embeddings=[embedding],
        n_results=min(10, _collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )
    if not result["ids"][0]:
        return []
    return [
        {"id": int(id_), "content": doc, "relevance": round(1 - dist, 3), **meta}
        for id_, doc, meta, dist in zip(
            result["ids"][0], result["documents"][0],
            result["metadatas"][0], result["distances"][0],
        )
    ]


def format_memories_for_prompt(query: str = "", top_k: int = 10) -> str:
    """将记忆格式化为 system prompt 的一部分。

    如果提供了 query，只返回语义最相关的 top_k 条；
    否则返回全部（记忆少时）或最近的 top_k 条。
    """
    if query:
        memories = search_memories(query)[:top_k]
    else:
        result = _collection.get(include=["documents", "metadatas"])
        if not result["ids"]:
            return ""
        memories = [
            {"id": int(id_), "content": doc, **meta}
            for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ]
        # 如果记忆太多，只取最近的 top_k 条
        if len(memories) > top_k:
            memories = memories[-top_k:]

    if not memories:
        return ""
    lines = ["[用户记忆]"]
    for m in memories:
        lines.append(f"- [{m.get('category', 'general')}] {m['content']}")
    return "\n".join(lines)
