"""系统操作工具 - 让 Agent 有"手"，能实际操作电脑。"""

import os
import subprocess
import webbrowser
import threading
from datetime import datetime, timedelta


# ── 打开网页 / 应用程序 ───────────────────────────────────

def open_url(url: str) -> str:
    """用默认浏览器打开网址。"""
    try:
        webbrowser.open(url)
        return f"已打开: {url}"
    except Exception as e:
        return f"打开网页失败: {e}"


# Windows UWP 应用 URI 协议映射
_UWP_APPS = {
    "相机": "microsoft.windows.camera:",
    "camera": "microsoft.windows.camera:",
    "时钟": "ms-clock:",
    "闹钟": "ms-clock:",
    "clock": "ms-clock:",
    "alarm": "ms-clock:",
    "设置": "ms-settings:",
    "settings": "ms-settings:",
    "照片": "ms-photos:",
    "photos": "ms-photos:",
    "邮件": "mailto:",
    "mail": "mailto:",
    "天气": "msnweather:",
    "weather": "msnweather:",
    "日历": "outlookcal:",
    "calendar": "outlookcal:",
    "商店": "ms-windows-store:",
    "store": "ms-windows-store:",
    "地图": "bingmaps:",
    "maps": "bingmaps:",
    "截图": "ms-screenclip:",
    "snipping": "ms-screenclip:",
}

# 传统应用映射
_CLASSIC_APPS = {
    "记事本": "notepad",
    "notepad": "notepad",
    "计算器": "calc",
    "calculator": "calc",
    "画图": "mspaint",
    "paint": "mspaint",
    "文件管理器": "explorer",
    "explorer": "explorer",
    "cmd": "cmd",
    "终端": "cmd",
    "powershell": "powershell",
    "vscode": "code",
    "code": "code",
    "任务管理器": "taskmgr",
    "taskmgr": "taskmgr",
}


def open_application(app_name: str) -> str:
    """打开应用程序。支持传统应用和 Windows UWP 应用。"""
    name_lower = app_name.lower()

    # 先查 UWP 应用
    if name_lower in _UWP_APPS:
        uri = _UWP_APPS[name_lower]
        try:
            result = subprocess.run(
                f'start {uri}', shell=True,
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return f"[成功] 已打开: {app_name}"
            return f"[失败] 打开 {app_name} 失败: {result.stderr.strip()}"
        except Exception as e:
            return f"[失败] 打开 {app_name} 出错: {e}"

    # 再查传统应用
    cmd = _CLASSIC_APPS.get(name_lower, app_name)
    try:
        result = subprocess.run(
            cmd, shell=True,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return f"[成功] 已打开: {app_name}"
        # 有些应用启动后立即返回非零也是正常的，用 Popen 兜底
        subprocess.Popen(cmd, shell=True)
        return f"[成功] 已打开: {app_name}"
    except Exception as e:
        return f"[失败] 打开 {app_name} 出错: {e}"


# ── 定时提醒 ───────────────────────────────────────────────

_active_reminders = {}  # id -> timer
_reminder_callback = None  # 由 app.py 注入的回调函数


def set_reminder_callback(callback):
    """注入提醒触发时的回调函数（由 app.py 调用）。"""
    global _reminder_callback
    _reminder_callback = callback


def set_reminder(time_str: str, message: str) -> str:
    """设置定时提醒。time_str 格式为 HH:MM（24小时制）。"""
    try:
        target = datetime.strptime(time_str, "%H:%M").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day,
        )
        now = datetime.now()
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()

        import uuid
        reminder_id = f"r_{uuid.uuid4().hex[:8]}"

        def fire():
            if _reminder_callback:
                _reminder_callback(message, time_str)
            _active_reminders.pop(reminder_id, None)

        timer = threading.Timer(delay, fire)
        timer.daemon = True
        timer.start()
        _active_reminders[reminder_id] = timer

        minutes = int(delay // 60)
        if minutes >= 60:
            time_desc = f"{minutes // 60}小时{minutes % 60}分钟后"
        else:
            time_desc = f"{minutes}分钟后"

        return f"[成功] 已设置提醒: {time_str} - {message} ({time_desc}触发)"
    except ValueError:
        return f"[失败] 时间格式错误，请使用 HH:MM 格式（如 16:30）"
    except Exception as e:
        return f"[失败] 设置提醒失败: {e}"


def list_reminders() -> str:
    """列出所有活跃的提醒。"""
    if not _active_reminders:
        return "当前没有活跃的提醒。"
    lines = ["活跃的提醒:"]
    for rid in _active_reminders:
        lines.append(f"  - {rid}")
    return "\n".join(lines)


# ── 剪贴板 ────────────────────────────────────────────────

def read_clipboard() -> str:
    """读取剪贴板文本内容。"""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return f"剪贴板内容:\n{data}"
        except TypeError:
            return "剪贴板中没有文本内容。"
        finally:
            win32clipboard.CloseClipboard()
    except ImportError:
        # 降级方案：用 PowerShell
        try:
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            content = result.stdout.strip()
            return f"剪贴板内容:\n{content}" if content else "剪贴板为空。"
        except Exception as e:
            return f"读取剪贴板失败: {e}"


def write_clipboard(text: str) -> str:
    """将文本写入剪贴板。"""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return f"已复制到剪贴板 ({len(text)} 字)"
    except ImportError:
        try:
            result = subprocess.run(
                ["powershell", "-command", "Set-Clipboard", "-Value", text],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return f"[成功] 已复制到剪贴板 ({len(text)} 字)"
            return f"[失败] 写入剪贴板失败: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "[失败] 写入剪贴板超时"
        except Exception as e:
            return f"[失败] 写入剪贴板失败: {e}"


# ── 文件操作 ───────────────────────────────────────────────

def read_file(file_path: str) -> str:
    """读取本地文件内容。支持文本文件，返回前 5000 字。"""
    path = os.path.expanduser(file_path)
    if not os.path.exists(path):
        return f"文件不存在: {path}"
    if not os.path.isfile(path):
        return f"不是文件: {path}"
    # 检查文件大小
    size = os.path.getsize(path)
    if size > 10 * 1024 * 1024:
        return f"文件过大 ({size // 1024 // 1024}MB)，暂不支持读取超过 10MB 的文件。"
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read(5000)
            truncated = " (内容已截断)" if len(content) >= 5000 else ""
            return f"[成功] 文件: {path}{truncated}\n\n{content}"
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"[失败] 读取失败: {e}"
    return f"[失败] 无法读取: {path}，不是文本文件或编码不支持。"


def write_file(file_path: str, content: str) -> str:
    """创建或覆写文件。"""
    path = os.path.expanduser(file_path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已写入: {path} ({len(content)} 字)"
    except Exception as e:
        return f"写入失败: {e}"


def list_directory(dir_path: str) -> str:
    """列出目录内容。"""
    path = os.path.expanduser(dir_path)
    if not os.path.exists(path):
        return f"目录不存在: {path}"
    if not os.path.isdir(path):
        return f"不是目录: {path}"
    try:
        items = os.listdir(path)
        if not items:
            return f"目录为空: {path}"
        lines = [f"目录: {path} ({len(items)} 项)\n"]
        for item in sorted(items)[:50]:
            full = os.path.join(path, item)
            prefix = "[DIR] " if os.path.isdir(full) else "      "
            lines.append(f"  {prefix}{item}")
        if len(items) > 50:
            lines.append(f"\n  ... 还有 {len(items) - 50} 项未显示")
        return "\n".join(lines)
    except Exception as e:
        return f"列出目录失败: {e}"
