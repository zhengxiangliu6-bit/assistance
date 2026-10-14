"""记忆系统 v2 - 使用 ChromaDB 向量数据库存储，支持语义检索（RAG）。

v2 新增：来源追踪、去重、冲突检测、版本历史、状态管理、增强检索。
"""

import os
import shutil
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import chromadb

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "data", "chroma_db_backup_v1")
EMBEDDING_MODEL = "text-embedding-v3"

VALID_CATEGORIES = [
    "habit", "preference", "info", "general",
    "goal", "decision", "event", "feedback",
]
VALID_STATUSES = ["active", "superseded", "revoked"]
VALID_SOURCE_TYPES = ["explicit", "inferred"]

DEDUP_SIMILARITY_THRESHOLD = 0.92

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


def _now_iso() -> str:
    return datetime.now().isoformat()


def _default_metadata(category: str = "general", **overrides) -> dict:
    """构造完整的 v2 metadata，所有字段均为字符串。"""
    now = _now_iso()
    meta = {
        "category": category if category in VALID_CATEGORIES else "general",
        "created_at": now,
        "updated_at": now,
        "source_type": "explicit",
        "source_summary": "",
        "status": "active",
        "supersedes": "",
        "project": "",
        "confirmed": "true",
    }
    for k, v in overrides.items():
        if k in meta and v is not None:
            meta[k] = str(v)
    return meta


# ── 迁移 ─────────────────────────────────────────────────

def _needs_migration() -> bool:
    """检查是否存在缺少 v2 字段的旧记忆。"""
    result = _collection.get(include=["metadatas"], limit=1)
    if not result["ids"]:
        return False
    meta = result["metadatas"][0]
    return "status" not in meta


def migrate_v1_to_v2():
    """为所有旧记忆补全 v2 字段。迁移前自动备份。"""
    if not _needs_migration():
        return

    # 备份
    if os.path.isdir(DATA_DIR) and not os.path.isdir(BACKUP_DIR):
        shutil.copytree(DATA_DIR, BACKUP_DIR)
        print("[Memory] v1 数据已备份到 chroma_db_backup_v1/")

    result = _collection.get(include=["documents", "metadatas"])
    if not result["ids"]:
        return

    for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
        if "status" in meta:
            continue
        new_meta = {
            "category": meta.get("category", "general"),
            "created_at": meta.get("created_at", _now_iso()),
            "updated_at": meta.get("created_at", _now_iso()),
            "source_type": "explicit",
            "source_summary": "",
            "status": "active",
            "supersedes": "",
            "project": "",
            "confirmed": "true",
        }
        _collection.update(ids=[id_], metadatas=[new_meta])

    print(f"[Memory] 已迁移 {len(result['ids'])} 条记忆到 v2 格式")


# ── 去重检测 ──────────────────────────────────────────────

def find_duplicates(content: str, threshold: float = DEDUP_SIMILARITY_THRESHOLD) -> list[dict]:
    """查找与给定内容语义相似的已有记忆。返回相似度 >= threshold 的活跃记忆。"""
    count = _collection.count()
    if count == 0:
        return []
    embedding = _get_embedding(content)
    result = _collection.query(
        query_embeddings=[embedding],
        n_results=min(5, count),
        include=["documents", "metadatas", "distances"],
    )
    if not result["ids"][0]:
        return []
    duplicates = []
    for id_, doc, meta, dist in zip(
        result["ids"][0], result["documents"][0],
        result["metadatas"][0], result["distances"][0],
    ):
        similarity = 1 - dist
        if similarity >= threshold and meta.get("status", "active") == "active":
            duplicates.append({
                "id": int(id_), "content": doc, "similarity": round(similarity, 4), **meta,
            })
    return duplicates


# ── 公开接口 ──────────────────────────────────────────────

def save_memory(
    content: str,
    category: str = "general",
    source_type: str = "explicit",
    source_summary: str = "",
    project: str = "",
    confirmed: str = "true",
    _skip_dedup: bool = False,
) -> str:
    """保存一条记忆到向量数据库。

    自动去重：如果已有高度相似的活跃记忆，跳过写入并返回提示。
    """
    # 去重检查
    if not _skip_dedup:
        dups = find_duplicates(content)
        if dups:
            dup = dups[0]
            return (
                f"已存在相似记忆 #{dup['id']}（相似度 {dup['similarity']}）: "
                f"{dup['content'][:60]}... 跳过重复保存。"
                f"如需更新，请使用 update_memory。"
            )

    memory_id = _next_id()
    embedding = _get_embedding(content)
    meta = _default_metadata(
        category=category,
        source_type=source_type,
        source_summary=source_summary,
        project=project,
        confirmed=confirmed,
    )
    _collection.add(
        ids=[memory_id],
        embeddings=[embedding],
        documents=[content],
        metadatas=[meta],
    )
    return f"已记住 (#{memory_id}): {content}"


