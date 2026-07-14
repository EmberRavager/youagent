# YouAgent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.0-orange?style=for-the-badge" alt="Version">
</p>

> 🤖 A lightweight AI agent framework with tool-calling capabilities, similar to Manus/miniagent style. Build your own AI assistant that can execute tasks autonomously.

**[中文版](./README_CN.md)** | **[English](./README.md)**

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

## 🛡️ YouAgent Guard (macOS MVP)

YouAgent Guard monitors AI-agent process trees for dangerous commands and potential credential exposure. It works with known agents such as Codex, Claude Code, Cursor, Aider, OpenCode, and user-defined agent processes.

> **MVP boundary:** this release observes newly started processes and can immediately alert or terminate them. It is not yet an Endpoint Security system extension and cannot guarantee pre-execution blocking or detect every file read.

### Watch running agents

```bash
# Alert only
youagent-guard watch

# Immediately stop newly detected high-risk processes
youagent-guard watch --action terminate

# Protect a custom agent process name or existing PID
youagent-guard watch --agent my-agent --pid 12345 --action terminate
```

### Launch an agent in protected mode

```bash
youagent-guard run --action terminate -- codex
youagent-guard run --action terminate -- python ./my_agent.py
```

Protected launch strips environment variables whose names look like API keys, tokens, secrets, passwords, private keys, or database credentials before the agent starts. Audit records are written to:

```text
~/.youagent-guard/audit.jsonl
```

Current detections include recursive deletion, destructive Git operations, privilege escalation, remote scripts piped to a shell, Docker/Kubernetes destructive commands, database destruction, protected credential paths, and secret-like values exposed in process arguments.

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

<p align="center">Made with ❤️ by <a href="mailto:emberravager@gmail.com">EmberRavager</a></p>
