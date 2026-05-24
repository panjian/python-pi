import os
import re
import subprocess
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse, unquote
import xml.etree.ElementTree as ET

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
        # 基于正则的高危命令拦截，避免子串误匹配
        forbidden_patterns = [
            r'\brm\s+(-\w+\s+)*-rf\s*/\s*$',  # rm -rf / 或 rm -rf /path
            r'\brm\s+(-\w+\s+)*--no-preserve-root',  # --no-preserve-root
            r'\bmkfs\b',           # 磁盘格式化
            r'\bdd\s',             # dd if=/dev/... (word-boundary, 不影响 git add 等)
            r'\bsudo\s+reboot\b',   # 重启
            r'\bsudo\s+halt\b',     # 关机
        ]
        for pattern in forbidden_patterns:
            if re.search(pattern, command):
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

    def web_search(self, query: str, engine: str = "duckduckgo", num_results: int = 10) -> str:
        """使用网页搜索引擎搜索信息，无需API key。支持 duckduckgo, bing, google, baidu 等引擎。"""
        engine = engine.lower()
        supported_engines = ["duckduckgo", "bing", "google", "baidu"]
        if engine not in supported_engines:
            return f"Error: Unsupported search engine '{engine}'. Supported engines: {', '.join(supported_engines)}"

        if not query or len(query.strip()) == 0:
            return "Error: Query cannot be empty."

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

            results = []

            if engine == "duckduckgo":
                # DuckDuckGo HTML version - uses POST
                search_url = "https://html.duckduckgo.com/html/"
                data = {"q": query}
                response = requests.post(search_url, data=data, headers=headers, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                for a_tag in soup.select('a.result__a'):
                    url = a_tag.get('href', '')
                    title = a_tag.get_text(strip=True)
                    if not title:
                        continue

                    # DDG uses a redirect URL; extract the actual URL
                    if url.startswith('/'):
                        from urllib.parse import parse_qs
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        if 'uddg' in params:
                            url = unquote(params['uddg'][0])

                    # Find snippet
                    snippet_tag = a_tag.find_next_sibling('a', class_='result__snippet')
                    snippet = ""
                    if snippet_tag:
                        snippet = snippet_tag.get_text(strip=True)
                    else:
                        # Alternative: find via result class
                        result_div = a_tag.find_parent('.result')
                        if result_div:
                            snip = result_div.select_one('.result__snippet')
                            if snip:
                                snippet = snip.get_text(strip=True)

                    if url and title:
                        results.append({"title": title, "url": url, "snippet": snippet})
                        if len(results) >= num_results:
                            break

            elif engine == "bing":
                # Bing RSS format - returns structured XML with title/link/description
                encoded_query = quote(query)
                search_url = f"https://www.bing.com/search?format=rss&q={encoded_query}&count={num_results}"
                response = requests.get(search_url, headers=headers, timeout=15)
                response.raise_for_status()

                root = ET.fromstring(response.text)
                for item in root.findall('.//item')[:num_results]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    desc = item.find('description').text if item.find('description') is not None else ""
                    if title and link:
                        results.append({"title": title, "url": link, "snippet": desc})

            elif engine == "google":
                encoded_query = quote(query)
                search_url = f"https://www.google.com/search?q={encoded_query}&num={num_results}&hl=zh-CN"
                response = requests.get(search_url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                for a_tag in soup.select('a[href]'):
                    href = a_tag.get('href', '')
                    text = a_tag.get_text(strip=True)
                    if '/url?q=' in href:
                        actual_url = href.split('/url?q=')[1].split('&')[0]
                        actual_url = unquote(actual_url)
                        if text and len(text) > 10:
                            results.append({"title": text[:150], "url": actual_url, "snippet": ""})
                            if len(results) >= num_results:
                                break

            elif engine == "baidu":
                encoded_query = quote(query)
                search_url = f"https://www.baidu.com/s?wd={encoded_query}&rn={num_results}"
                response = requests.get(search_url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                for a_tag in soup.select('a[href]'):
                    href = a_tag.get('href', '')
                    text = a_tag.get_text(strip=True)
                    if href and text and len(text) > 10:
                        results.append({"title": text[:150], "url": href, "snippet": ""})
                        if len(results) >= num_results:
                            break

            if not results:
                return f"No results found for query: '{query}' on {engine}."

            # 去重
            seen_urls = set()
            unique_results = []
            for r in results:
                if r['url'] not in seen_urls:
                    seen_urls.add(r['url'])
                    unique_results.append(r)

            # 格式化输出
            output = f"Search results for '{query}' on {engine}:\n\n"
            for i, r in enumerate(unique_results, 1):
                output += f"{i}. {r['title']}\n"
                output += f"   URL: {r['url']}\n"
                if r.get('snippet'):
                    output += f"   Summary: {r['snippet'][:200]}\n"
                output += "\n"

            return output

        except requests.exceptions.Timeout:
            return f"Error: Search request to {engine} timed out."
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to search on {engine}: {str(e)}"
        except Exception as e:
            return f"Error during search: {str(e)}"

    def web_fetch(self, url: str, max_length: int = 10000) -> str:
        """获取指定URL的网页内容，返回提取的文本内容。"""
        if not url or not url.startswith(('http://', 'https://')):
            return "Error: Invalid URL. URL must start with http:// or https://"
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # 检测编码
            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除脚本和样式元素
            for script in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                script.decompose()
            
            # 获取标题
            title = soup.title.string.strip() if soup.title and soup.title.string else urlparse(url).netloc
            
            # 提取文本内容
            text = soup.get_text(separator='\n', strip=True)
            
            # 清理多余空行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            # 限制返回长度
            if len(cleaned_text) > max_length:
                cleaned_text = cleaned_text[:max_length] + f"\n\n... [Content truncated, total length: {len(soup.get_text())} chars]"
            
            return f"=== Page: {title} ===\nURL: {url}\n\n{cleaned_text}"
            
        except requests.exceptions.Timeout:
            return f"Error: Request to {url} timed out."
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to fetch {url}: {str(e)}"
        except Exception as e:
            return f"Error during fetch: {str(e)}"

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
            },
            {
                "name": "web_search",
                "description": "Search the web using search engines (duckduckgo, bing, google, baidu) without API key. Returns search results with titles, URLs, and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query string"},
                        "engine": {"type": "string", "description": "Search engine to use: 'duckduckgo', 'bing', 'google', or 'baidu'. Default is 'duckduckgo'.", "enum": ["duckduckgo", "bing", "google", "baidu"]},
                        "num_results": {"type": "integer", "description": "Number of results to return. Default is 10."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "web_fetch",
                "description": "Fetch and extract the text content of a web page from a given URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to fetch (must start with http:// or https://)"},
                        "max_length": {"type": "integer", "description": "Maximum length of returned content. Default is 10000."}
                    },
                    "required": ["url"]
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