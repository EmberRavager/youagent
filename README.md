# youagent

一个类似 Manus / miniagent 风格的轻量项目：

- 通过对话驱动 agent
- agent 可以自动调用本地工具帮你完成任务
- 支持两种风格：`manus_like`（更偏计划+分步）和 `miniagent_like`（更偏直接执行）

## Features

- Tool-calling 对话循环（OpenAI-compatible Chat Completions）
- 内置安全工具：
  - `list_files`
  - `read_file`
  - `write_file`
  - `run_shell`
  - `find_files`
  - `grep_text`
  - `fetch_url`
  - `read_json`
  - `write_json`
- 多 provider 配置：`openai` / `openrouter` / `minimax` / `custom`
- 支持 `.env` 自动加载（无需每次手动 `export`）
- 支持会话记忆持久化（多 session）
- 基础安全限制：
  - 工具默认限制在工作目录内
  - shell 拒绝明显危险命令
  - `fetch_url` 屏蔽高风险本地地址（如 `localhost`）
- CLI 交互式聊天

## Quick Start

```bash
cd /Users/ember/Desktop/youagent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

创建 `.env`（推荐）：

```bash
cat > .env <<'EOF'
MINIMAX_API_KEY="your_minimax_key"
# 可选覆盖（默认已内置）
# MINIMAX_BASE_URL="https://api.minimaxi.com/v1"
EOF
```

## 模型和 Key 配置

- `model` 配置：通过 `--model` 或环境变量脚本参数（如 `MW_MODEL`）设置。
- `key` 配置优先级：`--api-key` > provider 专属环境变量 > `OPENAI_API_KEY`。
- `minimax` 推荐：

```bash
export MINIMAX_API_KEY="your_minimax_key"
youagent serve --provider minimax --model MiniMax-M2.5
```

- 也可写入项目根目录 `.env`：

```bash
MINIMAX_API_KEY="your_minimax_key"
MINIMAX_BASE_URL="https://api.minimaxi.com/v1"
```

## Web 客户端

启动：

```bash
./start-web.sh
```

打开：`http://127.0.0.1:7788`

页面支持直接配置：

- `provider`（`openai/openrouter/minimax/custom`）
- `model`
- `base_url`
- `api_key`（可留空，优先使用 `.env`）

点击“应用模型配置”后立即生效。

或直接设置环境变量（OpenAI-compatible API）：

```bash
export OPENAI_API_KEY="your_key"
# 可选：兼容网关
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

## One-Click Start

项目根目录提供 `start.sh`，会自动：

- 创建虚拟环境（若不存在）
- 安装项目（editable）
- 启动 `youagent chat`

直接启动：

```bash
./start.sh
```

可通过环境变量覆盖默认参数：

```bash
MW_AGENT=manus_like MW_PROVIDER=minimax MW_MODEL=MiniMax-M2.5 MW_SESSION=project_a ./start.sh
```

启动聊天（OpenAI）：

```bash
youagent chat --agent manus_like --provider openai --model gpt-4.1-mini
```

Minimax（OpenAI 兼容模式）：

```bash
export MINIMAX_API_KEY="your_minimax_key"
youagent chat --agent miniagent_like --provider minimax --model MiniMax-M2.5
```

> 提示：`minimax` provider 下，`minmax` / `minimax2.5` / `m2.5` 会自动映射到 `MiniMax-M2.5`。

OpenRouter：

```bash
export OPENROUTER_API_KEY="your_openrouter_key"
youagent chat --agent miniagent_like --provider openrouter --model openai/gpt-4.1-mini
```

自定义网关（任何 OpenAI-compatible API）：

```bash
youagent chat --agent miniagent_like --provider custom --base-url https://your-gateway/v1 --api-key your_key --model your_model
```

输入 `exit` 或 `quit` 退出。

## CLI Options

```bash
youagent chat \
  --agent miniagent_like \
  --provider minimax \
  --model MiniMax-M2.5 \
  --workspace . \
  --session default
