"""Agent 引擎 - 核心对话逻辑，支持流式输出，供 CLI 和 GUI 共用。"""

import os
import json
from datetime import datetime, date
from openai import OpenAI
from dotenv import load_dotenv
from memory import (
    save_memory, delete_memory, update_memory, search_memories,
    list_memories, get_memory_history, format_memories_for_prompt,
)
from memory_extractor import extract_memories_async
from schedule import add_task, complete_task, delete_task, list_tasks, get_today_tasks
from creative import save_idea, list_ideas, get_idea, update_idea_status, delete_idea
from compressor import compress_messages, estimate_tokens
from settings import is_tool_allowed, get_blocked_tools
from system_tools import open_url, open_application, read_clipboard, write_clipboard, read_file, write_file, list_directory, set_reminder
from search import web_search, news_search
from mcp_client import mcp_start, mcp_get_tools, mcp_is_tool, mcp_call_tool
from skills import SkillLoader

load_dotenv()

# 启动 MCP 服务器
try:
    mcp_start()
except Exception as e:
    print(f"[MCP] 启动失败（非致命）: {e}")

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL"),
)
MODEL = os.getenv("MODEL", "glm-5.2")
MAX_TOKENS_BEFORE_COMPRESS = 3000
MAX_TOOL_ROUNDS = 3

# ── 工具定义 ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "记住用户的习惯、偏好或重要信息，跨对话保留。当用户提到自己的习惯、喜好、个人信息时主动调用。系统会自动去重，重复内容不会重复保存。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记住的内容"},
                    "category": {
                        "type": "string",
                        "enum": ["habit", "preference", "info", "general", "goal", "decision", "event", "feedback"],
                        "description": "分类: habit=习惯, preference=偏好, info=重要信息, goal=目标, decision=决策, event=事件, feedback=反馈, general=其他",
                    },
                    "project": {"type": "string", "description": "所属项目或主题（可选，空=全局）"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": "搜索用户之前保存的记忆/偏好/习惯信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词，为空则返回所有记忆"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_memory",
            "description": "删除一条记忆（软删除，历史可查）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer", "description": "要删除的记忆 ID"},
                },
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": "更新一条记忆的内容或属性。内容变更时自动创建新版本，旧版本保留可查。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer", "description": "要更新的记忆 ID"},
                    "content": {"type": "string", "description": "新内容（不填则不改内容）"},
                    "category": {"type": "string", "description": "新分类（不填则不改分类）"},
                    "project": {"type": "string", "description": "所属项目或主题"},
                },
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "按条件筛选记忆列表。可按分类、项目、状态筛选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "按分类筛选（可选）"},
                    "project": {"type": "string", "description": "按项目筛选（可选）"},
                    "status": {"type": "string", "enum": ["active", "superseded", "revoked"], "description": "按状态筛选，默认 active"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_history",
            "description": "查看一条记忆的版本历史，了解它被更新或取代的记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer", "description": "记忆 ID"},
                },
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "添加一条待办事项或日程安排。注意：title 中不要包含时间信息，时间必须填到 due_date 和 due_time 字段中。例如用户说'今天12点午睡'，title 应该是'午睡'，due_time 应该是'12:00'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "待办事项标题，不要包含日期和时间，只写事项内容"},
                    "due_date": {"type": "string", "description": "截止日期，格式 YYYY-MM-DD。用户说'今天'就填今天日期，说'明天'就填明天日期"},
                    "due_time": {"type": "string", "description": "具体时间，格式 HH:MM（24小时制）。用户说'12点'填'12:00'，说'下午3点'填'15:00'"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "description": "优先级",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "将一条待办标记为已完成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "待办 ID"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "删除一条待办事项。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "待办 ID"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "列出所有待办事项。",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_done": {"type": "boolean", "description": "是否显示已完成的待办，默认否"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_tasks",
            "description": "获取今天的待办事项。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_idea",
            "description": "将用户的创意想法进行结构化分析后保存。当用户提出一个创意/想法/点子并且你已经完成分析后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "创意标题（简短概括）"},
                    "summary": {"type": "string", "description": "创意概述（2-3句话）"},
                    "requirements": {"type": "string", "description": "需求分析（列出核心需求点）"},
                    "plan": {"type": "string", "description": "实施方案（分步骤的行动计划）"},
                    "risks": {"type": "string", "description": "潜在风险与挑战"},
                },
                "required": ["title", "summary", "requirements", "plan"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_ideas",
            "description": "列出所有保存过的创意。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_idea",
            "description": "查看某个创意的完整分析详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_id": {"type": "integer", "description": "创意 ID"},
                },
                "required": ["idea_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_idea_status",
            "description": "更新创意的状态（draft/in_progress/done/abandoned）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_id": {"type": "integer", "description": "创意 ID"},
                    "status": {
                        "type": "string",
                        "enum": ["draft", "in_progress", "done", "abandoned"],
                        "description": "新状态",
                    },
                },
                "required": ["idea_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_idea",
            "description": "删除一个创意。",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_id": {"type": "integer", "description": "创意 ID"},
                },
                "required": ["idea_id"],
            },
        },
    },
    # ── 系统操作工具 ──
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "用默认浏览器打开网址。当用户说'打开某网站'、'帮我搜一下'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的网址"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "打开电脑上的应用程序。支持：记事本、计算器、画图、文件管理器、cmd、powershell、vscode，或直接输入程序名/路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "应用名称或路径"},
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "读取系统剪贴板中的文本内容。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_clipboard",
            "description": "将文本写入系统剪贴板（复制到剪贴板）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要复制的文本"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文件的文本内容。当用户说'看看这个文件'、'总结一下这个文档'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的完整路径"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建或覆写一个文本文件。当用户说'帮我写个脚本'、'保存到文件'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的完整路径"},
                    "content": {"type": "string", "description": "要写入的内容"},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出一个目录下的文件和文件夹。当用户说'看看这个文件夹里有什么'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "目录路径"},
                },
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "设置定时提醒。到时间后会弹出桌面通知。当用户说'提醒我'、'X分钟后提醒我'、'X点提醒我做某事'时使用。如果用户说'X分钟后'，你需要根据当前时间计算出目标时间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_str": {"type": "string", "description": "提醒时间，格式 HH:MM（24小时制），如 16:30。如果用户说'5分钟后'，你要用当前时间加上5分钟算出具体时间"},
                    "message": {"type": "string", "description": "提醒内容"},
                },
                "required": ["time_str", "message"],
            },
        },
    },
    # ── 技能工具 ──
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "列出所有可用的技能（Skill）。当用户询问'有哪些技能'、'你能做什么特殊任务'时使用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": "激活一个技能，使 Agent 获得该技能的专业流程指导。当用户的请求匹配某个技能的场景时主动激活。可用技能: document-to-action-items(从文档提取任务), weekly-review-planning(每周回顾与规划), humanizer(人性化文本去AI味)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deactivate_skill",
            "description": "停用当前激活的技能，恢复为通用模式。当技能任务完成后调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # ── 搜索工具 ──
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取信息。当用户询问你不确定的事实、想了解某个话题、或需要实时信息时使用。每次搜索只调用一次，不要重复搜索同一个话题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
            "description": "搜索最新新闻。当用户想了解某个话题的最新动态时使用。每次只调用一次。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "新闻关键词"},
                },
                "required": ["query"],
            },
        },
    },
]

