# Architecture Notes

## Tooling Layer

- `ToolRegistry` is now registration-based.
- Built-in tools are mounted through `_register_builtin_tools()`.
- External tools can be mounted through:
  - `register_tool(...)` for any custom tool source.
  - `add_mcp_tool(...)` for MCP-discovered tools.

This removes hardcoded `if/elif` dispatch and keeps runtime unchanged when adding tools.

## MCP Layer

- `MCPRuntime` manages MCP client lifecycle for one process (`chat`, `serve`, `heartbeat`).
- `MCPClient` supports stdio JSON-RPC with:
  - `initialize`
  - `tools/list`
  - `tools/call`
- Reader thread + queue is used for robust response handling and timeout behavior.

## Config Layer

- Persistent config file: `.mini_worker/config.json`
- New key: `mcp_config`
- Commands:
  - `youagent config --mcp-config ...`
  - `youagent status`

## Next Extension Points

- Add MCP `streamable-http` transport by implementing another client class and reusing `MCPRuntime.mount()`.
- Add channel adapters (Telegram/Discord) as separate runtime wrappers that reuse `AgentRuntime`.
- Add policy hooks for tool allow/deny at registration time (before schemas are exposed).