```

常用参数：

- `--agent`: `manus_like` 或 `miniagent_like`
- `--provider`: `openai` / `openrouter` / `minimax` / `custom`
- `--model`: 模型 ID
- `--api-key`: 直接传 key（会覆盖 env）
- `--base-url`: 自定义兼容网关地址
- `--timeout`: LLM 请求超时秒数
- `--workspace`: 工具可访问的工作目录
- `--session`: 会话 ID（用于持久记忆）
- `--no-memory`: 关闭记忆

## Memory

- 默认开启会话记忆，保存在 `./.mini_worker/sessions/<session>.json`
- 使用 `--session <name>` 切换会话上下文
- 使用 `--no-memory` 关闭持久记忆

示例：

```bash
youagent chat --agent manus_like --provider minimax --model MiniMax-M2.5 --session project_a
```

## Tools

- `list_files(path)`: 列出目录或文件
- `read_file(path, max_chars?)`: 读取文本文件
- `write_file(path, content, append?)`: 写入文本文件
- `run_shell(command, timeout?)`: 在工作目录执行 shell
- `find_files(path?, pattern, limit?)`: 按 glob 模式查找文件
- `grep_text(path?, pattern, include?, limit?)`: 正则搜索文本
- `fetch_url(url, timeout?, max_chars?)`: 抓取网页内容
- `read_json(path)`: 读取 JSON
- `write_json(path, data, indent?)`: 写入 JSON

## Example Dialog

用户：

```text
帮我列出当前目录，并读取 README.md 前 40 行
```

agent 会自动触发 `list_files` 和 `read_file`，然后汇总结果回复。

再比如：

```text
去联网查一下 MiniMax 文本模型列表，并保存到 models.json
```

agent 可能会组合调用 `fetch_url` + `write_json` 完成任务。

## Project Layout

```text
src/mini_worker/
  agents.py      # agent 角色与系统提示词
  cli.py         # CLI 入口
  llm.py         # OpenAI-compatible 客户端
  runtime.py     # 对话循环与工具调度
  tools.py       # 工具实现与安全策略
```

## Notes

- 这是一个“类似风格”的实用骨架，不是对 Manus 或 miniagent 的源码复刻。
- 你可以在 `src/mini_worker/tools.py` 继续扩展数据库、HTTP、GitHub、部署等工具。

## 联系方式

- 在杭州，有想招作者进去的联系邮箱：`emberravager@gmail.com`

## MCP Integration

You can mount MCP tools (stdio servers) with `--mcp-config`.

Example `mcp.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
      "cwd": ".",
      "startup_timeout": 15,
      "request_timeout": 60
    }
  ]
}
```

Run:

```bash
youagent chat --mcp-config ./mcp.json
youagent serve --mcp-config ./mcp.json
youagent heartbeat --mcp-config ./mcp.json --message "scan repo and summarize TODOs" --every 300 --count 1
```

Persist defaults:

```bash
youagent config --mcp-config ./mcp.json
youagent status
```

## Scheduler, Progress, Observability, Security, Playwright

### Scheduled tasks

Add task:

```bash
youagent tasks add \
  --name daily_report \
  --prompt "Check repo status and summarize TODOs" \
  --every 600 \
  --provider openai \
  --model gpt-4.1-mini
```

List/Delete:

```bash
youagent tasks list
youagent tasks delete --id <task_id>
```

Run due tasks once / start loop:

```bash
youagent tasks run
youagent tasks start --poll 5
```

### Task progress visualization

- Web dashboard: `http://127.0.0.1:7788/tasks.html`
- APIs:
  - `GET /api/tasks`
  - `GET /api/metrics`
  - `GET /api/events?limit=40`
  - `POST /api/tasks` (create)
  - `POST /api/tasks/delete` (delete)
  - `POST /api/tasks/run_due` (execute due tasks)

Start web with built-in scheduler:

```bash
youagent serve --scheduler
```

### Observability

- Event log: `.mini_worker/observability/events.jsonl`
- Metrics: `.mini_worker/observability/metrics.json`
- Runtime emits tool-step events (for progress tracking).

### Security policy

Create `.mini_worker/security.json` to override defaults:

```json
{
  "allow_shell": true,
  "blocked_shell_tokens": ["rm -rf /", "mkfs", "curl | sh"],
  "blocked_hosts": ["localhost", "127.0.0.1", "169.254.169.254"],
  "allowed_hosts": [],
  "max_shell_timeout": 60,
  "max_fetch_chars": 200000,
  "max_playwright_chars": 120000
}
```

### Playwright tool

Tool name: `playwright_browse`

- `action=content` : read visible text from page.
- `action=screenshot` : save screenshot into workspace.

Example prompt to agent:

```text
Use playwright_browse to open https://example.com and return main content.
```

For screenshot:

```text
Use playwright_browse with action=screenshot, url=https://example.com, path=artifacts/example.png
```

Note: Node.js + Playwright package must be installed for this tool.
