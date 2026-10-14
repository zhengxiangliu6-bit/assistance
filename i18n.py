"""多语言支持。settings.json 中 language 字段控制当前语言。"""

import os
import json

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "data", "settings.json")

_STRINGS = {
    "zh": {
        # Nav
        "nav.chat": "对话",
        "nav.schedule": "日程",
        "nav.memory": "记忆",
        "nav.ideas": "创意",
        "nav.settings": "设置",

        # Chat
        "chat.welcome_title": "有什么我可以帮你的？",
        "chat.welcome_sub": "你的个人 AI 工作台",
        "chat.placeholder": "输入消息...",
        "chat.clear": "清空对话",
        "chat.quick.plan": "安排今日",
        "chat.quick.plan_prompt": "帮我安排一下今天的日程",
        "chat.quick.tasks": "查看待办",
        "chat.quick.tasks_prompt": "我今天有什么待办事项？",
        "chat.quick.memory": "搜索记忆",
        "chat.quick.memory_prompt": "你还记得我的作息习惯吗？",
        "chat.quick.idea": "分析想法",
        "chat.quick.idea_prompt": "我有一个新的想法想分析一下",

        # Status
        "status.ready": "就绪",
        "status.thinking": "思考中...",
        "status.tool": "执行工具",
        "status.streaming": "生成中...",
        "status.error": "出错",

        # Schedule
        "schedule.add_placeholder": "添加新待办...",
        "schedule.add": "添加",
        "schedule.overdue": "逾期",
        "schedule.today": "今日",
        "schedule.upcoming": "即将到来",
        "schedule.unscheduled": "未安排",
        "schedule.completed": "已完成",
        "schedule.empty": "暂无待办，在上方添加一个吧。",
        "schedule.edit": "编辑",

        # Memory
        "memory.add_placeholder": "添加新记忆...",
        "memory.add": "添加",
        "memory.empty": "暂无记忆。",
        "memory.edit": "编辑",
        "memory.cat.habit": "习惯",
        "memory.cat.preference": "偏好",
        "memory.cat.info": "信息",
        "memory.cat.general": "其他",

        # Ideas
        "ideas.empty": "暂无创意。在对话中让助理帮你分析想法。",
        "ideas.status.draft": "草稿",
        "ideas.status.in_progress": "进行中",
        "ideas.status.done": "已完成",
        "ideas.status.abandoned": "已搁置",

        # Dialog
        "dialog.title": "标题",
        "dialog.priority": "优先级",
        "dialog.date": "日期 (YYYY-MM-DD)",
        "dialog.time": "时间 (HH:MM)",
        "dialog.content": "内容",
        "dialog.category": "分类",
        "dialog.save": "保存",
        "dialog.cancel": "取消",
        "dialog.edit_task": "编辑待办",
        "dialog.edit_memory": "编辑记忆",

        # Settings
        "settings.language": "界面语言",
        "settings.language_desc": "切换界面显示语言",

        # Tray
        "tray.show": "显示窗口",
        "tray.quit": "退出",
        "tray.minimized": "已最小化到托盘。Ctrl+Alt+A 切换显示。",
        "tray.reminder": "提醒",
        "tray.tasks": "待办提醒",
        "tray.upcoming": "即将开始",
    },

    "en": {
        "nav.chat": "Chat",
        "nav.schedule": "Schedule",
        "nav.memory": "Memory",
        "nav.ideas": "Ideas",
        "nav.settings": "Settings",

        "chat.welcome_title": "What can I help you with?",
        "chat.welcome_sub": "Your personal AI workspace.",
        "chat.placeholder": "Message Assistance...",
        "chat.clear": "Clear",
        "chat.quick.plan": "Plan my day",
        "chat.quick.plan_prompt": "Help me plan my day",
        "chat.quick.tasks": "Review tasks",
        "chat.quick.tasks_prompt": "What tasks do I have today?",
        "chat.quick.memory": "Search memory",
        "chat.quick.memory_prompt": "Do you remember my daily routine?",
        "chat.quick.idea": "Capture idea",
        "chat.quick.idea_prompt": "I have a new idea to analyze",

        "status.ready": "Ready",
        "status.thinking": "Thinking...",
        "status.tool": "Running tool",
        "status.streaming": "Generating...",
        "status.error": "Error",

        "schedule.add_placeholder": "Add a new task...",
        "schedule.add": "Add",
        "schedule.overdue": "Overdue",
        "schedule.today": "Today",
        "schedule.upcoming": "Upcoming",
        "schedule.unscheduled": "Unscheduled",
        "schedule.completed": "Completed",
        "schedule.empty": "No tasks yet. Add one above.",
        "schedule.edit": "Edit",

        "memory.add_placeholder": "Add a new memory...",
        "memory.add": "Add",
        "memory.empty": "No memories stored yet.",
        "memory.edit": "Edit",
        "memory.cat.habit": "Habit",
        "memory.cat.preference": "Preference",
        "memory.cat.info": "Info",
        "memory.cat.general": "General",

        "ideas.empty": "No ideas yet. Chat with the agent to analyze one.",
        "ideas.status.draft": "Draft",
        "ideas.status.in_progress": "In Progress",
        "ideas.status.done": "Done",
        "ideas.status.abandoned": "Abandoned",

        "dialog.title": "Title",
        "dialog.priority": "Priority",
        "dialog.date": "Date (YYYY-MM-DD)",
        "dialog.time": "Time (HH:MM)",
        "dialog.content": "Content",
        "dialog.category": "Category",
        "dialog.save": "Save",
        "dialog.cancel": "Cancel",
        "dialog.edit_task": "Edit Task",
        "dialog.edit_memory": "Edit Memory",

        "settings.language": "Language",
        "settings.language_desc": "Switch interface language",

        "tray.show": "Show",
        "tray.quit": "Quit",
        "tray.minimized": "Minimized to tray. Ctrl+Alt+A to toggle.",
        "tray.reminder": "Reminder",
        "tray.tasks": "Task Reminder",
        "tray.upcoming": "Upcoming",
    },
}

_current_lang = None


def _load_lang() -> str:
    global _current_lang
    if _current_lang:
        return _current_lang
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _current_lang = data.get("language", "zh")
    except (FileNotFoundError, json.JSONDecodeError):
        _current_lang = "zh"
    return _current_lang


def set_language(lang: str):
    global _current_lang
    _current_lang = lang
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data["language"] = lang
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_language() -> str:
    return _load_lang()


def t(key: str) -> str:
    """获取翻译文本。"""
    lang = _load_lang()
    strings = _STRINGS.get(lang, _STRINGS["zh"])
    return strings.get(key, _STRINGS["zh"].get(key, key))


def cat_name(category: str) -> str:
    """获取记忆分类的显示名。"""
    return t(f"memory.cat.{category}")
