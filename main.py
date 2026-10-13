"""CLI 入口 - 命令行版个人助理，复用 engine.py。"""

from engine import AgentEngine


def chat():
    engine = AgentEngine()

    print("=" * 50)
    print("  个人助理 Agent - 终端版")
    print("  输入 'exit' 或 'quit' 退出")
    print("  输入 'clear' 清空对话历史")
    print("=" * 50)
    print()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("再见！")
            break
        if user_input.lower() == "clear":
            engine.clear()
            print("[对话已清空]\n")
            continue

        for event_type, data in engine.chat_stream(user_input):
            if event_type == "tool":
                print(f"  [调用工具: {data}]")
            elif event_type == "token":
                print(data, end="", flush=True)
            elif event_type == "done":
                print("\n")
            elif event_type == "error":
                print(f"\n[错误] {data}\n")
            elif event_type == "compressed":
                print(f"  [对话已压缩: {data}]\n")


if __name__ == "__main__":
    chat()
