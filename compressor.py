"""对话历史压缩 - 当消息过多时，用模型将旧对话总结为摘要，减少 token 消耗。"""


def _get_field(m, field: str, default=""):
    """从 dict 或 Pydantic 对象中统一取字段。"""
    if isinstance(m, dict):
        return m.get(field, default)
    return getattr(m, field, default)


def estimate_tokens(messages: list) -> int:
    """粗略估算 token 数（中文约 1 字 = 1.5 token）。"""
    total = 0
    for m in messages:
        content = _get_field(m, "content", "")
        if isinstance(content, str):
            total += len(content)
    return int(total * 1.5)


def compress_messages(client, model: str, messages: list[dict], keep_recent: int = 6) -> list[dict]:
    """当消息列表过长时，将旧消息压缩为一条摘要。

    保留:
    - messages[0]: system prompt（始终保留）
    - 最近 keep_recent 条消息（保留上下文连贯性）
    压缩:
    - 中间的旧消息 → 让模型总结为一段摘要
    """
    # system + 至少 keep_recent 条才需要压缩
    if len(messages) <= keep_recent + 1:
        return messages

    system_msg = messages[0]
    old_messages = messages[1:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # 如果旧消息太少，不值得压缩
    if len(old_messages) < 4:
        return messages

    # 构造压缩请求
    old_text = []
    for m in old_messages:
        role = _get_field(m, "role", "unknown")
        content = _get_field(m, "content", "")
        if isinstance(content, str) and content:
            old_text.append(f"[{role}]: {content}")

    if not old_text:
        return messages

    summary_prompt = [
        {"role": "system", "content": "你是一个对话摘要助手。请将以下对话内容压缩为简洁的摘要，保留关键信息（用户的请求、重要决定、已完成的操作）。用中文回复，控制在 200 字以内。"},
        {"role": "user", "content": "\n".join(old_text)},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=summary_prompt,
            temperature=0.3,
        )
        summary = response.choices[0].message.content or "（摘要生成失败）"
    except Exception:
        return messages

    # 重建消息列表
    compressed = [
        system_msg,
        {"role": "system", "content": f"[以下是之前对话的摘要]\n{summary}"},
        *recent_messages,
    ]
    return compressed
