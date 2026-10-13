"""创意分析模块 - 将用户的想法结构化拆解为需求、方案、待办。"""

import json
import os
from datetime import datetime

IDEAS_FILE = os.path.join(os.path.dirname(__file__), "data", "ideas.json")


def _ensure_file():
    os.makedirs(os.path.dirname(IDEAS_FILE), exist_ok=True)
    if not os.path.exists(IDEAS_FILE):
        with open(IDEAS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_ideas() -> list[dict]:
    _ensure_file()
    with open(IDEAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_idea(title: str, summary: str, requirements: str, plan: str, risks: str = "") -> str:
    """保存一个结构化的创意分析结果。"""
    ideas = load_ideas()
    max_id = max((i["id"] for i in ideas), default=0)
    idea = {
        "id": max_id + 1,
        "title": title,
        "summary": summary,
        "requirements": requirements,
        "plan": plan,
        "risks": risks,
        "status": "draft",
        "created_at": datetime.now().isoformat(),
    }
    ideas.append(idea)
    with open(IDEAS_FILE, "w", encoding="utf-8") as f:
        json.dump(ideas, f, ensure_ascii=False, indent=2)
    return f"创意已保存: #{idea['id']} {title}"


def list_ideas() -> str:
    ideas = load_ideas()
    if not ideas:
        return "还没有保存任何创意。"
    lines = ["已保存的创意:"]
    for idea in ideas:
        lines.append(f"  #{idea['id']} [{idea['status']}] {idea['title']} ({idea['created_at'][:10]})")
    return "\n".join(lines)


def get_idea(idea_id: int) -> str:
    ideas = load_ideas()
    for idea in ideas:
        if idea["id"] == idea_id:
            parts = [
                f"=== 创意 #{idea['id']}: {idea['title']} ===",
                f"状态: {idea['status']}",
                f"\n[概述]\n{idea['summary']}",
                f"\n[需求分析]\n{idea['requirements']}",
                f"\n[方案规划]\n{idea['plan']}",
            ]
            if idea.get("risks"):
                parts.append(f"\n[风险与挑战]\n{idea['risks']}")
            return "\n".join(parts)
    return f"未找到 ID 为 {idea_id} 的创意"


def update_idea_status(idea_id: int, status: str) -> str:
    ideas = load_ideas()
    for idea in ideas:
        if idea["id"] == idea_id:
            idea["status"] = status
            with open(IDEAS_FILE, "w", encoding="utf-8") as f:
                json.dump(ideas, f, ensure_ascii=False, indent=2)
            return f"创意 #{idea_id} 状态已更新为: {status}"
    return f"未找到 ID 为 {idea_id} 的创意"


def delete_idea(idea_id: int) -> str:
    ideas = load_ideas()
    original_len = len(ideas)
    ideas = [i for i in ideas if i["id"] != idea_id]
    if len(ideas) == original_len:
        return f"未找到 ID 为 {idea_id} 的创意"
    with open(IDEAS_FILE, "w", encoding="utf-8") as f:
        json.dump(ideas, f, ensure_ascii=False, indent=2)
    return f"已删除创意 #{idea_id}"
