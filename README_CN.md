# YouAgent Code

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.0-orange?style=for-the-badge" alt="Version">
</p>

> 一个本地优先、可审计、可控的 Coding Agent Harness。
>
> YouAgent 不是黑盒代码助手，而是一个透明的 Agent 执行环境：**计划 → 工具调用 → 轨迹记录 → Diff 预览 → 用户确认 → 测试验证 → 报告总结**。

**[中文版](./README_CN.md)** | **[English](./README.md)**

## 为什么做 YouAgent？

现在很多 Coding Agent 很强，但也很像黑盒：它读了什么文件、为什么改这段代码、执行了什么命令、哪一步开始跑偏，用户不一定看得清楚。

YouAgent 的定位是：让开发者可以理解、二开和掌控模型外层的 Agent Harness。

- **Trace-first**：每次任务都可以生成可读的执行轨迹，记录项目画像、工具调用和最终结果。
- **Local-first**：围绕本地代码仓库工作，默认限制在 workspace 内。
- **Tool-calling runtime**：内置文件、Shell、搜索、JSON、浏览器和 MCP 工具挂载能力。
- **Safe by default**：路径边界检查、Shell 安全策略、可回滚的工作流设计。
- **Coding-agent mode**：支持项目扫描、代码问答、代码定位和任务历史记录。
- **MCP-ready**：支持通过 Model Context Protocol 挂载外部工具。

## 快速开始

### 安装

```bash
git clone https://github.com/EmberRavager/youagent.git
cd youagent
pip install -e .
```

### 配置

可以在 workspace 创建 `.env`，也可以用 `youagent config` 写入默认配置：

```bash
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.openai.com/v1"
MINIMAX_API_KEY="your_api_key"
MINIMAX_BASE_URL="https://api.minimaxi.com/v1"
```

可选默认配置：

```bash
youagent config --provider openai --model gpt-4.1-mini --api-key "sk-..."
```

## Coding Agent CLI

初始化项目画像：

```bash
youagent-code init
```

围绕当前代码仓库提问：

```bash
youagent-code ask "这个项目是干嘛的？"
youagent-code ask "登录逻辑在哪里？列出关键文件"
youagent-code ask "认证接口的错误处理应该加在哪里？"
```

也支持简写：

```bash
youagent-code "分析这个仓库的架构"
```

查看任务轨迹：

```bash
youagent-code trace last
youagent-code trace list
```

生成文件：

```text
.youagent/
├── project.json
└── runs/
    └── 20260611-120000-task.md
```

## 经典 Agent Chat

原来的交互式工具调用 Agent 仍然可用：

```bash
youagent chat --agent miniagent_like --provider minimax --model MiniMax-M2.5
```

## Web UI

```bash
youagent serve --host 0.0.0.0 --port 7788
# 打开 http://localhost:7788
```

Docker 示例：

```bash
docker run -d -p 8000:7788 -v $(pwd)/workspace:/workspace youagent
```

## 内置工具

| 工具 | 描述 |
|------|------|
| `list_files` | 列出目录内容 |
| `read_file` | 读取文本文件，带大小限制 |
| `write_file` | 写入或创建文件 |
| `run_shell` | 通过安全策略执行 Shell 命令 |
| `find_files` | Glob 文件搜索 |
| `grep_text` | 正则文本搜索 |
| `fetch_url` | 获取网页内容 |
| `read_json` / `write_json` | JSON 操作 |
| `playwright_browse` | 浏览器内容提取或截图 |
| MCP tools | 通过 MCP 配置挂载的外部工具 |

## 架构

```text
src/mini_worker/
├── code_cli.py       # Coding Agent CLI：扫描、问答、Trace
├── agents.py         # Agent 配置和提示词
├── cli.py            # 经典 CLI 入口
├── llm.py            # OpenAI 兼容 LLM 客户端
├── runtime.py        # 工具调用循环
├── tools.py          # 内置工具实现
├── mcp.py            # MCP 工具挂载
├── memory.py         # 会话记忆
├── tasking.py        # 定时任务
├── observability.py  # 事件和指标
└── server.py         # Web 服务和 API
```

## 配置参数

```bash
youagent-code ask "分析这个仓库" \
  --provider openai \
  --model gpt-4.1-mini \
  --workspace /path/to/repo \
  --session code \
  --timeout 60
```

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `--provider` | LLM 提供商 | 默认配置 |
| `--model` | 模型名称 | 默认配置 |
| `--workspace` | 工作目录 | `.` |
| `--session` | 记忆会话 ID | `code` |
| `--timeout` | LLM 请求超时，单位秒 | `60` |
| `--mcp-config` | MCP 服务器配置路径 | - |
| `--no-trace` | 不生成 trace 文件 | `false` |

## 支持的 Provider

- OpenAI / OpenAI 兼容接口
- MiniMax
- Anthropic
- DeepSeek
- Gemini
- Grok
- OpenRouter
- 自定义兼容端点

## 安全设计

- 文件操作限制在 workspace 内
- Shell 命令通过 `.mini_worker/security.json` 过滤
- URL 抓取限制
- 任务执行过程可追踪
- Coding Agent 默认先检查仓库，再给结论；除非用户明确要求，否则不主动改文件

## 可观测性

```bash
curl http://localhost:7788/api/events?limit=40
curl http://localhost:7788/api/metrics
```

事件日志保存在：

```text
.mini_worker/observability/events.jsonl
```

## Roadmap

- Patch-first 编辑：写文件前先生成 diff
- 文件写入和高风险命令的人类确认流
- Playbook 工作流：`fix-test`、`explain-project`、`review-pr`、`add-api`
- 更强的代码库索引和上下文压缩
- Trace 回放和可分享任务报告

## 许可证

MIT License - 查看 [LICENSE](LICENSE) 了解更多。

## 相关链接

- [GitHub 仓库](https://github.com/EmberRavager/youagent)
- [问题反馈](https://github.com/EmberRavager/youagent/issues)
