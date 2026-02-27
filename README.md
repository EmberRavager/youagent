<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YouAgent</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background: #fafafa; }
    h1, h2, h3 { margin-top: 1.5em; margin-bottom: 0.5em; }
    h1 { font-size: 2.5em; text-align: center; padding: 20px 0; }
    p, li { margin-bottom: 0.8em; }
    code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
    pre { background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto; }
    pre code { background: none; padding: 0; color: inherit; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 0.8em; margin: 2px; }
    .badge-blue { background: #e1ecf4; color: #0366d6; }
    .badge-green { background: #d4edda; color: #155724; }
    .badge-orange { background: #fff3cd; color: #856404; }
    .center { text-align: center; }
    table { width: 100%; border-collapse: collapse; margin: 1em 0; }
    th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
    th { background: #f4f4f4; }
    .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; }
    
    /* Tab Styles */
    .tab-container { margin-bottom: 20px; }
    .tab-buttons { display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; }
    .tab-btn { padding: 10px 30px; border: 2px solid #0366d6; background: white; color: #0366d6; font-size: 1em; cursor: pointer; border-radius: 25px; transition: all 0.3s; }
    .tab-btn:hover { background: #e1ecf4; }
    .tab-btn.active { background: #0366d6; color: white; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .tab-content h1 { font-size: 2em; }
  </style>
</head>
<body>

<div class="tab-container">
  <div class="tab-buttons">
    <button class="tab-btn active" onclick="switchTab('en')">English</button>
    <button class="tab-btn" onclick="switchTab('cn')">中文</button>
  </div>
</div>

<!-- English Version -->
<div id="en" class="tab-content active">

# YouAgent

<p class="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.0-orange?style=for-the-badge" alt="Version">
</p>

> 🤖 A lightweight AI agent framework with tool-calling capabilities, similar to Manus/miniagent style. Build your own AI assistant that can execute tasks autonomously.

## ✨ Features

- **🤝 Tool-Calling Agent** - Autonomous AI agent that calls tools to complete tasks
- **🛠️ Built-in Tools** - File operations, shell execution, web fetching, JSON handling
- **🌐 Web UI** - Modern chat interface with real-time streaming
- **💬 Multi-Agent Support** - Choose between `manus_like` (planning) or `miniagent_like` (direct execution)
- **🔌 Multi-Provider** - OpenAI, OpenRouter, MiniMax, Anthropic, DeepSeek, Gemini, Grok, and more
- **💾 Memory Persistence** - Session-based conversation memory
- **🔒 Security First** - Sandboxed tool execution with configurable policies
- **📅 Scheduler** - Automated task scheduling and execution
- **📊 Observability** - Event logging and metrics tracking
- **🎭 MCP Integration** - Model Context Protocol tool mounting

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/EmberRavager/youagent.git
cd youagent
pip install -e .
```

### Configuration

Create `.env` file:

```bash
# MiniMax Example
MINIMAX_API_KEY="your_api_key"
MINIMAX_BASE_URL="https://api.minimaxi.com/v1"

# Or OpenAI
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.openai.com/v1"
```

### Start Web UI

```bash
docker run -d -p 8000:7788 -v $(pwd)/workspace:/workspace youagent
# Open http://localhost:8000
```

Or without Docker:

```bash
youagent serve --host 0.0.0.0 --port 7788
```

### CLI Chat

```bash
youagent chat --agent miniagent_like --provider minimax --model MiniMax-M2.5
```

## 📖 Usage Examples

### Example 1: List Files and Read Content

```
User: "List current directory files and read README.md"
Agent: [automatically calls list_files → read_file]
→ Returns formatted results
```

### Example 2: Web Research

```
User: "Search for latest AI news and save to news.json"
Agent: [calls fetch_url → writes JSON]
→ Saves research results
```

### Example 3: Code Tasks

```
User: "Find all TODO comments in src/ and summarize"
Agent: [calls grep_text → analyzes results]
→ Returns summary
```

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `list_files` | List directory contents |
| `read_file` | Read text files (with size limit) |
| `write_file` | Write/create files |
| `run_shell` | Execute shell commands |
| `find_files` | Glob pattern file search |
| `grep_text` | Regex text search |
| `fetch_url` | Fetch web page content |
| `read_json` / `write_json` | JSON operations |

## 🏗️ Architecture

```
src/mini_worker/
├── agents.py       # Agent profiles & prompts
├── cli.py          # CLI entry point
├── llm.py          # LLM client (OpenAI-compatible)
├── runtime.py      # Tool-calling loop
├── server.py       # Web server & APIs
├── tools.py        # Tool implementations
├── memory.py       # Session memory
├── tasking.py      # Task scheduler
└── observability.py # Logging & metrics
```

## 🔧 Configuration Options

```bash
youagent serve \
  --agent miniagent_like \
  --provider minimax \
  --model MiniMax-M2.5 \
  --workspace /path/to/workdir \
  --session my_project \
  --timeout 60 \
  --scheduler
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--agent` | Agent type: `manus_like` or `miniagent_like` | `miniagent_like` |
| `--provider` | LLM provider | `minimax` |
| `--model` | Model name | `MiniMax-M2.5` |
| `--workspace` | Working directory | `.` |
| `--session` | Session ID for memory | `default` |
| `--timeout` | LLM request timeout (seconds) | `60` |
| `--scheduler` | Enable task scheduler | `false` |
| `--mcp-config` | MCP server config path | - |

## 🌐 Supported Providers

- OpenAI / OpenAI Compatible
- MiniMax
- Anthropic
- DeepSeek
- Gemini
- Grok
- OpenRouter
- Custom (any OpenAI-compatible API)

## 🔐 Security

- Sandboxed file operations (workspace boundary)
- Shell command filtering
- URL fetch restrictions
- Configurable security policies via `.mini_worker/security.json`

## 📊 Observability

```bash
# View events
curl http://localhost:7788/api/events?limit=40

# View metrics
curl http://localhost:7788/api/metrics
```

Events are logged to `.mini_worker/observability/events.jsonl`

## 📅 Scheduler

```bash
# Add scheduled task
youagent tasks add --name daily_report --prompt "Check repo status" --every 600

# List tasks
youagent tasks list

# Run once
youagent tasks run
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🔗 Links

- [GitHub Repository](https://github.com/EmberRavager/youagent)
- [Report Issues](https://github.com/EmberRavager/youagent/issues)

---

<p class="center">Made with ❤️ by <a href="mailto:emberravager@gmail.com">EmberRavager</a></p>

</div>

<!-- Chinese Version -->
<div id="cn" class="tab-content">

# YouAgent

<p class="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.0-orange?style=for-the-badge" alt="Version">
</p>

> 🤖 轻量级 AI Agent 框架，具有工具调用能力，类 Manus/miniagent 风格。构建你自己的 AI 助手，自主执行任务。

## ✨ 特性

- **🤝 工具调用 Agent** - 自主调用工具完成任务的 AI Agent
- **🛠️ 内置工具** - 文件操作、Shell 执行、网页抓取、JSON 处理
- **🌐 Web UI** - 现代聊天界面，支持实时流式输出
- **💬 多 Agent 支持** - 支持 `manus_like`（规划型）和 `miniagent_like`（执行型）
- **🔌 多 Provider** - OpenAI、OpenRouter、MiniMax、Anthropic、DeepSeek、Gemini、Grok 等
- **💾 记忆持久化** - 基于会话的对话记忆
- **🔒 安全优先** - 沙盒工具执行，可配置安全策略
- **📅 定时任务** - 自动化任务调度与执行
- **📊 可观测性** - 事件日志和指标追踪
- **🎭 MCP 集成** - Model Context Protocol 工具挂载

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/EmberRavager/youagent.git
cd youagent
pip install -e .
```

### 配置

创建 `.env` 文件：

```bash
# MiniMax 示例
MINIMAX_API_KEY="your_api_key"
MINIMAX_BASE_URL="https://api.minimaxi.com/v1"

# 或 OpenAI
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.openai.com/v1"
```

### 启动 Web UI

```bash
docker run -d -p 8000:7788 -v $(pwd)/workspace:/workspace youagent
# 打开 http://localhost:8000
```

或不使用 Docker：

```bash
youagent serve --host 0.0.0.0 --port 7788
```

### CLI 聊天

```bash
youagent chat --agent miniagent_like --provider minimax --model MiniMax-M2.5
```

## 📖 使用示例

### 示例 1：列出文件并读取内容

```
用户："列出当前目录文件并读取 README.md"
Agent：[自动调用 list_files → read_file]
→ 返回格式化结果
```

### 示例 2：网络研究

```
用户："搜索最新 AI 新闻并保存到 news.json"
Agent：[调用 fetch_url → 写 JSON]
→ 保存研究结果
```

### 示例 3：代码任务

```
用户："查找 src/ 中所有 TODO 注释并总结"
Agent：[调用 grep_text → 分析结果]
→ 返回总结
```

## 🛠️ 可用工具

| 工具 | 描述 |
|------|------|
| `list_files` | 列出目录内容 |
| `read_file` | 读取文本文件（带大小限制） |
| `write_file` | 写入/创建文件 |
| `run_shell` | 执行 Shell 命令 |
| `find_files` | Glob 模式文件搜索 |
| `grep_text` | 正则文本搜索 |
| `fetch_url` | 获取网页内容 |
| `read_json` / `write_json` | JSON 操作 |

## 🏗️ 架构

```
src/mini_worker/
├── agents.py       # Agent 配置和提示词
├── cli.py          # CLI 入口
├── llm.py          # LLM 客户端（OpenAI 兼容）
├── runtime.py      # 工具调用循环
├── server.py       # Web 服务器和 API
├── tools.py        # 工具实现
├── memory.py       # 会话记忆
├── tasking.py      # 任务调度
└── observability.py # 日志和指标
```

## 🔧 配置选项

```bash
youagent serve \
  --agent miniagent_like \
  --provider minimax \
  --model MiniMax-M2.5 \
  --workspace /path/to/workdir \
  --session my_project \
  --timeout 60 \
  --scheduler
```

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `--agent` | Agent 类型：`manus_like` 或 `miniagent_like` | `miniagent_like` |
| `--provider` | LLM 提供商 | `minimax` |
| `--model` | 模型名称 | `MiniMax-M2.5` |
| `--workspace` | 工作目录 | `.` |
| `--session` | 记忆会话 ID | `default` |
| `--timeout` | LLM 请求超时（秒） | `60` |
| `--scheduler` | 启用任务调度器 | `false` |
| `--mcp-config` | MCP 服务器配置路径 | - |

## 🌐 支持的 Provider

- OpenAI / OpenAI 兼容
- MiniMax
- Anthropic
- DeepSeek
- Gemini
- Grok
- OpenRouter
- 自定义（任何 OpenAI 兼容 API）

## 🔐 安全

- 沙盒文件操作（工作目录边界）
- Shell 命令过滤
- URL 抓取限制
- 通过 `.mini_worker/security.json` 配置安全策略

## 📊 可观测性

```bash
# 查看事件
curl http://localhost:7788/api/events?limit=40

# 查看指标
curl http://localhost:7788/api/metrics
```

事件日志保存在 `.mini_worker/observability/events.jsonl`

## 📅 定时任务

```bash
# 添加定时任务
youagent tasks add --name daily_report --prompt "检查仓库状态" --every 600

# 列出任务
youagent tasks list

# 执行一次
youagent tasks run
```

## 🤝 贡献

欢迎提交 Pull Request！

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 📝 许可证

MIT License - 查看 [LICENSE](LICENSE) 了解更多。

## 🔗 相关链接

- [GitHub 仓库](https://github.com/EmberRavager/youagent)
- [问题反馈](https://github.com/EmberRavager/youagent/issues)

---

<p class="center">由 <a href="mailto:emberravager@gmail.com">EmberRavager</a> ❤️ 开发</p>

</div>

<script>
function switchTab(lang) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(lang).classList.add('active');
  document.querySelector(`[onclick="switchTab('${lang}')"]`).classList.add('active');
}
</script>

</body>
</html>
