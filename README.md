# Python-PI Coding Agent 完全使用与全平台部署手册

本项目是一个轻量级的 AI 编码智能体（Coding Agent）。系统通过自主执行 **ReAct (Reasoning and Acting)** 循环，能够实现自动探索目录、读写代码、局部修补（Patch）以及运行终端测试命令。项目原生支持 OpenAI 与 Anthropic 双模驱动，并兼容自定义中转网关。

---

## 🎯 第一部分：本地环境快速初始化

### 1. 创建或clone项目目录
打开终端，创建并进入项目核心工作区：
```bash
mkdir python-pi
cd python-pi
```

### 2. 部署 Python 3.14 虚拟环境
为了确保版本隔离，使用 Windows 的 `py` 启动器强行指定全新的 Python 3.14 版本来构建虚拟环境：
```powershell
# 检查当前系统支持的 Python 版本列表
py --list

# 强行指定 3.14 版本创建虚拟环境（大于3.10的版本都可以使用，这里以3.14为例）
py -3.14 -m venv venv
```

**激活虚拟环境：**
* **Windows (PowerShell/CMD):**
    ```powershell
    venv\Scripts\activate
    ```
* **macOS / Linux:**
    ```bash
    source venv/bin/activate
    ```

### 3. 安装核心依赖
在激活的虚拟环境中升级包管理工具并安装依赖：
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 环境变量配置 (`.env`)
在项目根目录下创建一个名为 `.env` 的文件，根据你倾向使用的模型供应商填入对应的密钥。系统会自动读取此文件：

```env
# 核心切换开关：可选 openai 或 anthropic
LLM_PROVIDER=openai

# OpenAI 模式配置 (支持官方或标准兼容中转站)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=[https://api.your-proxy-domain.com/v1](https://api.your-proxy-domain.com/v1)

# Anthropic 模式配置
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_BASE_URL=[https://api.your-anthropic-proxy.com](https://api.your-anthropic-proxy.com)
```

### 5. 启动与基础测试
在当前项目目录下，直接运行主入口文件进入交互式 TUI 界面：
```bash
python cli.py
```

---

## 🚀 第二部分：智能体能力验证（推荐测试指令）

进入系统后，你可以依次向 Agent 复制并发送以下任务，观察它是如何**进行工具链组合**、**自主执行**以及**报错自我修复**的：

* **🧪 任务一：创建基础代码（文件写入测试）**
    > **User:** 请帮我本地写一个简单的 python 数学计算脚本 `utils.py`，里面包含加减乘除四个函数。
* **🧪 任务二：编写测试并执行（命令调度验证）**
    > **User:** 帮我在本地再写一个包含 pytest 的单元测试文件 `test_utils.py`，并帮我运行 pytest 看看能不能全部通过。
* **🧪 任务三：局部修复与回归测试 (Auto-healing 模拟)**
    > **User:** 修改 `utils.py` 里面的除法函数，如果除数为 0，需要 `raise ValueError("Cannot divide by zero")`。改完之后再帮我跑一下测试确认安全。

---

## 🛠️ 第三部分：全平台全局快捷命令 (`pi`) 配置

配置完成后，你可以彻底脱离源码目录的束缚。在电脑的**任何代码文件夹**下，只需输入短命令 `pi`，就能瞬间唤醒智能体对当前目录进行一键 Debug 和编码。

### 💻 Windows 环境配置 (PowerShell / CMD)
*假设你的 Agent 源码和虚拟环境存放在：`C:\Users\cspan\python-pi`*

1.  **创建快捷批处理：**
    在 `C:\Users\cspan\python-pi` 目录下新建一个名为 **`pi.bat`** 的文本文件，写入以下内容：
    ```batch
    @echo off
    "C:\Users\cspan\python-pi\venv\Scripts\python.exe" "C:\Users\cspan\python-pi\cli.py" %*
    ```
2.  **配置系统 PATH 变量：**
    * 在 Windows 搜索框中输入 **“环境变量”**，选择 **“编辑系统环境变量”**。
    * 点击右下角的 **“环境变量”**。
    * 在“用户变量”或“系统变量”列表中双击打开 **`Path`**。
    * 点击右侧的 **“新建”**，将 `pi.bat` 所在的文件夹路径（`C:\Users\cspan\python-pi`）粘贴进去。
    * 一路点击 **“确定”** 保存关闭所有窗口。
3.  **使用验证：**
    关闭所有旧终端，打开一个新的 PowerShell，`cd` 到任何全新的项目目录运行：
    ```powershell
    cd D:\your-other-project
    pi
    ```

### 🍏 macOS / Linux 环境配置 (Zsh)
*假设你的 Agent 源码和虚拟环境存放在：`/Users/yourname/python-pi`*

1.  **写入终端别名 (Alias)：**
    打开 Mac 自带的终端，通过命令行编辑器打开 Zsh 的配置文件：
    ```bash
    nano ~/.zshrc
    ```
2.  **粘贴全局映射：**
    使用方向键滑到文件最底部，粘贴以下命令（务必替换为你 Mac 上的实际绝对路径）：
    ```bash
    alias pi="/Users/yourname/python-pi/venv/bin/python /Users/yourname/python-pi/cli.py"
    ```
3.  **保存并退出：**
    * 按下 `Ctrl + O`，再按下 `Enter` 键保存。
    * 按下 `Ctrl + X` 退出 nano 编辑器。
