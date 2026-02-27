# YouAgent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.0-orange?style=for-the-badge" alt="Version">
</p>

> 🤖 轻量级 AI Agent 框架，具有工具调用能力，类 Manus/miniagent 风格。构建你自己的 AI 助手，自主执行任务。

**[English](./README.md)** | **[中文版](./README_CN.md)**

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

<p align="center">由 <a href="mailto:emberravager@gmail.com">EmberRavager</a> ❤️ 开发</p>
