import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tools import ToolCallResult, ToolRegistry


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    startup_timeout: int = 15
    request_timeout: int = 60
    disabled: bool = False


@dataclass(frozen=True)
class MCPToolDescriptor:
    name: str
    description: str
    input_schema: dict[str, Any]


def load_mcp_servers(config_path: str, workspace: str) -> list[MCPServerConfig]:
    path = Path(config_path)
    if not path.is_absolute():
        path = Path(workspace).resolve() / path
    payload = json.loads(path.read_text(encoding="utf-8"))

    raw_servers = payload.get("servers", [])
    if not isinstance(raw_servers, list):
        raise ValueError("Invalid mcp config: 'servers' must be a list")

    servers: list[MCPServerConfig] = []
    for item in raw_servers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        command = str(item.get("command", "")).strip()
        if not name or not command:
            continue
        raw_args = item.get("args", [])
        args = [str(arg) for arg in raw_args] if isinstance(raw_args, list) else []
        raw_env = item.get("env", {})
        env = (
            {str(k): str(v) for k, v in raw_env.items()}
            if isinstance(raw_env, dict)
            else {}
        )
        cwd = item.get("cwd")
        startup_timeout = int(item.get("startup_timeout", 15))
        request_timeout = int(item.get("request_timeout", 60))
        disabled = bool(item.get("disabled", False))
        servers.append(
            MCPServerConfig(
                name=name,
                command=command,
                args=args,
                env=env,
                cwd=None if cwd in (None, "") else str(cwd),
                startup_timeout=max(1, startup_timeout),
                request_timeout=max(1, request_timeout),
                disabled=disabled,
            )
        )
    return servers


class MCPClient:
    def __init__(self, cfg: MCPServerConfig, workspace: str):
        self.cfg = cfg
        self.workspace = Path(workspace).resolve()
        self._proc: subprocess.Popen[bytes] | None = None
        self._id = 0
        self._lock = threading.Lock()
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._reader_error: str | None = None

    def start(self) -> None:
        if self._proc is not None:
            return
        env = None
        if self.cfg.env:
            env = {**os.environ, **self.cfg.env}
        cwd = self.cfg.cwd
        if cwd:
            target = Path(cwd)
            if not target.is_absolute():
                target = self.workspace / target
            cwd = str(target.resolve())
        else:
            cwd = str(self.workspace)
        self._proc = subprocess.Popen(
            [self.cfg.command, *self.cfg.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        self._reader_error = None
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "youagent", "version": "0.1.0"},
            },
            timeout=self.cfg.startup_timeout,
        )
        self._notify("notifications/initialized", {})

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._reader = None

    def list_tools(self) -> list[MCPToolDescriptor]:
        result = self._request(
            "tools/list", {"cursor": None}, timeout=self.cfg.request_timeout
        )
        raw_tools = result.get("tools", [])
        if not isinstance(raw_tools, list):
            return []
        tools: list[MCPToolDescriptor] = []
        for item in raw_tools:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            description = str(item.get("description", "")).strip() or name
            input_schema = item.get("inputSchema", {"type": "object", "properties": {}})
            if not isinstance(input_schema, dict):
                input_schema = {"type": "object", "properties": {}}
            tools.append(
                MCPToolDescriptor(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                )
            )
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=self.cfg.request_timeout,
        )
        if result.get("isError"):
            return ToolCallResult(False, self._normalize_content(result))
        return ToolCallResult(True, self._normalize_content(result))

    def _normalize_content(self, payload: dict[str, Any]) -> str:
        content = payload.get("content")
        if not isinstance(content, list):
            return json.dumps(payload, ensure_ascii=True)
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
                continue
            parts.append(json.dumps(item, ensure_ascii=True))
        if parts:
            return "\n".join(part for part in parts if part).strip()
        return json.dumps(payload, ensure_ascii=True)

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._write_message({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
        with self._lock:
            self._id += 1
            request_id = self._id
            self._write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            deadline = time.time() + max(1, timeout)
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f"MCP request timed out: {method}")
                if self._reader_error:
                    raise RuntimeError(self._reader_error)
                try:
                    message = self._queue.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(f"MCP request timed out: {method}") from exc
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    error = message.get("error")
                    raise RuntimeError(f"MCP error: {error}")
                result = message.get("result")
                if not isinstance(result, dict):
                    return {}
                return result

    def _write_message(self, payload: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise RuntimeError("MCP process not started")
        raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
        proc.stdin.write(header + raw)
        proc.stdin.flush()

    def _reader_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        while True:
            if proc.poll() is not None:
                self._reader_error = f"MCP process exited: code={proc.returncode}"
                return
            try:
                message = self._read_frame(proc.stdout)
                self._queue.put(message)
            except Exception as exc:  # noqa: BLE001
                self._reader_error = f"MCP read failed: {exc}"
                return

    def _read_frame(self, stdout: Any) -> dict[str, Any]:
        content_length = -1
        while True:
            line = stdout.readline()
            if not line:
                raise RuntimeError("MCP stream closed")
            if line in {b"\r\n", b"\n"}:
                break
            lower = line.lower()
            if lower.startswith(b"content-length:"):
                value = line.split(b":", 1)[1].strip()
                content_length = int(value.decode("ascii"))
        if content_length < 0:
            raise RuntimeError("MCP protocol error: missing Content-Length")
        body = stdout.read(content_length)
        if not body:
            raise RuntimeError("MCP protocol error: empty body")
        return json.loads(body.decode("utf-8"))


class MCPRuntime:
    def __init__(self, workspace: str, config_path: str | None):
        self.workspace = workspace
        self.config_path = config_path
        self.clients: list[MCPClient] = []
        self.mounted_tools: list[str] = []

    def mount(self, tools: ToolRegistry) -> None:
        if not self.config_path:
            return
        servers = load_mcp_servers(self.config_path, workspace=self.workspace)
        for server in servers:
            if server.disabled:
                continue
            client = MCPClient(server, workspace=self.workspace)
            client.start()
            self.clients.append(client)
            for mcp_tool in client.list_tools():
                parameters = mcp_tool.input_schema
                if not isinstance(parameters, dict) or not parameters:
                    parameters = {"type": "object", "properties": {}}
                if "type" not in parameters:
                    parameters = {"type": "object", "properties": {}, **parameters}
                mounted_name = tools.add_mcp_tool(
                    mcp_server=server.name,
                    mcp_tool_name=mcp_tool.name,
                    description=mcp_tool.description,
                    parameters=parameters,
                    handler=lambda args, c=client, t=mcp_tool.name: c.call_tool(t, args),
                )
                self.mounted_tools.append(mounted_name)

    def close(self) -> None:
        for client in self.clients:
            client.stop()
        self.clients.clear()
