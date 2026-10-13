"""MCP 客户端 - 连接 MCP 服务器，获取工具并执行调用。

配置文件: data/mcp_servers.json
格式:
{
    "fetch": {
        "command": "python",
        "args": ["-m", "mcp_server_fetch"],
        "enabled": true
    },
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@anthropic-ai/mcp-server-brave-search"],
        "env": {"BRAVE_API_KEY": "xxx"},
        "enabled": true
    }
}
"""

import os
import json
import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "data", "mcp_servers.json")

# 默认配置
_DEFAULT_CONFIG = {
    "fetch": {
        "command": "python",
        "args": ["-m", "mcp_server_fetch"],
        "enabled": True,
    },
}


def _ensure_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)


def load_config() -> dict:
    _ensure_config()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    _ensure_config()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class MCPManager:
    """管理多个 MCP 服务器连接，提供统一的工具发现和调用接口。"""

    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}
        self._tool_map: dict[str, str] = {}  # tool_name -> server_name
        self._tools: list[dict] = []  # OpenAI function calling 格式的工具列表
        self._exit_stack: AsyncExitStack | None = None
        self._started = False

    async def start(self):
        """连接所有已启用的 MCP 服务器。"""
        if self._started:
            return
        config = load_config()
        self._exit_stack = AsyncExitStack()

        for name, srv_config in config.items():
            if not srv_config.get("enabled", True):
                continue
            try:
                await self._connect_server(name, srv_config)
            except Exception as e:
                print(f"[MCP] 连接 {name} 失败: {e}")

        self._started = True

    async def _connect_server(self, name: str, srv_config: dict):
        """连接单个 MCP 服务器并获取其工具列表。"""
        env = {**os.environ, **srv_config.get("env", {})}
        params = StdioServerParameters(
            command=srv_config["command"],
            args=srv_config.get("args", []),
            env=env,
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        read_stream, write_stream = stdio_transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        self._sessions[name] = session

        # 获取工具列表并转换为 OpenAI function calling 格式
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            tool_name = f"mcp_{name}_{tool.name}"
            self._tool_map[tool_name] = name

            # 转换为 OpenAI 格式
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
                },
            }
            self._tools.append(openai_tool)

        print(f"[MCP] {name}: 已连接，发现 {len(tools_result.tools)} 个工具")

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP 工具。"""
        server_name = self._tool_map.get(tool_name)
        if not server_name or server_name not in self._sessions:
            return f"[失败] MCP 工具 {tool_name} 不可用"

        # 从 tool_name 还原原始工具名
        prefix = f"mcp_{server_name}_"
        original_name = tool_name[len(prefix):]

        session = self._sessions[server_name]
        try:
            result = await session.call_tool(original_name, arguments)
            # 拼接所有内容
            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
                elif hasattr(content, "data"):
                    texts.append(f"[二进制数据: {len(content.data)} 字节]")
            return "[成功] " + "\n".join(texts) if texts else "[成功] 工具执行完毕"
        except Exception as e:
            return f"[失败] MCP 工具执行出错: {e}"

    def get_tools(self) -> list[dict]:
        """返回所有 MCP 工具的 OpenAI function calling 格式定义。"""
        return self._tools

    def is_mcp_tool(self, tool_name: str) -> bool:
        """判断是否是 MCP 工具。"""
        return tool_name in self._tool_map

    async def stop(self):
        """断开所有连接。"""
        if self._exit_stack:
            await self._exit_stack.aclose()
        self._sessions.clear()
        self._tool_map.clear()
        self._tools.clear()
        self._started = False


# ── 同步包装器（供 engine.py 使用）──────────────────────

_manager = MCPManager()
_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """获取或创建事件循环。"""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def mcp_start():
    """同步启动 MCP 管理器。"""
    loop = _get_loop()
    loop.run_until_complete(_manager.start())


def mcp_get_tools() -> list[dict]:
    """获取所有 MCP 工具定义。"""
    return _manager.get_tools()


def mcp_is_tool(tool_name: str) -> bool:
    """判断是否 MCP 工具。"""
    return _manager.is_mcp_tool(tool_name)


def mcp_call_tool(tool_name: str, arguments: dict) -> str:
    """同步调用 MCP 工具。"""
    loop = _get_loop()
    return loop.run_until_complete(_manager.call_tool(tool_name, arguments))


def mcp_stop():
    """同步停止 MCP 管理器。"""
    loop = _get_loop()
    loop.run_until_complete(_manager.stop())
