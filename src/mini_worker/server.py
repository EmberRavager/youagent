import json
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .agents import AGENTS, get_agent
from .config import available_providers
from .llm import ChatClient
from .mcp import MCPRuntime
from .memory import SessionMemory
from .observability import Observability
from .runtime import AgentRuntime
from .settings import SettingsStore
from .tasking import ScheduledTask, TaskStore, run_due_tasks
from .tools import ToolRegistry


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouAgent</title>
  <style>
    :root {
      --bg: #f7f7f8;
      --panel: #ffffff;
      --line: #e5e7eb;
      --text: #0f172a;
      --muted: #64748b;
      --user: #eef6ff;
      --assistant: #ffffff;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      background: radial-gradient(1000px 700px at 0% -10%, #ffffff 0%, #f6f8fb 45%, #f3f5f8 100%);
      color: var(--text);
      font-family: "Sohne", "Segoe UI", "PingFang SC", sans-serif;
    }
    .app {
      display: grid;
      grid-template-columns: 280px 1fr;
      height: 100vh;
    }
    .sidebar {
      border-right: 1px solid #d7dee7;
      background: linear-gradient(180deg, #eef2f6 0%, #e8edf3 100%);
      padding: 14px;
      overflow: auto;
      display: grid;
      gap: 10px;
      align-content: start;
    }
    .brand { font-size: 18px; font-weight: 700; }
    .subtle { color: var(--muted); font-size: 12px; }
    .panel {
      background: rgba(255,255,255,0.86);
      border: 1px solid #dce3ec;
      border-radius: 12px;
      padding: 10px;
      display: grid;
      gap: 8px;
    }
    label { font-size: 12px; color: #475569; display: block; margin-bottom: 2px; }
    input, select, button {
      width: 100%;
      border: 1px solid #d6dde7;
      border-radius: 10px;
      padding: 10px 11px;
      font-size: 13px;
      background: #fff;
      color: #0f172a;
      outline: none;
    }
    input:focus, select:focus {
      border-color: #a6b5c9;
      box-shadow: 0 0 0 3px rgba(100,116,139,0.15);
    }
    button { cursor: pointer; font-weight: 600; }
    .btn-primary { background: #111827; border-color: #111827; color: #fff; }
    .btn-ghost { background: #fff; }
    .btn-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .link { color: #334155; text-decoration: none; font-size: 12px; }

    .main {
      display: grid;
      grid-template-rows: 56px 1fr auto;
      height: 100vh;
    }
    .header {
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,0.8);
      backdrop-filter: blur(6px);
      padding: 0 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    .title { font-size: 15px; font-weight: 700; }
    .meta {
      font-size: 12px;
      color: var(--muted);
      max-width: 70%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-align: right;
    }
    .chat {
      overflow-y: auto;
      padding: 22px 0 34px;
      scroll-behavior: smooth;
    }
    .msg-wrap {
      width: min(860px, calc(100% - 30px));
      margin: 0 auto;
      padding: 0 4px;
    }
    .row { display: flex; margin-bottom: 12px; }
    .row.user { justify-content: flex-end; }
    .row.assistant { justify-content: flex-start; }
    .bubble {
      max-width: 86%;
      border: 1px solid var(--line);
      background: var(--assistant);
      border-radius: 14px;
      padding: 12px 14px;
      line-height: 1.58;
      font-size: 15px;
      white-space: pre-wrap;
      word-break: break-word;
      box-shadow: 0 1px 0 rgba(0,0,0,0.03);
    }
    .row.user .bubble { background: var(--user); }

    .composer {
      border-top: 1px solid var(--line);
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(6px);
      padding: 14px;
    }
    .composer-inner {
      width: min(860px, calc(100% - 30px));
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: end;
    }
    textarea {
      width: 100%;
      min-height: 52px;
      max-height: 220px;
      resize: vertical;
      border: 1px solid #d5dde8;
      border-radius: 14px;
      padding: 13px 14px;
      font-size: 15px;
      font-family: inherit;
      line-height: 1.5;
      outline: none;
      background: #fff;
    }
    textarea:focus {
      border-color: #9fb0c6;
      box-shadow: 0 0 0 3px rgba(100,116,139,0.16);
    }
    .send { height: 52px; padding: 0 18px; border-radius: 12px; }

    .typing { display: inline-flex; align-items: center; gap: 4px; height: 18px; }
    .typing i {
      width: 7px; height: 7px; border-radius: 50%; background: #9aa8bb;
      display: inline-block; animation: blink 1.05s infinite ease-in-out;
    }
    .typing i:nth-child(2) { animation-delay: 0.14s; }
    .typing i:nth-child(3) { animation-delay: 0.28s; }
    @keyframes blink {
      0%,80%,100% { opacity: 0.35; transform: translateY(0); }
      40% { opacity: 1; transform: translateY(-2px); }
    }

    @media (max-width: 980px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid #d7dee7; }
      .main { height: calc(100vh - 330px); }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">YouAgent</div>
      <div class="subtle">ChatGPT-like conversation layout</div>

      <div class="panel">
        <div>
          <label for="session">Session</label>
          <input id="session" placeholder="default" value="default" />
        </div>
        <div>
          <label for="agent">Agent</label>
          <select id="agent">
            <option value="miniagent_like">miniagent_like</option>
            <option value="manus_like">manus_like</option>
          </select>
        </div>
        <div class="btn-row">
          <button id="switchBtn" class="btn-ghost">Apply Agent</button>
          <button id="clearBtn" class="btn-ghost">Clear Chat</button>
        </div>
      </div>

      <div class="panel">
        <div>
          <label for="provider">Provider</label>
          <select id="provider"></select>
        </div>
        <div>
          <label for="model">Model</label>
          <input id="model" placeholder="gpt-4.1-mini" />
        </div>
        <div>
          <label for="baseUrl">Base URL</label>
          <input id="baseUrl" placeholder="https://..." />
        </div>
        <div>
          <label for="apiKey">API Key (optional)</label>
          <input id="apiKey" type="password" placeholder="leave empty to use env/config" />
        </div>
        <button id="saveConfigBtn" class="btn-primary">Save Model Config</button>
      </div>

      <div class="panel">
        <a class="link" href="/tasks.html" target="_blank">Open Task Dashboard</a>
      </div>
    </aside>

    <main class="main">
      <header class="header">
        <div class="title">Chat</div>
        <div id="meta" class="meta">Loading configuration...</div>
      </header>

      <section id="messages" class="chat">
        <div class="msg-wrap">
          <div class="row assistant">
            <div class="bubble">Ready. Ask me to inspect files, run tools, or execute tasks.</div>
          </div>
        </div>
      </section>

      <footer class="composer">
        <div class="composer-inner">
          <textarea id="input" placeholder="Send a message... (Enter to send, Shift+Enter for newline)"></textarea>
          <button id="sendBtn" class="btn-primary send">Send</button>
        </div>
      </footer>
    </main>
  </div>

  <script>
    const messages = document.getElementById("messages");
    const input = document.getElementById("input");
    const sendBtn = document.getElementById("sendBtn");
    const switchBtn = document.getElementById("switchBtn");
    const clearBtn = document.getElementById("clearBtn");
    const agent = document.getElementById("agent");
    const session = document.getElementById("session");
    const meta = document.getElementById("meta");
    const provider = document.getElementById("provider");
    const model = document.getElementById("model");
    const baseUrl = document.getElementById("baseUrl");
    const apiKey = document.getElementById("apiKey");
    const saveConfigBtn = document.getElementById("saveConfigBtn");

    function cleanReply(text) {
      return String(text || "").replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
    }

    function appendBubble(role, text) {
      const wrap = document.createElement("div");
      wrap.className = "msg-wrap";
      const row = document.createElement("div");
      row.className = `row ${role}`;
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = text;
      row.appendChild(bubble);
      wrap.appendChild(row);
      messages.appendChild(wrap);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function appendTyping() {
      const wrap = document.createElement("div");
      wrap.className = "msg-wrap";
      const row = document.createElement("div");
      row.className = "row assistant";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
      row.appendChild(bubble);
      wrap.appendChild(row);
      messages.appendChild(wrap);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function renderProviders(list) {
      const values = Array.isArray(list) ? list : [];
      provider.innerHTML = "";
      values.forEach((item) => {
        const op = document.createElement("option");
        op.value = item;
        op.textContent = item;
        provider.appendChild(op);
      });
      if (!values.length) {
        const op = document.createElement("option");
        op.value = "openai";
        op.textContent = "openai";
        provider.appendChild(op);
      }
    }

    async function loadStatus() {
      const resp = await fetch("/api/status");
      const data = await resp.json();
      renderProviders(data.providers || []);
      provider.value = data.provider || "openai";
      model.value = data.model || "";
      baseUrl.value = data.base_url || "";
      meta.textContent = `provider=${data.provider} | model=${data.model} | mcp_tools=${data.mcp_mounted_tools || 0} | scheduler=${Boolean(data.scheduler)}`;
    }

    async function saveConfig() {
      saveConfigBtn.disabled = true;
      try {
        const resp = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: provider.value,
            model: model.value.trim(),
            base_url: baseUrl.value.trim(),
            api_key: apiKey.value.trim(),
          }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
          appendBubble("assistant", `Config update failed: ${data.error || "unknown error"}`);
          return;
        }
        apiKey.value = "";
        appendBubble("assistant", `Config updated: ${data.provider} / ${data.model}`);
        await loadStatus();
      } catch (err) {
        appendBubble("assistant", `Config update failed: ${String(err)}`);
      } finally {
        saveConfigBtn.disabled = false;
      }
    }

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;
      appendBubble("user", text);
      input.value = "";
      sendBtn.disabled = true;
      const loadingNode = appendTyping();

      try {
        const resp = await fetch("/api/chat_stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            session: session.value.trim() || "default",
            agent: agent.value,
          }),
        });
        if (!resp.ok || !resp.body) {
          loadingNode.textContent = `Request failed (${resp.status})`;
          return;
        }

        let buffer = "";
        let started = false;
        const decoder = new TextDecoder();
        const reader = resp.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() || "";
          for (const frame of frames) {
            const line = frame.split("\n").find((x) => x.startsWith("data:"));
            if (!line) continue;
            const data = JSON.parse(line.slice(5).trim());
            if (data.type === "error") {
              loadingNode.textContent = `Error: ${data.error || "request failed"}`;
              return;
            }
            if (data.type === "delta") {
              if (!started) {
                loadingNode.textContent = "";
                started = true;
              }
              loadingNode.textContent += data.text || "";
              messages.scrollTop = messages.scrollHeight;
            }
            if (data.type === "done") {
              loadingNode.textContent = cleanReply(loadingNode.textContent);
            }
          }
        }
        if (!started) {
          loadingNode.textContent = "No output from model.";
        }
      } catch (err) {
        loadingNode.textContent = `Network error: ${String(err)}`;
      } finally {
        sendBtn.disabled = false;
        input.focus();
      }
    }

    switchBtn.addEventListener("click", () => {
      appendBubble("assistant", `Switched to ${agent.value} (session=${session.value || "default"})`);
    });
    clearBtn.addEventListener("click", () => {
      messages.innerHTML = "";
      appendBubble("assistant", "Chat cleared.");
      input.focus();
    });
    saveConfigBtn.addEventListener("click", saveConfig);
    sendBtn.addEventListener("click", sendMessage);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    loadStatus().catch((err) => {
      meta.textContent = `status load failed: ${String(err)}`;
    });
    input.focus();
  </script>
</body>
</html>"""


TASKS_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouAgent Task Dashboard</title>
  <style>
    body { margin: 0; padding: 20px; font-family: Segoe UI, sans-serif; background: #f5f7fb; color: #0f172a; }
    .grid { display: grid; gap: 12px; }
    .card { background: #fff; border: 1px solid #dbe2ea; border-radius: 12px; padding: 12px; }
    .title { font-size: 18px; font-weight: 700; }
    .meta { color: #64748b; font-size: 12px; margin-top: 4px; }
    .row { border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; margin-top: 8px; background: #fcfdff; }
    .status { font-weight: 700; }
    .ok { color: #047857; }
    .error { color: #b91c1c; }
    .idle { color: #334155; }
    code { background: #eef2ff; padding: 1px 4px; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="grid">
    <div class="card">
      <div class="title">Task Dashboard</div>
      <div class="meta">Auto refresh every 3s</div>
      <div id="metrics" class="meta">loading metrics...</div>
    </div>
    <div class="card">
      <div class="title">Scheduled Tasks</div>
      <div id="tasks">loading...</div>
    </div>
    <div class="card">
      <div class="title">Recent Events</div>
      <div id="events">loading...</div>
    </div>
  </div>
  <script>
    const tasksEl = document.getElementById('tasks');
    const metricsEl = document.getElementById('metrics');
    const eventsEl = document.getElementById('events');
    function fmtTs(ts) {
      if (!ts) return '-';
      return new Date(ts * 1000).toLocaleString();
    }
    function statusClass(status) {
      if (status === 'error') return 'error';
      if (status === 'running') return 'ok';
      return 'idle';
    }
    async function load() {
      const [tasksResp, metricsResp, eventsResp] = await Promise.all([
        fetch('/api/tasks'),
        fetch('/api/metrics'),
        fetch('/api/events?limit=40'),
      ]);
      const tasks = await tasksResp.json();
      const metrics = await metricsResp.json();
      const events = await eventsResp.json();
      metricsEl.textContent = `metrics: ${JSON.stringify((metrics && metrics.counters) || {})}`;
      const rows = (tasks.tasks || []).map((t) => `
        <div class="row">
          <div><strong>${t.name}</strong> <span class="status ${statusClass(t.status)}">[${t.status}]</span></div>
          <div class="meta">id=<code>${t.id}</code> step=${t.step_index}/${t.step_total} next=${fmtTs(t.next_run_at)} every=${t.interval_seconds}s</div>
          <div class="meta">last_run=${fmtTs(t.last_run_at)} runs=${t.runs}</div>
          <div class="meta">${t.last_error ? ('error=' + t.last_error) : (t.last_reply ? ('reply=' + t.last_reply.slice(0, 220)) : '')}</div>
        </div>
      `).join('');
      tasksEl.innerHTML = rows || '<div class="meta">No tasks</div>';
      const ers = (events.events || []).map((e) => `<div class="meta">${fmtTs(e.ts)} | ${e.event} | ${JSON.stringify(e).slice(0, 220)}</div>`).join('');
      eventsEl.innerHTML = ers || '<div class="meta">No events</div>';
    }
    load().catch((e) => { tasksEl.textContent = String(e); });
    setInterval(() => load().catch(() => {}), 3000);
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
    mcp_config: str | None = None
    scheduler: bool = False
    observability: Observability | None = None


class WebApp:
    def __init__(self, cfg: ServerConfig, client: ChatClient):
        self.cfg = cfg
        self.client = client
        self.obs = cfg.observability or Observability(cfg.workspace)
        self.timeout_seconds = client.cfg.timeout_seconds
        self.tools = ToolRegistry(workspace=cfg.workspace)
        self.mcp_runtime = MCPRuntime(workspace=cfg.workspace, config_path=cfg.mcp_config)
        self.mcp_runtime.mount(self.tools)
        self.task_store = TaskStore(cfg.workspace)
        self.runtimes: dict[tuple[str, str], AgentRuntime] = {}
        self._lock = threading.Lock()
        self._scheduler_stop = threading.Event()
        self._scheduler_thread: threading.Thread | None = None
        if cfg.scheduler:
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()

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
            "providers": available_providers(),
            "mcp_config": self.cfg.mcp_config,
            "mcp_mounted_tools": len(self.mcp_runtime.mounted_tools),
            "mcp_tools": self.mcp_runtime.mounted_tools,
            "scheduler": self.cfg.scheduler,
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
        reply = runtime.ask(
            message,
            event_callback=lambda evt: self.obs.record(
                "runtime_event",
                mode="web_chat",
                session=session_id,
                phase=evt.get("phase"),
                detail=evt,
            ),
        )
        self.obs.record("web_chat_reply", session=session_id, chars=len(reply))
        return {"ok": True, "reply": reply, "session": session_id, "agent": agent_name}

    def tasks(self) -> dict[str, Any]:
        return {"tasks": [task.to_dict() for task in self.task_store.list()]}

    def metrics(self) -> dict[str, Any]:
        return self.obs.metrics()

    def events(self, limit: int = 80) -> dict[str, Any]:
        return {"events": self.obs.recent(limit=limit)}

    def add_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            return {"ok": False, "error": "prompt is required"}
        name = str(payload.get("name", "task")).strip() or "task"
        try:
            every = max(10, int(payload.get("every", 300)))
        except Exception:
            return {"ok": False, "error": "every must be integer seconds"}
        task = self.task_store.add(
            name=name,
            prompt=prompt,
            provider=str(payload.get("provider", self.cfg.provider)).strip(),
            model=str(payload.get("model", self.cfg.model)).strip(),
            agent=str(payload.get("agent", "miniagent_like")).strip(),
            session=str(payload.get("session", "default")).strip() or "default",
            workspace=self.cfg.workspace,
            base_url=str(payload.get("base_url", "")).strip() or None,
            interval_seconds=every,
            no_memory=bool(payload.get("no_memory", self.cfg.no_memory)),
            mcp_config=str(payload.get("mcp_config", self.cfg.mcp_config or "")).strip() or None,
        )
        self.obs.record("task_added", task_id=task.id, name=task.name)
        return {"ok": True, "task": task.to_dict()}

    def delete_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(payload.get("id", "")).strip()
        if not task_id:
            return {"ok": False, "error": "id is required"}
        ok = self.task_store.delete(task_id)
        if ok:
            self.obs.record("task_deleted", task_id=task_id)
        return {"ok": ok, "id": task_id}

    def run_due_once(self) -> dict[str, Any]:
        executed = run_due_tasks(
            self.task_store,
            self._run_task_once,
            on_event=lambda event, data: self.obs.record(event, **data),
        )
        return {"ok": True, "executed": executed}

    def _run_task_once(
        self, task: ScheduledTask, progress_callback: Any
    ) -> tuple[bool, str]:
        settings = SettingsStore(task.workspace).load()
        api_key = settings.api_keys.get(task.provider)
        client = ChatClient.from_options(
            provider=task.provider,
            model=task.model,
            api_key=api_key,
            base_url=task.base_url,
            timeout_seconds=self.timeout_seconds,
        )
        tools = ToolRegistry(workspace=task.workspace)
        mcp_runtime = MCPRuntime(workspace=task.workspace, config_path=task.mcp_config)
        try:
            mcp_runtime.mount(tools)
            memory = (
                None
                if task.no_memory
                else SessionMemory(workspace=task.workspace, session_id=task.session)
            )
            runtime = AgentRuntime(
                agent=get_agent(task.agent),
                client=client,
                tools=tools,
                memory=memory,
            )
            reply = runtime.ask(task.prompt, event_callback=progress_callback)
            return True, reply
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"
        finally:
            mcp_runtime.close()

    def _scheduler_loop(self) -> None:
        self.obs.record("scheduler_started", workspace=self.cfg.workspace)
        while not self._scheduler_stop.is_set():
            try:
                run_due_tasks(
                    self.task_store,
                    self._run_task_once,
                    on_event=lambda event, data: self.obs.record(event, **data),
                )
            except Exception as exc:  # noqa: BLE001
                self.obs.record("scheduler_error", error=str(exc))
            self._scheduler_stop.wait(3)
        self.obs.record("scheduler_stopped", workspace=self.cfg.workspace)


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
            if self.path == "/tasks.html":
                _html(self, HTTPStatus.OK, TASKS_PAGE)
                return
            if self.path == "/api/status":
                _json(self, HTTPStatus.OK, app.status())
                return
            if self.path == "/api/tasks":
                _json(self, HTTPStatus.OK, app.tasks())
                return
            if self.path == "/api/metrics":
                _json(self, HTTPStatus.OK, app.metrics())
                return
            if self.path.startswith("/api/events"):
                limit = 80
                if "limit=" in self.path:
                    try:
                        limit = int(self.path.split("limit=", 1)[1].split("&", 1)[0])
                    except Exception:
                        limit = 80
                _json(self, HTTPStatus.OK, app.events(limit=limit))
                return
            _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {
                "/api/chat",
                "/api/chat_stream",
                "/api/config",
                "/api/tasks",
                "/api/tasks/delete",
                "/api/tasks/run_due",
            }:
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
                if self.path == "/api/tasks":
                    result = app.add_task(payload)
                    status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
                    _json(self, status, result)
                    return
                if self.path == "/api/tasks/delete":
                    result = app.delete_task(payload)
                    status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
                    _json(self, status, result)
                    return
                if self.path == "/api/tasks/run_due":
                    result = app.run_due_once()
                    _json(self, HTTPStatus.OK, result)
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
        app._scheduler_stop.set()
        if app._scheduler_thread is not None:
            app._scheduler_thread.join(timeout=2)
        server.server_close()
        app.mcp_runtime.close()
    return 0




