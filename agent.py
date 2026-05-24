import sys
import json
from openai import OpenAI
from anthropic import Anthropic
from config import settings
from tools import ToolEngine
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

class CodingAgent:
    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.tools = ToolEngine()
        self.history = []
        
        # 统一的 System Prompt 注入
        self.system_prompt = (
            "You are an elite software engineering agent with local workspace access.\n"
            "You can use tools to discover files, read/write/patch code, and execute bash commands.\n"
            "When fixing code, run relevant tests or execution commands to verify your changes.\n"
            "Be precise, and state your reasoning before calling tools."
        )

        if self.provider == "openai":
            if not settings.openai_api_key:
                console.print("[red]Error: OPENAI_API_KEY is not set.[/red]")
                sys.exit(1)
            
            # 优化：支持自定义 base_url
            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                client_kwargs["base_url"] = settings.openai_base_url
                console.print(f"[dim]ℹ OpenAI Base URL set to: {settings.openai_base_url}[/dim]")
                
            self.client = OpenAI(**client_kwargs)
            self.model = settings.openai_model
            self.history.append({"role": "system", "content": self.system_prompt})
            
        elif self.provider == "anthropic":
            if not settings.anthropic_api_key:
                console.print("[red]Error: ANTHROPIC_API_KEY is not set.[/red]")
                sys.exit(1)
                
            # 优化：支持自定义 base_url
            client_kwargs = {"api_key": settings.anthropic_api_key}
            if settings.anthropic_base_url:
                client_kwargs["base_url"] = settings.anthropic_base_url
                console.print(f"[dim]ℹ Anthropic Base URL set to: {settings.anthropic_base_url}[/dim]")
                
            self.client = Anthropic(**client_kwargs)
            self.model = settings.anthropic_model
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def step_openai(self) -> bool:
        """执行单步 OpenAI ReAct 循环 (增强防错版)"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=self.tools.get_openai_tools(),
                tool_choice="auto"
            )
        except Exception as api_err:
            console.print(f"[red]❌ API 调用失败，请检查中转 Base URL 或 API Key。[/red]")
            console.print(f"[red]错误详情: {api_err}[/red]")
            return False # 中断循环

        # 防御性编程：检查 response 是否拥有 choices 属性
        if not hasattr(response, 'choices'):
            console.print(Panel(
                f"中转接口返回了非标准数据，无法解析。\n原始返回内容: {response}", 
                title="[bold red]中转站网关错误[/bold red]", 
                border_style="red"
            ))
            return False

        msg = response.choices[0].message
        self.history.append(msg)

        if msg.content:
            console.print(Panel(Markdown(msg.content), title="[bold blue]Agent Thought[/bold blue]", border_style="blue"))

        if not msg.tool_calls:
            return False  # 没有工具调用，循环结束

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            console.print(f"[bold yellow]🔧 Tool Call (OpenAI):[/bold yellow] {name}({args})")
            
            # 【优化：加固工具执行】
            try:
                func = getattr(self.tools, name)
                observation = func(**args)
            except TypeError as te:
                observation = f"Error: Invalid arguments for tool '{name}'. {str(te)}. Please re-call the tool with all required arguments."
            except Exception as e:
                observation = f"Error executing tool '{name}': {str(e)}"
            
            console.print(Panel(observation, title="[bold green]Observation[/bold green]", border_style="green"))
            
            self.history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": observation
            })
        return True

    def step_anthropic(self) -> bool:
        """执行单步 Anthropic ReAct 循环"""
        # Anthropic 的 system prompt 需要作为独立参数传入
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.system_prompt,
            messages=self.history,
            tools=self.tools.get_anthropic_tools()
        )
        
        # 将本次的响应转化为 Anthropic 的 message 记录进历史
        # 兼容处理：Anthropic 需要保存完整的 content 数组（包含文本和 tool_use）
        self.history.append({"role": "assistant", "content": response.content})

        has_tool_use = False
        tool_requests = []

        for block in response.content:
            if block.type == "text":
                console.print(Panel(Markdown(block.text), title="[bold magenta]Agent Thought[/bold magenta]", border_style="magenta"))
            elif block.type == "tool_use":
                has_tool_use = True
                tool_requests.append(block)

        if not has_tool_use:
            return False

        tool_outputs = []
        for tool_use in tool_requests:
            name = tool_use.name
            args = tool_use.input
            
            console.print(f"[bold yellow]🔧 Tool Call (Claude):[/bold yellow] {name}({args})")
            
            # 【优化：加固工具执行】
            try:
                func = getattr(self.tools, name)
                observation = func(**args)
            except TypeError as te:
                observation = f"Error: Invalid arguments for tool '{name}'. {str(te)}. Please re-call the tool with all required arguments defined in the schema."
            except Exception as e:
                observation = f"Error executing tool '{name}': {str(e)}"
            
            console.print(Panel(observation, title="[bold green]Observation[/bold green]", border_style="green"))
            
            tool_outputs.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": observation
            })
        
        # Anthropic 的 tool 结果回复必须是 role='user' 且 content 为 tool_result 类型
        self.history.append({"role": "user", "content": tool_outputs})
        return True

    def _get_summary(self) -> str:
        """Extract the final text response (summary) from conversation history."""
        if self.provider == "openai":
            for msg in reversed(self.history):
                if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
                    return msg["content"]
        else:
            for msg in reversed(self.history):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in reversed(content):
                            if getattr(block, "type", None) == "text" and getattr(block, "text", "").strip():
                                return block.text
        return "(No text response)"

    def run(self, prompt: str, max_steps: int | None = None):
        """主运行循环：默认根据任务执行情况自然停止，可选设置 max_steps 作为安全上限"""
        if self.provider == "openai":
            self.history.append({"role": "user", "content": prompt})
        else:
            self.history.append({"role": "user", "content": [{"type": "text", "text": prompt}]})

        console.print(f"\n🚀 [bold cyan]Starting task:[/bold cyan] {prompt}")
        
        step = 0
        while True:
            step += 1
            if max_steps is None:
                console.print(f"\n[dim]=== Loop Step {step} ===[/dim]")
            else:
                console.print(f"\n[dim]=== Loop Step {step}/{max_steps} ===[/dim]")
            
            if self.provider == "openai":
                continue_loop = self.step_openai()
            else:
                continue_loop = self.step_anthropic()
                
            if not continue_loop:
                console.print("[bold green]🏁 Task finished by Agent successfully.[/bold green]")
                break

            if max_steps is not None and step >= max_steps:
                console.print("[red]⚠️ Reached configured max loop steps limit.[/red]")
                break
			
    def clear_history(self):
        """清空对话历史，但保留 System Prompt (OpenAI需要)"""
        if self.provider == "openai":
            self.history = [{"role": "system", "content": self.system_prompt}]
        else:
            # Anthropic 的 System Prompt 是在请求时单独传递的
            self.history = []
        return "Conversation history cleared."

    def get_config_info(self):
        """获取当前配置信息"""
        return {
            "Provider": self.provider.upper(),
            "Model": self.model,
            "Workspace": self.tools.workspace_dir,
            "History Length": len(self.history)
        }

    def get_tools_info(self):
        """获取可用工具列表"""
        return [t["name"] for t in self.tools.get_raw_schemas()]