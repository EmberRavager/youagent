import json
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .agents import AGENTS, get_agent
from .llm import ChatClient
from .memory import SessionMemory
from .runtime import AgentRuntime
from .tools import ToolRegistry


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mini Worker 聊天</title>
  <style>
    :root {
      --bg: #f7f7f8;
      --panel: #ffffff;
      --line: #e5e7eb;
      --text: #0f172a;
      --muted: #6b7280;
      --brand: #10a37f;
      --user-bg: #f0fdf4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Sohne", "SF Pro Text", "Segoe UI", sans-serif;
    }
    .shell {
      max-width: 980px;
      margin: 0 auto;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto auto auto 1fr auto auto;
      gap: 10px;
      padding: 14px;
    }
    .topbar, .composer {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 1px 1px rgba(0, 0, 0, 0.03);
    }
    .topbar {
      display: grid;
      grid-template-columns: 1.2fr 1fr auto auto;
      gap: 10px;
      padding: 10px;
    }
    .modelbar {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 1px 1px rgba(0, 0, 0, 0.03);
      display: grid;
      grid-template-columns: 1fr 1fr 1.2fr 1.2fr auto;
      gap: 10px;
      padding: 10px;
    }
    input, select, button {
      height: 40px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      padding: 0 12px;
      font-size: 14px;
      outline: none;
    }
    input:focus, select:focus {
      border-color: #b6ddd4;
      box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.12);
    }
    button {
      cursor: pointer;
      font-weight: 600;
    }
    .btn-primary {
      background: var(--brand);
      border-color: var(--brand);
      color: #fff;
    }
    .btn-ghost {
      background: #fff;
      color: #334155;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
      padding: 0 6px;
    }
    .chat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .row {
      display: flex;
      width: 100%;
    }
    .row.user { justify-content: flex-end; }
    .row.agent { justify-content: flex-start; }
    .bubble {
      max-width: min(820px, 88%);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      line-height: 1.55;
      font-size: 15px;
      white-space: pre-wrap;
      word-break: break-word;
      background: #fff;
    }
    .row.user .bubble {
      background: var(--user-bg);
    }
    .composer {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      padding: 10px;
    }
    .composer input {
      height: 46px;
      font-size: 15px;
    }
    .typing {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      height: 18px;
    }
    .typing span {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #94a3b8;
      animation: blink 1s infinite ease-in-out;
    }
    .typing span:nth-child(2) { animation-delay: 0.15s; }
    .typing span:nth-child(3) { animation-delay: 0.3s; }
    @keyframes blink {
      0%, 80%, 100% { opacity: 0.35; transform: translateY(0); }
      40% { opacity: 1; transform: translateY(-2px); }
    }
    .footer {
      text-align: right;
      color: var(--muted);
      font-size: 12px;
      padding-bottom: 2px;
    }
    @media (max-width: 860px) {
      .topbar { grid-template-columns: 1fr 1fr; }
      .modelbar { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <input id="session" placeholder="会话 ID" value="default" />
      <select id="agent">
        <option value="miniagent_like">miniagent_like</option>
        <option value="manus_like">manus_like</option>
      </select>
      <button id="switchBtn" class="btn-ghost">切换风格</button>
      <button id="clearBtn" class="btn-ghost">清空</button>
    </div>
    <div class="modelbar">
      <select id="provider">
        <option value="openai">openai</option>
        <option value="openrouter">openrouter</option>
        <option value="minimax">minimax</option>
        <option value="custom">custom</option>
      </select>
      <input id="model" placeholder="模型，如 MiniMax-M2.5" />
      <input id="baseUrl" placeholder="Base URL（可选）" />
      <input id="apiKey" placeholder="API Key（可选，留空使用.env）" />
      <button id="saveConfigBtn" class="btn-ghost">应用模型配置</button>
    </div>
    <div id="meta" class="meta">正在加载配置...</div>
    <div id="messages" class="chat"></div>
    <div class="composer">
      <input id="input" placeholder="给 Mini Worker 发送消息..." />
      <button id="sendBtn" class="btn-primary">发送</button>
    </div>
    <div class="footer">由尤文开发 | 在杭州，有想招作者进去的联系邮箱 emberravager@gmail.com</div>
  </div>

  <script>
    const messages = document.getElementById('messages');
    const input = document.getElementById('input');
    const sendBtn = document.getElementById('sendBtn');
    const switchBtn = document.getElementById('switchBtn');
    const clearBtn = document.getElementById('clearBtn');
    const agent = document.getElementById('agent');
    const session = document.getElementById('session');
    const meta = document.getElementById('meta');
    const provider = document.getElementById('provider');
    const model = document.getElementById('model');
    const baseUrl = document.getElementById('baseUrl');
    const apiKey = document.getElementById('apiKey');
    const saveConfigBtn = document.getElementById('saveConfigBtn');

    function appendBubble(role, text) {
      const row = document.createElement('div');
      row.className = `row ${role}`;
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      row.appendChild(bubble);
      messages.appendChild(row);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function appendTyping() {
      const row = document.createElement('div');
      row.className = 'row agent';
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
      row.appendChild(bubble);
      messages.appendChild(row);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function cleanReply(text) {
      return text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
    }

    async function loadStatus() {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      provider.value = data.provider || 'minimax';
      model.value = data.model || '';
      baseUrl.value = data.base_url || '';
      meta.textContent = `Provider=${data.provider} | Model=${data.model} | Base=${data.base_url} | API Key=${data.api_key_configured ? '已配置' : '未配置'}`;
    }

    async function saveConfig() {
      saveConfigBtn.disabled = true;
      try {
        const resp = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: provider.value,
            model: model.value.trim(),
            base_url: baseUrl.value.trim(),
            api_key: apiKey.value.trim(),
          }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
          appendBubble('agent', `模型配置失败：${data.error || '未知错误'}`);
          return;
        }
        apiKey.value = '';
        appendBubble('agent', `模型配置已更新：${data.provider} / ${data.model}`);
        await loadStatus();
      } catch (err) {
        appendBubble('agent', `模型配置失败：${String(err)}`);
      } finally {
        saveConfigBtn.disabled = false;
      }
    }

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;

      appendBubble('user', text);
      input.value = '';
      sendBtn.disabled = true;
      const loadingNode = appendTyping();

      try {
        const resp = await fetch('/api/chat_stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            session: session.value.trim() || 'default',
            agent: agent.value,
          }),
        });

        if (!resp.ok || !resp.body) {
          loadingNode.textContent = `错误：请求失败 (${resp.status})`;
          return;
        }

        let firstDelta = false;
        let buffer = '';
        const decoder = new TextDecoder();
        const reader = resp.body.getReader();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';

          for (const frame of frames) {
            const line = frame.split('\n').find((x) => x.startsWith('data:'));
            if (!line) continue;
            const data = JSON.parse(line.slice(5).trim());

            if (data.type === 'error') {
              loadingNode.textContent = `错误：${data.error || '请求失败'}`;
              return;
            }

            if (data.type === 'delta') {
              if (!firstDelta) {
                loadingNode.textContent = '';
                firstDelta = true;
              }
              loadingNode.textContent += data.text || '';
              messages.scrollTop = messages.scrollHeight;
            }

            if (data.type === 'done') {
              loadingNode.textContent = cleanReply(loadingNode.textContent);
            }
          }
        }

        if (!firstDelta) {
          loadingNode.textContent = '模型未返回内容。';
        }
      } catch (err) {
        loadingNode.textContent = `网络错误：${String(err)}`;
      } finally {
        sendBtn.disabled = false;
        input.focus();
      }
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendMessage();
    });

    switchBtn.addEventListener('click', () => {
      appendBubble('agent', `已切换到 ${agent.value}（会话：${session.value || 'default'}）。`);
      input.focus();
    });

    clearBtn.addEventListener('click', () => {
      messages.innerHTML = '';
      input.focus();
    });

    saveConfigBtn.addEventListener('click', saveConfig);

    loadStatus();
    input.focus();
  </script>
