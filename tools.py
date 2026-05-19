import os
import subprocess
import json

class ToolEngine:
    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = os.path.abspath(workspace_dir)

    def list_dir(self, path: str = ".") -> str:
        """列出目录下的所有文件和文件夹"""
        target_path = os.path.abspath(os.path.join(self.workspace_dir, path))
        if not target_path.startswith(self.workspace_dir):
            return "Error: Cannot access path outside workspace."
        try:
            items = os.listdir(target_path)
            return json.dumps({"files": items})
        except Exception as e:
            return f"Error: {str(e)}"

    def view_file(self, path: str, line_start: int = 1, line_end: int = 10000) -> str:
        """查看指定文件的指定行数内容，单次最多返回 10000 行"""
        max_lines = 10000
        full_path = os.path.abspath(os.path.join(self.workspace_dir, path))
        if not full_path.startswith(self.workspace_dir):
            return "Error: Access denied."
        if not os.path.exists(full_path):
            return f"Error: File {path} not found."
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start = max(1, line_start) - 1
            requested_end = max(line_start, line_end)
            end = min(total_lines, requested_end, start + max_lines)
            
            content = "".join(lines[start:end])
            return f"--- File: {path} (Lines {start+1}-{end} of {total_lines}, max {max_lines} lines per read) ---\n{content}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def write_file(self, path: str, content: str = None) -> str:
        """创建或完全覆盖一个文件"""
        # 哨兵检查：如果模型根本没传 content 参数 (None)，直接拒绝并给出严厉提示
        if content is None:
            return (
                "Error: Missing required argument 'content'. "
                "You successfully provided 'path', but the 'content' field cannot be null or omitted. "
                "Please rewrite the full report content inside the 'content' argument."
            )

        full_path = os.path.abspath(os.path.join(self.workspace_dir, path))
        if not full_path.startswith(self.workspace_dir):
            return "Error: Access denied."
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Success: Written {len(content)} characters to {path}."
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def patch_file(self, path: str, search: str, replace: str) -> str:
        """局部替换文件中的特定代码块"""
        full_path = os.path.abspath(os.path.join(self.workspace_dir, path))
        if not full_path.startswith(self.workspace_dir):
            return "Error: Access denied."
        if not os.path.exists(full_path):
            return f"Error: File {path} not found."
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if search not in content:
                return "Error: The search block was not found exactly in the file. Ensure indentation and line breaks match perfectly."
            
            new_content = content.replace(search, replace, 1)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return f"Success: Patched {path} successfully."
        except Exception as e:
            return f"Error patching file: {str(e)}"

    def execute_command(self, command: str) -> str:
        """在本地终端执行安全命令"""
        # 基础的高危操作拦截（生产环境需更严格）
        forbidden = ["rm -rf /", "mkfs", "dd"]
        if any(f in command for f in forbidden):
            return "Error: Command rejected due to security policy."
            
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, cwd=self.workspace_dir, timeout=30
            )
            stdout = result.stdout[:2000] + ("\n... [Truncated]" if len(result.stdout) > 2000 else "")
            stderr = result.stderr[:2000] + ("\n... [Truncated]" if len(result.stderr) > 2000 else "")
            return f"Exit Code: {result.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds."

    def get_raw_schemas(self):
        return [
            {
                "name": "list_dir",
                "description": "List files and directories in the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Relative path, default is '.'"}}
                }
            },
            {
                "name": "view_file",
                "description": "View content of a file within a specific line range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "line_start": {"type": "integer", "default": 1},
                        "line_end": {"type": "integer", "default": 10000}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or overwrite a file with full content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "content": {"type": "string", "description": "Full content of the file"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "patch_file",
                "description": "Replace a specific snippet of code in a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "search": {"type": "string", "description": "The exact code block to find"},
                        "replace": {"type": "string", "description": "The code block to replace with"}
                    },
                    "required": ["path", "search", "replace"]
                }
            },
            {
                "name": "execute_command",
                "description": "Run a terminal command (e.g., pytest, pip install, git status).",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "The bash command to run"}},
                    "required": ["command"]
                }
            }
        ]

    def get_openai_tools(self):
        return [{"type": "function", "function": schema} for schema in self.get_raw_schemas()]

    def get_anthropic_tools(self):
        anthropic_tools = []
        for schema in self.get_raw_schemas():
            tool = {
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["parameters"]
            }
            anthropic_tools.append(tool)
        return anthropic_tools