"""智能通知 - 用 LLM 生成个性化、有温度的提醒内容。"""

import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from memory import format_memories_for_prompt
from schedule import load_tasks

load_dotenv()

_client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL"),
)
_MODEL = os.getenv("MODEL", "glm-5.2")


def _call_llm(prompt: str) -> str:
    """短调用，生成一句提醒话语。max_tokens 设高以留足空间给模型思考。"""
    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "你是一个亲切的个人助理。直接输出内容，简短回答，不超过两三句话。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.9,
        )
        content = resp.choices[0].message.content or ""
        return content.strip()
    except Exception as e:
        return f"(生成失败: {e})"


def _get_context(query: str = "") -> str:
    """获取当前时间 + 用户记忆 + 今日日程的简要上下文。"""
    now = datetime.now()
    time_str = now.strftime("%Y年%m月%d日 %A %H:%M")

    memories = format_memories_for_prompt(query=query or "作息习惯日程", top_k=3)

    today = now.strftime("%Y-%m-%d")
    tasks = load_tasks()
    today_tasks = [t for t in tasks if t.get("due_date") == today and not t["done"]]
    today_tasks.sort(key=lambda x: x.get("due_time") or "99:99")

    task_lines = []
    for t in today_tasks:
        time_part = f"[{t['due_time']}] " if t.get("due_time") else ""
        task_lines.append(f"  {time_part}{t['title']}")
    tasks_str = "\n".join(task_lines) if task_lines else "  (无)"

    return f"当前时间: {time_str}\n\n{memories}\n\n[今日剩余待办]\n{tasks_str}"


# ── 各场景的智能消息生成 ────────────────────────────────

def gen_pre_task_reminder(task: dict) -> str:
    """任务即将开始时的提醒（提前 10 分钟）。"""
    ctx = _get_context()
    prompt = f"""{ctx}

即将开始的任务: {task['title']}，时间: {task.get('due_time', '未知')}

请用一两句话提醒用户该准备做这件事了。要求：
- 结合用户的习惯和偏好（如果有相关记忆的话）
- 语气亲切自然，像朋友提醒一样
- 简短，不超过 50 字
- 不要用"您"，用"你"
- 直接输出提醒内容，不要加前缀"""
    return _call_llm(prompt)


def gen_overdue_reminder(task: dict) -> str:
    """任务逾期时的提醒。"""
    ctx = _get_context()
    prompt = f"""{ctx}

逾期任务: {task['title']}，原定时间: {task.get('due_date', '')} {task.get('due_time', '')}

请用一两句话提醒用户这个任务逾期了。要求：
- 语气不要指责，温和地提醒
- 可以建议是补做还是跳过/推迟
- 简短，不超过 50 字
- 不要用"您"，用"你"
- 直接输出提醒内容，不要加前缀"""
    return _call_llm(prompt)


def gen_completion_message(completed_task: dict, next_task: dict | None) -> str:
    """完成任务后的鼓励 + 下一步引导。"""
    ctx = _get_context()
    next_info = ""
    if next_task:
        t = next_task.get("due_time", "")
        next_info = f"\n下一个任务: {next_task['title']}，时间: {t}" if t else f"\n下一个任务: {next_task['title']}"

    prompt = f"""{ctx}

刚完成的任务: {completed_task['title']}{next_info}

请用一两句话回应用户完成了任务。要求：
- 先简短鼓励/肯定
- 如果有下一个任务，自然地引导过渡（结合用户习惯）
- 如果没有下一个任务，可以建议放松
- 简短，不超过 60 字
- 不要用"您"，用"你"
- 直接输出内容，不要加前缀"""
    return _call_llm(prompt)


def gen_greeting() -> str:
    """打开 app 时的时段问候。"""
    ctx = _get_context()
    now = datetime.now()
    hour = now.hour

    if hour < 6:
        period = "凌晨了还没睡"
    elif hour < 9:
        period = "早上好"
    elif hour < 12:
        period = "上午好"
    elif hour < 14:
        period = "中午好"
    elif hour < 18:
        period = "下午好"
    elif hour < 22:
        period = "晚上好"
    else:
        period = "夜深了"

    prompt = f"""{ctx}

用户刚打开助理 app，现在{period}。

请生成一句个性化的问候。要求：
- 结合当前时间段和用户的日程安排
- 如果有即将到来的任务，顺便提一下
- 如果有逾期任务，温和提醒
- 语气亲切，像认识很久的朋友
- 简短，不超过 60 字
- 不要用"您"，用"你"
- 直接输出问候内容，不要加前缀"""
    return _call_llm(prompt)


def gen_daily_briefing() -> str:
    """每日播报（更智能的版本）。"""
    ctx = _get_context()
    now = datetime.now()
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    prompt = f"""{ctx}

今天是{weekday}，请生成今日播报。要求：
- 先说今天星期几
- 列出今日待办安排（按时间顺序）
- 结合用户的习惯给出今天的建议（比如今天轮到学习+游戏还是外包+画画）
- 如果有逾期任务，提醒处理
- 语气轻松自然
- 不超过 150 字
- 不要用"您"，用"你"
- 直接输出播报内容"""
    return _call_llm(prompt)