# ── Skill 加载器 ──────────────────────────────────────────
_skill_loader = SkillLoader()
_active_skill: str | None = None


def _activate_skill(name: str) -> str:
    global _active_skill
    if not _skill_loader.has_skill(name):
        return f"[失败] 未找到技能: {name}。{_skill_loader.list_skills()}"
    _active_skill = name
    return f"[成功] 已激活技能: {name}"


def _deactivate_skill() -> str:
    global _active_skill
    if _active_skill is None:
        return "当前没有激活的技能。"
    old = _active_skill
    _active_skill = None
    return f"[成功] 已停用技能: {old}"


TOOL_MAP = {
    "save_memory": lambda args: save_memory(
        args["content"], args.get("category", "general"),
        project=args.get("project", ""),
    ),
    "search_memories": lambda args: json.dumps(search_memories(args.get("keyword", "")), ensure_ascii=False),
    "delete_memory": lambda args: delete_memory(args["memory_id"]),
    "update_memory": lambda args: update_memory(
        args["memory_id"],
        content=args.get("content"),
        category=args.get("category"),
        project=args.get("project"),
    ),
    "list_memories": lambda args: list_memories(
        category=args.get("category", ""),
        project=args.get("project", ""),
        status=args.get("status", "active"),
    ),
    "get_memory_history": lambda args: get_memory_history(args["memory_id"]),
    "add_task": lambda args: add_task(args["title"], args.get("due_date", ""), args.get("due_time", ""), args.get("priority", "normal")),
    "complete_task": lambda args: complete_task(args["task_id"]),
    "delete_task": lambda args: delete_task(args["task_id"]),
    "list_tasks": lambda args: list_tasks(args.get("show_done", False)),
    "get_today_tasks": lambda _: get_today_tasks(),
    "save_idea": lambda args: save_idea(args["title"], args["summary"], args["requirements"], args["plan"], args.get("risks", "")),
    "list_ideas": lambda _: list_ideas(),
    "get_idea": lambda args: get_idea(args["idea_id"]),
    "update_idea_status": lambda args: update_idea_status(args["idea_id"], args["status"]),
    "delete_idea": lambda args: delete_idea(args["idea_id"]),
    "open_url": lambda args: open_url(args["url"]),
    "open_application": lambda args: open_application(args["app_name"]),
    "read_clipboard": lambda _: read_clipboard(),
    "write_clipboard": lambda args: write_clipboard(args["text"]),
    "read_file": lambda args: read_file(args["file_path"]),
    "write_file": lambda args: write_file(args["file_path"], args["content"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "set_reminder": lambda args: set_reminder(args["time_str"], args["message"]),
    "web_search": lambda args: web_search(args["query"], args.get("max_results", 5)),
    "news_search": lambda args: news_search(args["query"], args.get("max_results", 5)),
    "list_skills": lambda _: _skill_loader.list_skills(),
    "activate_skill": lambda args: _activate_skill(args["name"]),
    "deactivate_skill": lambda _: _deactivate_skill(),
}


def execute_tool(name: str, arguments: str) -> str:
    try:
        if not is_tool_allowed(name):
            return f"权限不足: {name} 功能已被禁用，请在设置中开启对应权限。"
        args = json.loads(arguments) if arguments else {}
        # 优先检查本地工具
        if name in TOOL_MAP:
            return str(TOOL_MAP[name](args))
        # 再检查 MCP 工具
        if mcp_is_tool(name):
            return mcp_call_tool(name, args)
        return f"未知工具: {name}"
    except Exception as e:
        return f"工具执行出错: {e}"


def get_allowed_tools() -> list:
    """返回当前权限下可用的工具列表（含 MCP 工具）。"""
    blocked = get_blocked_tools()
    local_tools = [t for t in TOOLS if t["function"]["name"] not in blocked]
    mcp_tools = mcp_get_tools()
    return local_tools + mcp_tools


# ── System Prompt ─────────────────────────────────────────

def build_system_prompt(user_query: str = "") -> str:
    now = datetime.now()
    today = now.strftime("%Y年%m月%d日 %A")
    current_time = now.strftime("%H:%M")
    memory_context = format_memories_for_prompt(query=user_query)

    prompt = f"""你是一个智能个人助理 Agent。今天是 {today}，当前时间是 {current_time}。

你的职责：
1. 根据用户的生活习惯，帮助安排日常事务
2. 当用户有创意想法时，帮助分析需求、提供方案
3. 主动记住用户提到的习惯、偏好和重要信息
4. 帮用户执行实际操作：打开网页/应用、读写文件、操作剪贴板
5. 帮用户搜索信息：使用 mcp_fetch_fetch 抓取网页获取信息

工具使用规则：
- 当用户提到自己的习惯/偏好/个人信息/目标/决策时，用 save_memory 保存（系统会自动去重）
- 当用户要求修改已有记忆时，用 update_memory 更新（会自动保留版本历史）
- 当用户要求查看记忆列表时，用 list_memories 筛选；查看记忆变更历史用 get_memory_history
- 记忆分类包括: habit(习惯), preference(偏好), info(信息), goal(目标), decision(决策), event(事件), feedback(反馈)
- 记忆中标注"待确认"的内容是系统自动推断的，需要你在合适时机向用户确认
- 当用户要求添加待办/日程时，用 add_task 添加。务必将时间信息拆分到 due_date 和 due_time 字段，不要把时间写进 title 里。例如用户说"今天下午3点开会"，title="开会"，due_date=今天日期，due_time="15:00"
- 当用户询问安排时，用 list_tasks 或 get_today_tasks 查看
- 当用户说"打开XX"时，判断是网站还是应用，调用 open_url 或 open_application
- 当用户要求读取/创建文件时，使用 read_file / write_file
- 当用户要求复制内容或读取剪贴板时，使用 write_clipboard / read_clipboard
- 当用户说"提醒我"、"定个闹钟"时，使用 set_reminder 设置定时提醒
- 当用户要求搜索信息/新闻时，用 mcp_fetch_fetch 抓取搜索引擎页面。方法：构造 Bing 搜索 URL 如 https://cn.bing.com/search?q=关键词 ，用 mcp_fetch_fetch 抓取，max_length 设为 3000。只需要搜索一次，将结果总结给用户即可，不要反复搜索
- 你必须严格根据工具的返回结果回复用户。如果工具返回包含"[失败]"或"权限不足"或"出错"，你必须如实告知用户操作失败以及原因，绝对不能编造"已成功"
- 如果工具返回包含"[成功]"，才能告诉用户操作成功
- 回复时自然地融入工具结果，不要暴露工具调用细节

创意分析规则：
当用户提出一个创意/想法/点子时，按以下结构进行分析：
1. 先理解用户的核心诉求，必要时追问细节
2. 从以下维度分析：
   - 概述：用 2-3 句话概括这个创意
   - 需求分析：拆解核心需求，列出必须实现的功能点
   - 实施方案：给出分步骤的行动计划，每步要具体可执行
   - 风险与挑战：指出可能遇到的问题和应对建议
3. 分析完成后，用 save_idea 保存结构化结果
4. 如果用户同意推进，主动将方案中的步骤拆成 add_task 待办事项

沟通风格：简洁、有条理、直击重点、主动提建议。"""

    if memory_context:
        prompt += f"\n\n{memory_context}"

    if _active_skill:
        skill_prompt = _skill_loader.get_skill_prompt(_active_skill)
        if skill_prompt:
            prompt += skill_prompt

    return prompt


# ── Agent 引擎 ────────────────────────────────────────────

CHAT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "chat_history.json")


class AgentEngine:
    """Agent 核心引擎，管理对话状态，支持流式和非流式输出。"""

    def __init__(self):
        self.messages = [{"role": "system", "content": build_system_prompt()}]
        self.display_messages = []  # 用于 UI 显示的 (role, content) 列表
        self._load_history()

    def clear(self):
        self.messages = [{"role": "system", "content": build_system_prompt()}]
        self.display_messages = []
        self._save_history()

    def _history_path(self):
        os.makedirs(os.path.dirname(CHAT_HISTORY_FILE), exist_ok=True)
        return CHAT_HISTORY_FILE

    def _save_history(self):
        data = {
            "date": date.today().isoformat(),
            "display_messages": self.display_messages,
        }
        with open(self._history_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_history(self):
        path = self._history_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 只加载今天的历史，隔天自动清空
            if data.get("date") != date.today().isoformat():
                return
            self.display_messages = data.get("display_messages", [])
            # 重建 messages 上下文（最近几轮，避免 token 过多）
            for role, content in self.display_messages[-10:]:
                self.messages.append({"role": role, "content": content})
        except Exception:
            pass

    def get_display_messages(self) -> list:
        return self.display_messages

    def chat_stream(self, user_input: str):
        """流式对话。yield 三种事件：
        - ("tool", tool_name)        工具被调用
        - ("token", text)            流式文本片段
        - ("done", full_reply)       回复结束
        - ("error", error_msg)       出错
        - ("compressed", msg)        对话被压缩
        """
        # 根据用户输入检索相关记忆
        self.messages[0] = {"role": "system", "content": build_system_prompt(user_input)}
        self.messages.append({"role": "user", "content": user_input})
        self.display_messages.append(("user", user_input))

        tool_round = 0
        allowed_tools = get_allowed_tools()
        while True:
            # 先尝试非流式处理工具调用
            try:
                request_kwargs = {
                    "model": MODEL,
                    "messages": self.messages,
                    "temperature": 0.8,
                    "stream": False,
                }
                if allowed_tools:
                    request_kwargs["tools"] = allowed_tools
                response = client.chat.completions.create(**request_kwargs)
            except Exception as e:
                self.messages.pop()
                yield ("error", str(e))
                return

            choice = response.choices[0]

            # 如果模型要调用工具
            if choice.message.tool_calls:
                tool_round += 1
                self.messages.append(choice.message)
                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = tool_call.function.arguments
                    yield ("tool", fn_name)
                    result = execute_tool(fn_name, fn_args)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                if tool_round >= MAX_TOOL_ROUNDS:
                    self.messages.append({"role": "user", "content": "[系统提示: 工具调用次数已达上限，请根据已获取的信息直接回复用户。]"})
                continue

            # 没有工具调用，用流式输出生成回复
            break

        # 流式请求最终回复
        try:
            stream_kwargs = {
                "model": MODEL,
                "messages": self.messages,
                "temperature": 0.8,
                "stream": True,
            }
            if allowed_tools:
                stream_kwargs["tools"] = allowed_tools
            stream = client.chat.completions.create(**stream_kwargs)
        except Exception as e:
            yield ("error", str(e))
            return

        full_reply = ""
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                full_reply += delta.content
                yield ("token", delta.content)

        self.messages.append({"role": "assistant", "content": full_reply})
        self.display_messages.append(("assistant", full_reply))
        self._save_history()

        # 刷新 system prompt
        self.messages[0] = {"role": "system", "content": build_system_prompt(user_input)}

        # 对话压缩
        token_est = estimate_tokens(self.messages)
        if token_est > MAX_TOKENS_BEFORE_COMPRESS:
            old_len = len(self.messages)
            self.messages = compress_messages(client, MODEL, self.messages)
            if len(self.messages) < old_len:
                yield ("compressed", f"{old_len}条 -> {len(self.messages)}条")

        # 对话后异步记忆提取（后台线程，不阻塞）
        from settings import get_permission
        if get_permission("auto_save_memory"):
            extract_memories_async(client, MODEL, list(self.messages))

        yield ("done", full_reply)
