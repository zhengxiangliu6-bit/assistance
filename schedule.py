"""日程管理 - 增删查待办事项和日程安排。"""

import json
import os
from datetime import datetime

SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "data", "schedule.json")


def _ensure_file():
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    if not os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_tasks() -> list[dict]:
    _ensure_file()
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def add_task(title: str, due_date: str = "", due_time: str = "", priority: str = "normal") -> str:
    """添加待办。due_date 格式 YYYY-MM-DD，due_time 格式 HH:MM，priority: low/normal/high。"""
    tasks = load_tasks()
    max_id = max((t["id"] for t in tasks), default=0)
    task = {
        "id": max_id + 1,
        "title": title,
        "due_date": due_date,
        "due_time": due_time,
        "priority": priority,
        "done": False,
        "created_at": datetime.now().isoformat(),
    }
    tasks.append(task)
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    result = f"已添加待办: {title}"
    if due_date:
        result += f" (截止: {due_date}"
        if due_time:
            result += f" {due_time}"
        result += ")"
    elif due_time:
        result += f" (时间: {due_time})"
    return result


def complete_task(task_id: int) -> str:
    tasks = load_tasks()
    today = datetime.now().strftime("%Y-%m-%d")
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

            # 找出下一个待办（今日未完成，按时间排序）
            remaining = [
                x for x in tasks
                if not x["done"] and x.get("due_date", "") <= today and x.get("due_date", "") != ""
            ]
            remaining.sort(key=lambda x: x.get("due_time") or "99:99")

            result = f"已完成: {t['title']}"
            if remaining:
                nxt = remaining[0]
                time_hint = f" [{nxt['due_time']}]" if nxt.get("due_time") else ""
                result += f"\n下一项待办: {nxt['title']}{time_hint}"
                done_count = sum(1 for x in tasks if x["done"] and x.get("due_date") == today)
                total_today = sum(1 for x in tasks if x.get("due_date") == today)
                result += f"\n今日进度: {done_count}/{total_today}"
            else:
                result += "\n今日所有待办已完成!"
            return result
    return f"未找到 ID 为 {task_id} 的待办"


def uncomplete_task(task_id: int) -> str:
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = False
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            return f"已取消完成: {t['title']}"
    return f"未找到 ID 为 {task_id} 的待办"


def update_task(task_id: int, title: str = None, priority: str = None, due_date: str = None, due_time: str = None) -> str:
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            if title is not None:
                t["title"] = title
            if priority is not None:
                t["priority"] = priority
            if due_date is not None:
                t["due_date"] = due_date
            if due_time is not None:
                t["due_time"] = due_time
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            return f"已更新待办 #{task_id}"
    return f"未找到 ID 为 {task_id} 的待办"


def reorder_tasks(task_ids: list[int]) -> str:
    tasks = load_tasks()
    task_map = {t["id"]: t for t in tasks}
    reordered = []
    for tid in task_ids:
        if tid in task_map:
            reordered.append(task_map.pop(tid))
    reordered.extend(task_map.values())
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(reordered, f, ensure_ascii=False, indent=2)
    return "排序已更新"


def move_task(task_id: int, direction: int) -> str:
    """上移 direction=-1，下移 direction=1。"""
    tasks = load_tasks()
    idx = next((i for i, t in enumerate(tasks) if t["id"] == task_id), None)
    if idx is None:
        return f"未找到 ID 为 {task_id} 的待办"
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(tasks):
        return "已在边界"
    tasks[idx], tasks[new_idx] = tasks[new_idx], tasks[idx]
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    return "排序已更新"


def delete_task(task_id: int) -> str:
    tasks = load_tasks()
    original_len = len(tasks)
    tasks = [t for t in tasks if t["id"] != task_id]
    if len(tasks) == original_len:
        return f"未找到 ID 为 {task_id} 的待办"
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    return f"已删除待办 #{task_id}"


def list_tasks(show_done: bool = False) -> str:
    tasks = load_tasks()
    if not show_done:
        tasks = [t for t in tasks if not t["done"]]
    if not tasks:
        return "当前没有待办事项。"
    lines = []
    for t in tasks:
        status = "[x]" if t["done"] else "[ ]"
        pri = {"high": "[!]", "normal": "", "low": "[-]"}.get(t["priority"], "")
        due_parts = []
        if t.get("due_date"):
            due_parts.append(t["due_date"])
        if t.get("due_time"):
            due_parts.append(t["due_time"])
        due = f" (截止: {' '.join(due_parts)})" if due_parts else ""
        lines.append(f"  {status} #{t['id']} {pri} {t['title']}{due}")
    return "待办列表:\n" + "\n".join(lines)


def get_today_tasks() -> str:
    """获取今天的待办，包含逾期未完成的任务。"""
    today = datetime.now().strftime("%Y-%m-%d")
    tasks = load_tasks()
    overdue = []
    today_tasks = []
    for t in tasks:
        if t["done"] or not t.get("due_date"):
            continue
        if t["due_date"] < today:
            overdue.append(t)
        elif t["due_date"] == today:
            today_tasks.append(t)

    if not overdue and not today_tasks:
        return "今天没有待办事项。"

    lines = []
    if overdue:
        lines.append("逾期未完成:")
        for t in overdue:
            pri = {"high": "[!]", "normal": "", "low": "[-]"}.get(t["priority"], "")
            lines.append(f"  [!] #{t['id']} {pri} {t['title']} (截止: {t['due_date']})")
    if today_tasks:
        # 按时间排序：有时间的在前，按时间升序
        today_tasks.sort(key=lambda t: t.get("due_time") or "99:99")
        lines.append("今日待办:")
        for t in today_tasks:
            pri = {"high": "[!]", "normal": "", "low": "[-]"}.get(t["priority"], "")
            time_str = f" [{t['due_time']}]" if t.get("due_time") else ""
            lines.append(f"  [ ] #{t['id']} {pri} {t['title']}{time_str}")
    return "\n".join(lines)
