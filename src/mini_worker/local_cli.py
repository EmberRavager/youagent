import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .agents import AgentProfile
from .cli import main as classic_main
from .code_cli import (
    MODEL_EXAMPLES,
    _slug,
    _snapshot_dirs,
    _youagent_dir,
    create_snapshot,
    finalize_snapshot,
    run_undo,
)
from .config import PROVIDER_PRESETS, available_providers
from .env import load_dotenv
from .llm import ChatClient
from .mcp import MCPRuntime
from .memory import SessionMemory
from .runtime import AgentRuntime
from .settings import SettingsStore
from .tools import ToolRegistry


LOCAL_AGENT = AgentProfile(
    name="youagent_local",
    system_prompt=(
        "You are YouAgent, a local-first computer agent. "
        "You help users inspect folders, organize files, run safe shell commands, "
        "fetch web content, automate browser tasks, and manage local workflows. "
        "Use tools when needed, but avoid risky or destructive actions unless the user explicitly asks. "
        "Prefer reversible operations, explain what you did, and mention risks. "
        "For file deletion, system changes, package installation, or commands with external side effects, "
        "ask for confirmation or provide a safe plan first. "
        "Keep answers concise and practical."
    ),
    max_tool_rounds=10,
)


LEGACY_COMMANDS = {"chat", "serve", "status", "config", "heartbeat", "tasks"}
ONE_SHOT_COMMANDS = {"ask", "init", "trace", "undo", "model"}


def _print_help() -> None:
    print(
        """YouAgent - local-first computer agent

Usage:
  youagent                         Start interactive chat
  youagent <task>                  Run one-shot task
  youagent model status            Show current model
  youagent model list              List provider presets
  youagent model set <provider> <model>
  youagent undo last               Restore last file snapshot
  youagent trace last              Show latest trace
  youagent chat                    Use classic chat mode
  youagent serve                   Start Web UI

Slash commands in interactive mode:
  /help
  /model
  /model list
  /model set <provider> <model>
  /undo
  /trace
  /exit
""".strip()
    )