def delete_memory(memory_id: int) -> str:
    """软删除一条记忆（标记为 revoked，不物理删除，历史可查）。"""
    str_id = str(memory_id)
    existing = _collection.get(ids=[str_id], include=["documents", "metadatas"])
    if not existing["ids"]:
        return f"未找到记忆 #{memory_id}"
    meta = existing["metadatas"][0]
    if meta.get("status") == "revoked":
        return f"记忆 #{memory_id} 已经被删除过了。"
    meta["status"] = "revoked"
    meta["updated_at"] = _now_iso()
    _collection.update(ids=[str_id], metadatas=[meta])
    return f"已删除记忆 #{memory_id}"


def update_memory(
    memory_id: int,
    content: str = None,
    category: str = None,
    project: str = None,
    confirmed: str = None,
) -> str:
    """更新一条记忆。自动维护版本链：旧记忆标记 superseded，新记忆的 supersedes 指向旧 ID。"""
    str_id = str(memory_id)
    existing = _collection.get(ids=[str_id], include=["documents", "metadatas"])
    if not existing["ids"]:
        return f"未找到记忆 #{memory_id}"

    old_content = existing["documents"][0]
    old_meta = existing["metadatas"][0]

    # 如果内容有变化，创建新版本（旧记忆标记 superseded）
    if content is not None and content != old_content:
        # 标记旧记忆
        old_meta["status"] = "superseded"
        old_meta["updated_at"] = _now_iso()
        _collection.update(ids=[str_id], metadatas=[old_meta])

        # 创建新记忆
        new_id = _next_id()
        new_embedding = _get_embedding(content)
        new_meta = _default_metadata(
            category=category or old_meta.get("category", "general"),
            source_type=old_meta.get("source_type", "explicit"),
            source_summary=f"更新自记忆 #{memory_id}",
            project=project if project is not None else old_meta.get("project", ""),
            confirmed=confirmed if confirmed is not None else old_meta.get("confirmed", "true"),
            supersedes=str_id,
        )
        _collection.add(
            ids=[new_id],
            embeddings=[new_embedding],
            documents=[content],
            metadatas=[new_meta],
        )
        return f"已更新记忆 #{memory_id} → 新版本 #{new_id}: {content}"
    else:
        # 仅更新 metadata（不变内容）
        new_meta = dict(old_meta)
        if category is not None:
            new_meta["category"] = category
        if project is not None:
            new_meta["project"] = project
        if confirmed is not None:
            new_meta["confirmed"] = confirmed
        new_meta["updated_at"] = _now_iso()
        _collection.update(ids=[str_id], metadatas=[new_meta])
        return f"已更新记忆 #{memory_id} 的属性"


def supersede_memory(old_id: int, new_content: str, **kwargs) -> str:
    """用新内容取代旧记忆。用于冲突解决。"""
    return update_memory(old_id, content=new_content, **kwargs)


def search_memories(keyword: str = "", include_inactive: bool = False) -> list[dict]:
    """搜索记忆。有关键词时使用语义检索，否则返回全部活跃记忆。"""
    if not keyword:
        result = _collection.get(include=["documents", "metadatas"])
        memories = [
            {"id": int(id_), "content": doc, **meta}
            for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ]
        if not include_inactive:
            memories = [m for m in memories if m.get("status", "active") == "active"]
        return memories

    # 语义检索
    count = _collection.count()
    if count == 0:
        return []
    embedding = _get_embedding(keyword)
    result = _collection.query(
        query_embeddings=[embedding],
        n_results=min(20, count),
        include=["documents", "metadatas", "distances"],
    )
    if not result["ids"][0]:
        return []
    memories = [
        {"id": int(id_), "content": doc, "relevance": round(1 - dist, 3), **meta}
        for id_, doc, meta, dist in zip(
            result["ids"][0], result["documents"][0],
            result["metadatas"][0], result["distances"][0],
        )
    ]
    if not include_inactive:
        memories = [m for m in memories if m.get("status", "active") == "active"]
    return memories


def list_memories(
    category: str = "",
    project: str = "",
    status: str = "active",
) -> str:
    """按条件筛选记忆列表，返回格式化文本。"""
    result = _collection.get(include=["documents", "metadatas"])
    if not result["ids"]:
        return "当前没有任何记忆。"

    memories = []
    for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
        if status and meta.get("status", "active") != status:
            continue
        if category and meta.get("category", "general") != category:
            continue
        if project and meta.get("project", "") != project:
            continue
        memories.append({"id": int(id_), "content": doc, **meta})

    if not memories:
        return "没有符合条件的记忆。"

    lines = [f"记忆列表 ({len(memories)} 条):"]
    for m in memories:
        cat = m.get("category", "general")
        src = "用户陈述" if m.get("source_type") == "explicit" else "Agent推断"
        conf = "✓" if m.get("confirmed") == "true" else "?"
        proj = f" @{m['project']}" if m.get("project") else ""
        date = m.get("updated_at", m.get("created_at", ""))[:10]
        lines.append(f"  #{m['id']} [{cat}|{conf}]{proj} {m['content'][:80]} ({src} {date})")
    return "\n".join(lines)


