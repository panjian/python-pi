import sys
from agent import CodingAgent
from session_manager import SessionManager
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

# 引入 prompt_toolkit 模块
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

console = Console()

# 定义 Claude Code 风格的斜杠命令
SLASH_COMMANDS = {
    "/help": "Show this help message",
    "/clear": "Clear the conversation history and start fresh",
    "/config": "Show current agent configuration",
    "/tools": "List all available tools",
    "/exit": "Exit the agent"
}

def print_help():
    table = Table(title="Available Slash Commands", show_header=False, box=None)
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="dim")
    for cmd, desc in SLASH_COMMANDS.items():
        table.add_row(cmd, desc)
    console.print(Panel(table, border_style="blue"))

def handle_slash_command(command: str, agent: CodingAgent, session_mgr: SessionManager = None) -> bool:
    """处理斜杠命令，返回 False 表示需要退出程序"""
    cmd = command.strip().lower()

    if cmd == "/exit":
        console.print("[yellow]Goodbye![/yellow]")
        if session_mgr:
            session_mgr.save_input(command, prefix="Command")
        return False

    elif cmd == "/help":
        print_help()

    elif cmd == "/clear":
        msg = agent.clear_history()
        console.print(f"[green]? {msg}[/green]")

    elif cmd == "/config":
        info = agent.get_config_info()
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="green")
        for k, v in info.items():
            table.add_row(k, str(v))
        console.print(Panel(table, title="Agent Configuration", border_style="cyan"))

    elif cmd == "/tools":
        tools = agent.get_tools_info()
        console.print("[bold cyan]Available Tools:[/bold cyan]")
        for t in tools:
            console.print(f"  [green]{t}[/green]")

    else:
        console.print(f"[red]Unknown command: {cmd}. Type /help for available commands.[/red]")

    # Record all slash commands (except /exit which is handled above)
    if session_mgr:
        session_mgr.save_input(command, prefix="Command")

    return True

def main():
    console.print("[bold purple]🤖 Mini Coding Agent (TUI Edition) 初始化中...[/bold purple]")
    try:
        session_mgr = SessionManager()
        agent = CodingAgent()
    except Exception as e:
        console.print(f"[red]Initialization Error: {e}[/red]")
        sys.exit(1)

    # Start one session file for this entire run
    session_mgr.start_session(agent.tools.workspace_dir)

    console.print(f"Current Provider: [bold green]{agent.provider.upper()}[/bold green] | Model: [green]{agent.model}[/green]\n")
    console.print("提示: 支持使用 [cyan]Tab[/cyan] 键补全斜杠命令。输入 [cyan]/help[/cyan] 查看所有命令。\n")

    # 配置自动补全器
    completer = WordCompleter(list(SLASH_COMMANDS.keys()), ignore_case=True)

    # 配置 Prompt 样式
    style = Style.from_dict({
        'prompt': 'ansicyan bold',
    })

    # 创建带历史记录的 Session
    session = PromptSession(completer=completer, style=style)

    while True:
        try:
            # 使用 HTML 格式化 prompt，使其更美观
            user_input = session.prompt(HTML('<b><ansicyan>? User:</ansicyan></b> ')).strip()

            if not user_input:
                continue

            # 拦截并处理斜杠命令
            if user_input.startswith('/'):
                should_continue = handle_slash_command(user_input, agent, session_mgr)
                if not should_continue:
                    break
                continue

            # Record user input in session
            session_mgr.save_input(user_input, prefix="User Input")

            # 执行正常对话和任务
            agent.run(user_input)

            # Save agent summary after task completes
            summary = agent._get_summary()
            session_mgr.save_summary(summary)

            print("\n" + "="*60 + "\n")

        except KeyboardInterrupt:
            # 处理 Ctrl+C
            console.print("\n[yellow]Task interrupted. Press Ctrl+D or type /exit to quit.[/yellow]")
        except EOFError:
            # 处理 Ctrl+D
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]An error occurred during execution: {e}[/red]")

if __name__ == "__main__":
    main()
