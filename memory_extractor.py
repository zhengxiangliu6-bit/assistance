"""对话后记忆提取器 — 异步分析对话内容，提取值得长期保留的记忆。

设计原则：
- 区分用户明确陈述 (explicit) 和 Agent 推断 (inferred)
- 敏感信息不自动写入
- 单次最多提取 5 条候选记忆
- API 调用有超时和重试限制
- 提取失败不阻塞正常聊天
"""

import json
import re
import threading
from openai import OpenAI
from memory import save_memory, find_duplicates, supersede_memory

# 敏感信息关键词（匹配到则标记 confirmed="pending"）
_SENSITIVE_PATTERNS = re.compile(
    r"(身份证|银行卡|信用卡|密码|password|secret|token|api.?key|"
    r"手机号|电话号|社保|护照|驾照|\d{15,18}|\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})",
    re.IGNORECASE,
)

EXTRACTION_PROMPT = """你是一个记忆提取助手。请分析以下对话，提取出值得长期记住的信息。

**只提取有持续价值的信息**，忽略：
- 一次性的问答（如"今天天气怎样"）
- 纯指令执行（如"帮我打开计算器"）
- 已被 save_memory 工具保存过的内容（避免重复）

**必须区分**：
- explicit: 用户直接说出的事实（如"我喜欢喝咖啡"、"我在北京工作"）
- inferred: Agent 根据对话推断的信息（如用户频繁问法语问题→可能在学法语）

**输出 JSON 数组**（空数组 [] 表示无值得记忆的内容），每个元素：
```json
{
    "content": "记忆内容（简洁完整）",
    "category": "habit|preference|info|general|goal|decision|event|feedback",
    "source_type": "explicit|inferred",
    "source_summary": "来源描述（如：用户在讨论学习计划时说...）"
}
```

最多返回 5 条。只输出 JSON 数组，不要其他内容。"""


def _extract_memories_sync(client: OpenAI, model: str, messages: list[dict]) -> list[dict]:
    """同步调用 LLM 分析对话，返回候选记忆列表。"""
    # 构造对话摘要（只取最近的用户和助手消息，控制 token）
    conversation_lines = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            # 截断过长的单条消息
            truncated = content[:500] + "..." if len(content) > 500 else content
            conversation_lines.append(f"[{role}]: {truncated}")

    if len(conversation_lines) < 2:
        return []

    # 只取最近的对话（控制输入 token）
    conversation_text = "\n".join(conversation_lines[-20:])

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=512,
            temperature=0.3,
            timeout=15,
        )
        raw = resp.choices[0].message.content or "[]"
        # 提取 JSON 数组
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        candidates = json.loads(raw)
        if not isinstance(candidates, list):
            return []
        return candidates[:5]
    except Exception:
        return []


def _is_sensitive(content: str) -> bool:
    return bool(_SENSITIVE_PATTERNS.search(content))


def _process_candidates(candidates: list[dict]) -> list[str]:
    """处理候选记忆：去重、冲突检测、敏感信息检查，写入数据库。返回日志。"""
    logs = []
    for c in candidates:
        content = c.get("content", "").strip()
        if not content or len(content) < 4:
            continue

        category = c.get("category", "general")
        source_type = c.get("source_type", "inferred")
        source_summary = c.get("source_summary", "")

        # 敏感信息检查
        confirmed = "pending" if _is_sensitive(content) else "true"
        # Agent 推断默认待确认
        if source_type == "inferred":
            confirmed = "pending"

        # 去重检查
        dups = find_duplicates(content)
        if dups:
            dup = dups[0]
            # 如果旧记忆内容完全被新内容包含或扩展，取代旧记忆
            old_len = len(dup["content"])
            new_len = len(content)
            if new_len > old_len * 1.3 and dup["similarity"] < 0.97:
                # 新内容更丰富，取代旧版本
                result = supersede_memory(
                    dup["id"], content,
                    category=category,
                    confirmed=confirmed,
                )
                logs.append(f"[记忆提取] 更新: {result}")
            else:
                logs.append(f"[记忆提取] 跳过重复: {content[:40]}...")
            continue

        # 写入新记忆
        result = save_memory(
            content=content,
            category=category,
            source_type=source_type,
            source_summary=source_summary,
            confirmed=confirmed,
            _skip_dedup=True,  # 已手动检查过
        )
        logs.append(f"[记忆提取] {result}")

    return logs


def extract_memories_async(
    client: OpenAI,
    model: str,
    messages: list[dict],
    callback=None,
):
    """在后台线程中异步提取记忆。完成后调用 callback(logs)。"""
    def _run():
        try:
            candidates = _extract_memories_sync(client, model, messages)
            if candidates:
                logs = _process_candidates(candidates)
            else:
                logs = []
            if callback:
                callback(logs)
        except Exception as e:
            if callback:
                callback([f"[记忆提取] 失败（非致命）: {e}"])

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