def get_memory_history(memory_id: int) -> str:
    """查看一条记忆的版本历史链。"""
    str_id = str(memory_id)
    existing = _collection.get(ids=[str_id], include=["documents", "metadatas"])
    if not existing["ids"]:
        return f"未找到记忆 #{memory_id}"

    chain = []
    # 向前追溯：这条记忆取代了谁
    current_id = str_id
    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        rec = _collection.get(ids=[current_id], include=["documents", "metadatas"])
        if not rec["ids"]:
            break
        chain.insert(0, {
            "id": int(current_id),
            "content": rec["documents"][0],
            "status": rec["metadatas"][0].get("status", "active"),
            "updated_at": rec["metadatas"][0].get("updated_at", ""),
        })
        current_id = rec["metadatas"][0].get("supersedes", "")

    # 向后追溯：谁取代了这条记忆
    result = _collection.get(include=["metadatas"])
    for id_, meta in zip(result["ids"], result["metadatas"]):
        if meta.get("supersedes") == str_id and id_ not in visited:
            visited.add(id_)
            rec = _collection.get(ids=[id_], include=["documents", "metadatas"])
            if rec["ids"]:
                chain.append({
                    "id": int(id_),
                    "content": rec["documents"][0],
                    "status": rec["metadatas"][0].get("status", "active"),
                    "updated_at": rec["metadatas"][0].get("updated_at", ""),
                })

    if len(chain) <= 1:
        m = chain[0] if chain else {"id": memory_id, "content": "(无)", "status": "unknown"}
        return f"记忆 #{memory_id} 没有版本历史。\n当前: [{m['status']}] {m['content']}"

    lines = [f"记忆 #{memory_id} 的版本历史 ({len(chain)} 个版本):"]
    for i, v in enumerate(chain):
        marker = " ← 当前" if v["id"] == memory_id else ""
        lines.append(f"  v{i+1}: #{v['id']} [{v['status']}] {v['content'][:60]} ({v['updated_at'][:10]}){marker}")
    return "\n".join(lines)


def format_memories_for_prompt(
    query: str = "",
    top_k: int = 10,
    project: str = "",
    token_budget: int = 800,
) -> str:
    """将记忆格式化为 system prompt 的一部分。

    增强检索：仅活跃记忆、项目过滤、确认优先、来源标注、Token 预算。
    """
    if query:
        memories = search_memories(query)
    else:
        result = _collection.get(include=["documents", "metadatas"])
        if not result["ids"]:
            return ""
        memories = [
            {"id": int(id_), "content": doc, **meta}
            for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ]
        # 仅活跃记忆
        memories = [m for m in memories if m.get("status", "active") == "active"]
        if len(memories) > top_k:
            memories = memories[-top_k:]

    if not memories:
        return ""

    # 项目过滤：保留全局 + 匹配项目
    if project:
        memories = [
            m for m in memories
            if not m.get("project") or m.get("project") == project
        ]

    # 排序：确认优先 → explicit 优先 → 更新时间近优先
    def _sort_key(m):
        confirmed_score = 0 if m.get("confirmed") == "true" else 1
        source_score = 0 if m.get("source_type") == "explicit" else 1
        updated = m.get("updated_at", m.get("created_at", ""))
        relevance = m.get("relevance", 0.5)
        return (confirmed_score, source_score, -relevance, updated)

    memories.sort(key=_sort_key)
    memories = memories[:top_k]

    # Token 预算裁剪（粗略：1 中文字 ≈ 1.5 token）
    lines = ["[用户记忆]"]
    used_tokens = 10  # 标题开销
    for m in memories:
        cat = m.get("category", "general")
        conf = "确认" if m.get("confirmed") == "true" else "待确认"
        src = "用户陈述" if m.get("source_type") == "explicit" else "Agent推断"
        date = m.get("updated_at", m.get("created_at", ""))[:10]
        line = f"- [{cat}|{conf}] {m['content']} ({src} {date})"
        line_tokens = int(len(line) * 1.5)
        if used_tokens + line_tokens > token_budget:
            break
        lines.append(line)
        used_tokens += line_tokens

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


# ── 启动时自动迁移 ────────────────────────────────────────

try:
    migrate_v1_to_v2()
except Exception as e:
    print(f"[Memory] 迁移警告（非致命）: {e}")