def _write_trace(
    *,
    workspace: str,
    prompt: str,
    events: list[dict[str, Any]],
    reply: str,
    snapshot_path: Path | None,
) -> Path:
    runs = _youagent_dir(workspace) / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slug(prompt)}.md"
    lines = [
        "# YouAgent Trace",
        "",
        f"- Time: {datetime.now().isoformat(timespec='seconds')}",
        f"- Workspace: `{Path(workspace).resolve()}`",
    ]
    if snapshot_path is not None:
        lines.append(f"- Undo snapshot: `{snapshot_path}`")
    lines.extend(["", "## Goal", "", prompt.strip(), "", "## Runtime Events", ""])
    if events:
        for idx, event in enumerate(events, start=1):
            phase = event.get("phase", "unknown")
            tool_name = event.get("tool_name")
            ok = event.get("ok")
            suffix = ""
            if tool_name:
                suffix += f" tool={tool_name}"
            if ok is not None:
                suffix += f" ok={ok}"
            lines.append(f"{idx}. `{phase}`{suffix}")
    else:
        lines.append("No runtime events captured.")
    lines.extend(["", "## Final Answer", "", reply.strip() or "(empty)", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _model_status(workspace: str) -> None:
    store = SettingsStore(workspace)
    settings = store.load()
    print(
        json.dumps(
            {
                "provider": settings.provider,
                "model": settings.model,
                "base_url": settings.base_url,
                "workspace": str(Path(workspace).resolve()),
                "config_path": str(store.path),
                "api_keys_configured": sorted(settings.api_keys.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _model_list() -> None:
    rows = []
    for provider in available_providers():
        preset = PROVIDER_PRESETS[provider]
        rows.append(
            {
                "provider": provider,
                "base_url": preset["base_url"],
                "api_key_env": preset["key_env"],
                "examples": MODEL_EXAMPLES.get(provider, []),
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(
        "\nNote: YouAgent currently uses OpenAI-compatible /chat/completions. "
        "For native-only models, use OpenRouter, vLLM, or a custom compatible gateway."
    )


def _model_set(workspace: str, provider: str, model: str) -> None:
    provider = provider.strip().lower()
    if provider not in available_providers():
        print(f"Unknown provider: {provider}. Available: {', '.join(available_providers())}")
        return
    store = SettingsStore(workspace)
    settings = store.load()
    settings.provider = provider
    settings.model = model.strip()
    store.save(settings)
    print(f"model updated: provider={settings.provider} model={settings.model}")


def _show_latest_trace(workspace: str) -> None:
    runs = _youagent_dir(workspace) / "runs"
    files = sorted(runs.glob("*.md")) if runs.exists() else []
    if not files:
        print("No trace files found.")
        return
    print(files[-1].read_text(encoding="utf-8"))


def _run_undo_last(workspace: str) -> None:
    class Args:
        undo_command = "last"
        yes = False

        def __init__(self, workspace: str):
            self.workspace = workspace

    run_undo(Args(workspace))


def _handle_slash_command(text: str, workspace: str) -> bool:
    parts = text.strip().split()
    command = parts[0].lower() if parts else ""

    if command in {"/exit", "/quit"}:
        raise KeyboardInterrupt
    if command == "/help":
        _print_help()
        return True
    if command == "/model":
        if len(parts) == 1 or parts[1] == "status":
            _model_status(workspace)
            return True
        if parts[1] == "list":
            _model_list()
            return True
        if parts[1] == "set" and len(parts) >= 4:
            _model_set(workspace, parts[2], parts[3])
            return True
        print("Usage: /model | /model list | /model set <provider> <model>")
        return True
    if command == "/undo":
        _run_undo_last(workspace)
        return True
    if command == "/trace":
        _show_latest_trace(workspace)
        return True
    return False


def _build_runtime(workspace: str) -> tuple[AgentRuntime, MCPRuntime, str, str]:
    settings = SettingsStore(workspace).load()
    load_dotenv(workspace)
    api_key = settings.api_keys.get(settings.provider)
    client = ChatClient.from_options(
        provider=settings.provider,
        model=settings.model,
        api_key=api_key,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout,
    )
    tools = ToolRegistry(workspace=workspace)
    mcp_runtime = MCPRuntime(workspace=workspace, config_path=settings.mcp_config)
    mcp_runtime.mount(tools)
    memory = None if settings.no_memory else SessionMemory(workspace=workspace, session_id=settings.session)
    runtime = AgentRuntime(agent=LOCAL_AGENT, client=client, tools=tools, memory=memory)
    return runtime, mcp_runtime, client.cfg.provider, client.cfg.model


def interactive_chat(workspace: str) -> int:
    workspace = str(Path(workspace).resolve())
    try:
        runtime, mcp_runtime, provider, model = _build_runtime(workspace)
    except Exception as exc:  # noqa: BLE001
        print(f"failed to start YouAgent: {type(exc).__name__}: {exc}")
        print("Configure a model with: youagent model set <provider> <model>")
        return 1

    try:
        print(f"YouAgent ready | provider={provider} model={model} workspace={workspace}")
        print("Type /help for commands, /exit to quit.")
        while True:
            try:
                user_text = input("youagent> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not user_text:
                continue
            try:
                if user_text.startswith("/") and _handle_slash_command(user_text, workspace):
                    continue
            except KeyboardInterrupt:
                print()
                return 0

            events: list[dict[str, Any]] = []
            snapshot_dir = create_snapshot(workspace, user_text)
            try:
                reply = runtime.ask(
                    user_text,
                    event_callback=lambda evt: events.append(dict(evt)),
                )
                print(f"agent> {reply}")
            except Exception as exc:  # noqa: BLE001
                print(f"agent error: {type(exc).__name__}: {exc}")
                reply = f"ERROR: {type(exc).__name__}: {exc}"
            finally:
                undo_path = finalize_snapshot(workspace, snapshot_dir)
                undo = json.loads(undo_path.read_text(encoding="utf-8"))
                changes = len(undo.get("changes", []))
                trace_path = _write_trace(
                    workspace=workspace,
                    prompt=user_text,
                    events=events,
                    reply=reply,
                    snapshot_path=snapshot_dir,
                )
                print(f"[trace] {trace_path}")
                if changes:
                    print(f"[undo] {changes} change(s). Restore with: /undo")
    finally:
        mcp_runtime.close()


def one_shot(task: str, workspace: str) -> int:
    workspace = str(Path(workspace).resolve())
    try:
        runtime, mcp_runtime, provider, model = _build_runtime(workspace)
    except Exception as exc:  # noqa: BLE001
        print(f"failed to start YouAgent: {type(exc).__name__}: {exc}")
        return 1

    events: list[dict[str, Any]] = []
    snapshot_dir = create_snapshot(workspace, task)
    try:
        reply = runtime.ask(task, event_callback=lambda evt: events.append(dict(evt)))
        print(reply)
        undo_path = finalize_snapshot(workspace, snapshot_dir)
        undo = json.loads(undo_path.read_text(encoding="utf-8"))
        changes = len(undo.get("changes", []))
        trace_path = _write_trace(
            workspace=workspace,
            prompt=task,
            events=events,
            reply=reply,
            snapshot_path=snapshot_dir,
        )
        print(f"\n[trace] {trace_path}")
        if changes:
            print(f"[undo] {changes} change(s). Restore with: youagent undo last")
        return 0
    finally:
        mcp_runtime.close()


def main() -> int:
    argv = sys.argv[1:]
    workspace = os.getcwd()

    if not argv:
        return interactive_chat(workspace)

    if argv[0] in {"-h", "--help", "help"}:
        _print_help()
        return 0

    if argv[0] in LEGACY_COMMANDS:
        return classic_main()

    if argv[0] == "model":
        if len(argv) == 1 or argv[1] == "status":
            _model_status(workspace)
            return 0
        if argv[1] == "list":
            _model_list()
            return 0
        if argv[1] == "set" and len(argv) >= 4:
            _model_set(workspace, argv[2], argv[3])
            return 0
        print("Usage: youagent model status | model list | model set <provider> <model>")
        return 1

    if argv[0] == "undo":
        _run_undo_last(workspace)
        return 0

    if argv[0] == "trace":
        _show_latest_trace(workspace)
        return 0

    if argv[0] in ONE_SHOT_COMMANDS:
        # Keep compatibility for the experimental command set while the public entry stays `youagent`.
        from .code_cli import main as code_main

        return code_main()

    return one_shot(" ".join(argv), workspace)


if __name__ == "__main__":
    sys.exit(main())