4.  **激活配置并验证：**
    运行以下命令刷新当前终端，随后即可在任意目录下全局高呼 `pi` 唤醒 Agent：
    ```bash
    source ~/.zshrc
    cd ~/Documents/my-web-app
    pi
    ```

---

## 🎯 第四部分：底层架构与核心机制说明

1.  **优雅的免激活环境切换**
    本系统采用 Unix/Windows 标准的**隐式虚拟环境调用逻辑**。当你通过快捷键使用绝对路径（如 `venv/bin/python` 或 `venv\Scripts\python.exe`）去引导脚本时，操作系统在初始化进程时会自动将上下文沙箱锁定在该虚拟环境中。这意味着系统会自动加载该环境中已安装的依赖（如 `openai`, `rich` 等），**无需手动显式激活（source activate）**，从而实现了极致流畅的无缝切换。
2.  **全局密钥读取与本地上下文聚焦**
    在系统的核心层设计中，`config.py` 通过 `os.path.dirname(os.path.abspath(__file__))` 技术锁死了 `.env` 的读取路径，保证大模型密钥始终从安装根目录安全获取；而在 `tools.py` 的设计中，所有涉及文件列出（`list_dir`）、读写（`write_file`）以及命令执行（`execute_command`）的基础相对路径均被锚定为系统当前工作目录 `.`（Current Working Directory）。
    这带来了一个完美的解耦效果：**”配置和运行依赖锁在全局，而工具的枪口始终瞄准你当前打开终端的本地项目”**。

---

## 📱 第五部分：飞书机器人集成（手机端远程控制）

本项目使用飞书官方 SDK（`lark-oapi`）以 WebSocket 长连接模式远程指挥 Agent。WebSocket 模式**无需公网 IP 或域名**。

### 1. 飞书开放平台创建应用

1. 登录 [飞书开放平台](https://open.feishu.cn)，创建**企业自建应用**
2. 在应用后台 → **机器人** → 启用机器人能力
3. 在 **权限管理** 中，开通以下权限：
   - `im:message`（获取与发送单聊、群组消息）
   - `im:message:send_as_bot`（以机器人身份发消息）
4. 在 **事件与回调** → **事件订阅** 中：
   - 添加事件 `im.message.receive_v1`（接收消息）
   - **连接模式** 选择 **WebSocket 长连接**（不要选 HTTP 回调）
   - 启用”机器人被单独拉入群聊时接收消息”和”机器人被 @ 时接收消息”
5. 在 **凭证与基础信息** 中复制 `App ID`（`cli_xxx` 格式）和 `App Secret`

### 2. 配置 `.env`

在 `.env` 文件末尾追加以下配置：

```env
# 飞书机器人配置
FEISHU_APP_ID=cli_xxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# 允许的用户 open_id（逗号分隔，留空则允许所有人）
FEISHU_ALLOWED_USERS=ou_xxxx1,ou_xxxx2

# Agent 工作目录（默认当前目录）
FEISHU_WORKSPACE_DIR=.

# 单次任务最大步数，0 表示不限制（默认 30）
FEISHU_MAX_STEPS=0
```

### 3. 获取你的 `open_id`

`FEISHU_ALLOWED_USERS` 中的 `ou_xxxx` 是你的飞书用户 ID，获取方式：

**方法一：日志反查（最简单）**
1. 先把 `FEISHU_ALLOWED_USERS=` 留空
2. 启动 bot，在飞书 App 中给机器人发一条消息
3. 终端日志会打印发送者 ID：
   ```
   Received from ou_aBcDeFgHiJkLmNoP in oc_xxx...: 你好
   ```
4. 把 `ou_xxxx` 填入 `.env` 后重启即可

**方法二：API 查询**
```bash
# 先获取 token
curl -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H “Content-Type: application/json” \
  -d '{“app_id”:”cli_xxx”,”app_secret”:”xxx”}'

# 用 token 查询 open_id
curl -X GET “https://open.feishu.cn/open-apis/contact/v3/users/me” \
  -H “Authorization: Bearer <tenant_access_token>”
```

### 4. 启动飞书 Bot

```bash
python feishu_bot.py
```

启动后日志会显示：
```
Connecting to Feishu WebSocket: wss://open.feishu.cn/websocket/cli_xxx...
Feishu WebSocket authenticated successfully
Feishu WebSocket subscribed to im.message.receive_v1
Starting Feishu bot (allowed users: {'ou_xxxx'})
```

之后在飞书 App 中给机器人发消息即可，例如：
> “帮我写一个 Python 快排算法并保存为 sort.py”
> “列出当前目录下的所有 Python 文件”
> “帮我查一下 requests 库的最新版本”

### 5. 配置说明

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `FEISHU_APP_ID` | 飞书应用 App ID | 必填 |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret | 必填 |
| `FEISHU_ALLOWED_USERS` | 允许使用的用户 open_id，逗号分隔 | 空（允许所有人） |
| `FEISHU_WORKSPACE_DIR` | Agent 执行操作的工作目录 | `.`（当前目录） |
| `FEISHU_MAX_STEPS` | 单次任务最大 ReAct 循环步数，`0` 表示不限制 | `30` |

### 6. 运行模式

飞书 Bot 与本地 TUI CLI **可以并行运行**，互不干扰：

```bash
# 终端 1：本地 TUI
python cli.py

# 终端 2：飞书 Bot
python feishu_bot.py
```

两者共享同一 `.env` 和代码库，但各自有独立的对话历史和 Agent 实例。飞书 Bot 支持多轮对话 — 同一个聊天会话内，Agent 会保留之前的上下文。