</body>
</html>
"""


@dataclass
class ServerConfig:
    host: str
    port: int
    workspace: str
    provider: str
    model: str
    no_memory: bool


class WebApp:
    def __init__(self, cfg: ServerConfig, client: ChatClient):
        self.cfg = cfg
        self.client = client
        self.timeout_seconds = client.cfg.timeout_seconds
        self.tools = ToolRegistry(workspace=cfg.workspace)
        self.runtimes: dict[tuple[str, str], AgentRuntime] = {}
        self._lock = threading.Lock()

    def _runtime_for(self, session_id: str, agent_name: str) -> AgentRuntime:
        key = (session_id, agent_name)
        runtime = self.runtimes.get(key)
        if runtime is not None:
            return runtime

        memory = None
        if not self.cfg.no_memory:
            memory = SessionMemory(workspace=self.cfg.workspace, session_id=session_id)

        runtime = AgentRuntime(
            agent=get_agent(agent_name),
            client=self.client,
            tools=self.tools,
            memory=memory,
        )
        self.runtimes[key] = runtime
        return runtime

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.cfg.provider,
            "model": self.cfg.model,
            "base_url": self.client.cfg.base_url,
            "api_key_configured": bool(self.client.cfg.api_key),
            "workspace": str(Path(self.cfg.workspace).resolve()),
            "agents": sorted(list(AGENTS.keys())),
            "providers": ["openai", "openrouter", "minimax", "custom"],
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = str(payload.get("provider", self.cfg.provider)).strip()
        model = str(payload.get("model", self.cfg.model)).strip()
        base_url = str(payload.get("base_url", "")).strip() or None
        api_key = str(payload.get("api_key", "")).strip() or None

        if not model:
            return {"ok": False, "error": "model is required"}

        with self._lock:
            client = ChatClient.from_options(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=self.timeout_seconds,
            )
            self.client = client
            self.cfg.provider = client.cfg.provider
            self.cfg.model = client.cfg.model
            self.runtimes.clear()

        return {
            "ok": True,
            "provider": self.cfg.provider,
            "model": self.cfg.model,
            "base_url": self.client.cfg.base_url,
            "api_key_configured": bool(self.client.cfg.api_key),
        }

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = str(payload.get("message", "")).strip()
        if not message:
            return {"ok": False, "error": "message is required"}

        session_id = str(payload.get("session", "default")).strip() or "default"
        agent_name = (
            str(payload.get("agent", "miniagent_like")).strip() or "miniagent_like"
        )
        if agent_name not in AGENTS:
            return {"ok": False, "error": f"unknown agent: {agent_name}"}

        runtime = self._runtime_for(session_id=session_id, agent_name=agent_name)
        reply = runtime.ask(message)
        return {"ok": True, "reply": reply, "session": session_id, "agent": agent_name}


def _json(
    handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]
) -> None:
    raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _html(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    raw = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _sse(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=True)
    frame = f"data: {data}\n\n".encode("utf-8")
    handler.wfile.write(frame)
    handler.wfile.flush()


def _clean_reply(text: str) -> str:
    start = text.lower().find("<think>")
    while start >= 0:
        end = text.lower().find("</think>", start)
        if end < 0:
            text = text[:start]
            break
        text = text[:start] + text[end + len("</think>") :]
        start = text.lower().find("<think>")
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 30) -> list[str]:
    if not text:
        return [""]
    chunks: list[str] = []
    index = 0
    while index < len(text):
        chunks.append(text[index : index + chunk_size])
        index += chunk_size
    return chunks


def run_web_server(cfg: ServerConfig, client: ChatClient) -> int:
    app = WebApp(cfg, client)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/" or self.path == "/index.html":
                _html(self, HTTPStatus.OK, HTML_PAGE)
                return
            if self.path == "/api/status":
                _json(self, HTTPStatus.OK, app.status())
                return
            _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/api/chat", "/api/chat_stream", "/api/config"}:
                _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length > 0 else b"{}"
                payload = json.loads(body.decode("utf-8"))
                if self.path == "/api/config":
                    result = app.update_config(payload)
                    status = (
                        HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
                    )
                    _json(self, status, result)
                    return

                if self.path == "/api/chat":
                    result = app.chat(payload)
                    status = (
                        HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
                    )
                    _json(self, status, result)
                    return

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                holder: dict[str, Any] = {}
                done = threading.Event()

                def worker() -> None:
                    try:
                        holder["result"] = app.chat(payload)
                    except Exception as exc:  # noqa: BLE001
                        holder["error"] = str(exc)
                    finally:
                        done.set()

                threading.Thread(target=worker, daemon=True).start()

                tick = 0
                while not done.is_set():
                    _sse(self, {"type": "status", "state": "thinking", "tick": tick})
                    tick += 1
                    time.sleep(0.25)

                if "error" in holder:
                    _sse(self, {"type": "error", "error": holder["error"]})
                    return

                result = holder.get("result", {"ok": False, "error": "empty result"})
                if not result.get("ok"):
                    _sse(
                        self,
                        {
                            "type": "error",
                            "error": result.get("error", "request failed"),
                        },
                    )
                    return

                cleaned = _clean_reply(str(result.get("reply", "")))
                for chunk in _chunk_text(cleaned, chunk_size=36):
                    _sse(self, {"type": "delta", "text": chunk})
                    time.sleep(0.015)
                _sse(self, {"type": "done"})
            except Exception as exc:  # noqa: BLE001
                try:
                    _json(
                        self,
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": str(exc)},
                    )
                except Exception:  # noqa: BLE001
                    return

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((cfg.host, cfg.port), Handler)
    print(f"Web client running: http://{cfg.host}:{cfg.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()
    return 0
