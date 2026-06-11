# YouAgent Code

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.0-orange?style=for-the-badge" alt="Version">
</p>

> A local-first, traceable Coding Agent Harness for developers.
>
> YouAgent focuses on making agentic coding workflows transparent, controllable and reusable: **Plan → Tool Use → Trace → Diff → Approval → Test → Report**.

**[中文版](./README_CN.md)** | **[English](./README.md)**

## Why YouAgent?

Modern coding agents are powerful, but many of them feel like black boxes. YouAgent is designed for developers who want to understand, extend and control the harness around the model.

- **Trace-first**: every task can write a readable trace with project profile, runtime events and final result.
- **Local-first**: inspect and operate on a local workspace with sandboxed file paths.
- **Tool-calling runtime**: built-in file, shell, search, JSON, browser and MCP-mounted tools.
- **Safe by default**: workspace boundary checks, shell policy checks and reversible workflow design.
- **Coding-agent mode**: scan a repository, ask questions, locate code and preserve task history.
- **MCP-ready**: mount external tools through Model Context Protocol.

## Quick Start

### Installation

```bash
git clone https://github.com/EmberRavager/youagent.git
cd youagent
pip install -e .
```

### Configuration

Create a `.env` file in your workspace or configure defaults:

```bash
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.openai.com/v1"
MINIMAX_API_KEY="your_api_key"
MINIMAX_BASE_URL="https://api.minimaxi.com/v1"
```

Optional default config:

```bash
youagent config --provider openai --model gpt-4.1-mini --api-key "sk-..."
```

## Coding Agent CLI

Initialize project context:

```bash
youagent-code init
```

Ask about the current repository:

```bash
youagent-code ask "What does this project do?"
youagent-code ask "Find the login flow and explain the key files."
youagent-code ask "Where should I add error handling for the auth API?"
```

Shorthand is also supported:

```bash
youagent-code "Explain the architecture of this repo"
```

View traces:

```bash
youagent-code trace last
youagent-code trace list
```

Generated files:

```text
.youagent/
├── project.json
└── runs/
    └── 20260611-120000-task.md
```

## Classic Agent Chat

You can still run the original interactive tool-using agent:

```bash
youagent chat --agent miniagent_like --provider minimax --model MiniMax-M2.5
```

## Web UI

```bash
youagent serve --host 0.0.0.0 --port 7788
# Open http://localhost:7788
```

Docker example:

```bash
docker run -d -p 8000:7788 -v $(pwd)/workspace:/workspace youagent
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `list_files` | List directory contents |
| `read_file` | Read text files with size limits |
| `write_file` | Write or create files |
| `run_shell` | Execute shell commands through security policy |
| `find_files` | Glob-style file search |
| `grep_text` | Regex text search |
| `fetch_url` | Fetch web page content |
| `read_json` / `write_json` | JSON operations |
| `playwright_browse` | Browser content extraction or screenshot capture |
| MCP tools | Mounted external tools through MCP config |

## Architecture

```text
src/mini_worker/
├── code_cli.py       # Coding Agent CLI: scan, ask, trace
├── agents.py         # Agent profiles and prompts
├── cli.py            # Classic CLI entry point
├── llm.py            # OpenAI-compatible LLM client
├── runtime.py        # Tool-calling loop
├── tools.py          # Built-in tool implementations
├── mcp.py            # MCP tool mounting
├── memory.py         # Session memory
├── tasking.py        # Scheduler
├── observability.py  # Events and metrics
└── server.py         # Web server and APIs
```

## Configuration Options

```bash
youagent-code ask "Analyze this repo" \
  --provider openai \
  --model gpt-4.1-mini \
  --workspace /path/to/repo \
  --session code \
  --timeout 60
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--provider` | LLM provider | configured default |
| `--model` | Model name | configured default |
| `--workspace` | Working directory | `.` |
| `--session` | Memory session ID | `code` |
| `--timeout` | LLM request timeout in seconds | `60` |
| `--mcp-config` | MCP server config path | - |
| `--no-trace` | Disable trace file output | `false` |

## Supported Providers

- OpenAI / OpenAI-compatible
- MiniMax
- Anthropic
- DeepSeek
- Gemini
- Grok
- OpenRouter
- Custom compatible endpoints

## Security

- Workspace sandbox for file operations
- Shell command filtering through `.mini_worker/security.json`
- URL fetch restrictions
- Traceable task execution
- Coding-agent prompt defaults to inspection before modification

## Observability

```bash
curl http://localhost:7788/api/events?limit=40
curl http://localhost:7788/api/metrics
```

Events are logged to:

```text
.mini_worker/observability/events.jsonl
```

## Roadmap

- Patch-first editing: generate diff before writing files
- Human approval flow for file writes and risky shell commands
- Playbook workflows: `fix-test`, `explain-project`, `review-pr`, `add-api`
- Richer codebase indexing and context compression
- Trace replay and shareable task reports

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [GitHub Repository](https://github.com/EmberRavager/youagent)
- [Report Issues](https://github.com/EmberRavager/youagent/issues)
