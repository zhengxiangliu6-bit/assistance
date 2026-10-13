"""配置与权限管理 - 持久化存储在 data/settings.json。"""

import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "data", "settings.json")

# 权限定义：每项包含 name（显示名）、description（说明）、default（默认值）
PERMISSION_DEFS = {
    # ── 工具权限（对话中 Agent 能做什么）──
    "auto_save_memory": {
        "name": "自动记忆",
        "group": "chat",
        "description": "允许助理自动记住你提到的习惯和偏好",
        "default": True,
    },
    "auto_manage_schedule": {
        "name": "自动管理日程",
        "group": "chat",
        "description": "允许助理自动添加/修改/完成待办事项",
        "default": True,
    },
    "auto_save_ideas": {
        "name": "自动保存创意",
        "group": "chat",
        "description": "允许助理自动保存分析后的创意方案",
        "default": True,
    },
    # ── 系统权限（预留，后续实现）──
    "file_read": {
        "name": "读取文件",
        "group": "system",
        "description": "允许助理读取本地文件内容",
        "default": False,
    },
    "file_write": {
        "name": "写入文件",
        "group": "system",
        "description": "允许助理创建或修改本地文件",
        "default": False,
    },
    "run_command": {
        "name": "执行命令",
        "group": "system",
        "description": "允许助理执行系统命令和脚本",
        "default": False,
    },
    "network_search": {
        "name": "联网搜索",
        "group": "system",
        "description": "允许助理搜索互联网获取信息",
        "default": True,
    },
    "clipboard": {
        "name": "剪贴板访问",
        "group": "system",
        "description": "允许助理读取和写入系统剪贴板",
        "default": False,
    },
    "notification": {
        "name": "桌面通知",
        "group": "system",
        "description": "允许助理发送系统桌面通知",
        "default": False,
    },
    "autostart": {
        "name": "开机自启",
        "group": "system",
        "description": "系统开机时自动启动助理",
        "default": False,
    },
    "background": {
        "name": "后台运行",
        "group": "system",
        "description": "关闭窗口后最小化到托盘继续运行",
        "default": False,
    },
}

# 权限 → 工具名的映射（用于运行时检查）
PERMISSION_TOOL_MAP = {
    "auto_save_memory": ["save_memory", "delete_memory", "search_memories"],
    "auto_manage_schedule": ["add_task", "complete_task", "delete_task", "list_tasks", "get_today_tasks"],
    "auto_save_ideas": ["save_idea", "list_ideas", "get_idea", "update_idea_status", "delete_idea"],
    "network_search": ["web_search", "news_search"],
    "file_read": ["read_file", "list_directory"],
    "file_write": ["write_file"],
    "clipboard": ["read_clipboard", "write_clipboard"],
    "run_command": ["open_url", "open_application"],
    "notification": ["set_reminder"],
}


def _ensure_file():
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "permissions": {k: v["default"] for k, v in PERMISSION_DEFS.items()},
            "appearance": {
                "theme": "dark",
            },
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)


def load_settings() -> dict:
    _ensure_file()
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
    # 补齐新增的权限项
    for k, v in PERMISSION_DEFS.items():
        if k not in settings.get("permissions", {}):
            settings.setdefault("permissions", {})[k] = v["default"]
    return settings


def save_settings(settings: dict):
    _ensure_file()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_permission(key: str) -> bool:
    settings = load_settings()
    return settings.get("permissions", {}).get(key, False)


def set_permission(key: str, value: bool):
    settings = load_settings()
    settings.setdefault("permissions", {})[key] = value
    save_settings(settings)


def is_tool_allowed(tool_name: str) -> bool:
    """检查某个工具是否被当前权限允许。"""
    for perm_key, tools in PERMISSION_TOOL_MAP.items():
        if tool_name in tools:
            return get_permission(perm_key)
    # 未被任何权限管控的工具，默认允许
    return True


def get_blocked_tools() -> set:
    """返回当前被禁用的工具集合。"""
    blocked = set()
    for perm_key, tools in PERMISSION_TOOL_MAP.items():
        if not get_permission(perm_key):
            blocked.update(tools)
    return blocked
