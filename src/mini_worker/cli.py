import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

from .agents import get_agent
from .config import available_providers
from .env import load_dotenv
from .llm import ChatClient
from .mcp import MCPRuntime
from .memory import SessionMemory
from .observability import Observability
from .runtime import AgentRuntime
from .server import ServerConfig, run_web_server
from .settings import AppSettings, SettingsStore
from .tasking import ScheduledTask, TaskStore, run_due_tasks
from .tools import ToolRegistry


def build_parser(defaults: AppSettings) -> argparse.ArgumentParser:
    providers = available_providers()
    parser = argparse.ArgumentParser(prog="youagent")
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Start interactive agent chat")
    chat.add_argument(
        "--agent",
        default=defaults.agent,
        choices=["manus_like", "miniagent_like"],
    )
    chat.add_argument(
        "--provider",
        default=defaults.provider,
        choices=providers,
    )
    chat.add_argument("--model", default=defaults.model)
    chat.add_argument("--api-key", default=None)
    chat.add_argument("--base-url", default=defaults.base_url)
    chat.add_argument("--timeout", type=int, default=defaults.timeout)
    chat.add_argument("--workspace", default=defaults.workspace)
    chat.add_argument("--session", default=defaults.session)
    chat.add_argument("--no-memory", action="store_true", default=defaults.no_memory)
    chat.add_argument("--mcp-config", default=defaults.mcp_config)

    serve = sub.add_parser("serve", help="Start local web client")
    serve.add_argument(
        "--provider",
        default=defaults.provider,
        choices=providers,
    )
    serve.add_argument("--model", default=defaults.model)
    serve.add_argument("--api-key", default=None)
    serve.add_argument("--base-url", default=defaults.base_url)
    serve.add_argument("--timeout", type=int, default=defaults.timeout)
    serve.add_argument("--workspace", default=defaults.workspace)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7788)
    serve.add_argument("--no-memory", action="store_true", default=defaults.no_memory)
    serve.add_argument("--mcp-config", default=defaults.mcp_config)
    serve.add_argument("--scheduler", action="store_true", default=False)

    status = sub.add_parser("status", help="Show current local configuration")
    status.add_argument("--workspace", default=defaults.workspace)

    config = sub.add_parser("config", help="Show or update default configuration")
    config.add_argument("--workspace", default=defaults.workspace)
    config.add_argument("--provider", choices=providers, default=None)
    config.add_argument("--model", default=None)
    config.add_argument("--base-url", default=None)
    config.add_argument(
        "--agent", choices=["manus_like", "miniagent_like"], default=None
    )
    config.add_argument("--session", default=None)
    config.add_argument("--timeout", type=int, default=None)
    config.add_argument("--mcp-config", default=None)
    config.add_argument("--api-key", default=None)
    config.add_argument(
        "--api-key-provider",
        choices=providers,
        default=None,
        help="Provider name for --api-key, default to current provider",
    )
    mem_group = config.add_mutually_exclusive_group()
    mem_group.add_argument("--no-memory", dest="no_memory", action="store_true")
    mem_group.add_argument("--with-memory", dest="with_memory", action="store_true")

    heartbeat = sub.add_parser("heartbeat", help="Run periodic prompt execution")
    heartbeat.add_argument(
        "--agent",
        default=defaults.agent,
        choices=["manus_like", "miniagent_like"],
    )
    heartbeat.add_argument(
        "--provider",
        default=defaults.provider,
        choices=providers,
    )
    heartbeat.add_argument("--model", default=defaults.model)
    heartbeat.add_argument("--api-key", default=None)
    heartbeat.add_argument("--base-url", default=defaults.base_url)
    heartbeat.add_argument("--timeout", type=int, default=defaults.timeout)
    heartbeat.add_argument("--workspace", default=defaults.workspace)
    heartbeat.add_argument("--session", default=defaults.session)
    heartbeat.add_argument("--mcp-config", default=defaults.mcp_config)
    heartbeat.add_argument(
        "--message",
        required=True,
        help="Prompt sent every cycle",
    )
    heartbeat.add_argument("--every", type=int, default=300, help="Interval seconds")
    heartbeat.add_argument("--count", type=int, default=1, help="Run cycles")
    heartbeat.add_argument(
        "--no-memory", action="store_true", default=defaults.no_memory
    )

    tasks = sub.add_parser("tasks", help="Manage scheduled tasks")
    tasks_sub = tasks.add_subparsers(dest="tasks_command", required=True)

    tasks_add = tasks_sub.add_parser("add", help="Add a scheduled task")
    tasks_add.add_argument("--name", required=True)
    tasks_add.add_argument("--prompt", required=True)
    tasks_add.add_argument("--provider", default=defaults.provider, choices=providers)
    tasks_add.add_argument("--model", default=defaults.model)
    tasks_add.add_argument("--agent", default=defaults.agent, choices=["manus_like", "miniagent_like"])
    tasks_add.add_argument("--session", default=defaults.session)
    tasks_add.add_argument("--base-url", default=defaults.base_url)
    tasks_add.add_argument("--workspace", default=defaults.workspace)
    tasks_add.add_argument("--every", type=int, default=300)
    tasks_add.add_argument("--no-memory", action="store_true", default=defaults.no_memory)
    tasks_add.add_argument("--mcp-config", default=defaults.mcp_config)

    tasks_list = tasks_sub.add_parser("list", help="List scheduled tasks")
    tasks_list.add_argument("--workspace", default=defaults.workspace)

    tasks_del = tasks_sub.add_parser("delete", help="Delete task by id")
    tasks_del.add_argument("--workspace", default=defaults.workspace)
    tasks_del.add_argument("--id", required=True)

    tasks_run = tasks_sub.add_parser("run", help="Run due tasks once")
    tasks_run.add_argument("--workspace", default=defaults.workspace)

    tasks_start = tasks_sub.add_parser("start", help="Run scheduler loop")
    tasks_start.add_argument("--workspace", default=defaults.workspace)
    tasks_start.add_argument("--poll", type=int, default=5)
    return parser


def _resolve_api_key(
    api_key: str | None, provider: str, settings: AppSettings
) -> str | None:
    if api_key:
        return api_key
    return settings.api_keys.get(provider)


def _save_defaults(
    workspace: str,
    *,
    provider: str,
    model: str,
    base_url: str | None,
    agent: str,
    timeout: int,
    session: str,
    no_memory: bool,
    mcp_config: str | None,
    api_key: str | None,
) -> None:
    store = SettingsStore(workspace)
    settings = store.load()
    settings.provider = provider
    settings.model = model
    settings.base_url = base_url
    settings.agent = agent
    settings.timeout = timeout
    settings.workspace = workspace
    settings.session = session
    settings.no_memory = no_memory
    settings.mcp_config = mcp_config
    if api_key:
        settings.api_keys[provider] = api_key
    store.save(settings)


def run_chat(
    agent_name: str,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout: int,
    workspace: str,
    session: str,
    no_memory: bool,
    mcp_config: str | None,
) -> int:
    obs = Observability(workspace)
    settings = SettingsStore(workspace).load()
    final_api_key = _resolve_api_key(api_key=api_key, provider=provider, settings=settings)

    load_dotenv(workspace)
    agent = get_agent(agent_name)
    client = ChatClient.from_options(
        provider=provider,
        model=model,
        api_key=final_api_key,
        base_url=base_url,
        timeout_seconds=timeout,
    )
    tools = ToolRegistry(workspace=workspace)
    mcp_runtime = MCPRuntime(workspace=workspace, config_path=mcp_config)
    try:
        mcp_runtime.mount(tools)
        memory = (
            None if no_memory else SessionMemory(workspace=workspace, session_id=session)
        )
        runtime = AgentRuntime(agent=agent, client=client, tools=tools, memory=memory)
        _save_defaults(
            workspace=workspace,
            provider=client.cfg.provider,
            model=client.cfg.model,
            base_url=client.cfg.base_url,
            agent=agent_name,
            timeout=timeout,
            session=session,
            no_memory=no_memory,
            mcp_config=mcp_config,
            api_key=final_api_key,
        )

        print(
            f"[{agent.name}] ready | provider={provider} model={model} session={session} | type 'exit' to quit."
        )
        if mcp_runtime.mounted_tools:
            print(
                f"[mcp] mounted {len(mcp_runtime.mounted_tools)} tools from {len(mcp_runtime.clients)} server(s)"
            )
        while True:
            try:
                user_text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0

            if not user_text:
                continue
            if user_text.lower() in {"exit", "quit"}:
                return 0

            try:
                reply = runtime.ask(
                    user_text,
                    event_callback=lambda evt: obs.record(
                        "runtime_event",
                        mode="chat",
                        session=session,
                        phase=evt.get("phase"),
                        detail=evt,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                print(f"agent error: {exc}")
                obs.record("chat_error", error=str(exc), session=session)
                continue

            print(f"agent> {reply}")
            obs.record("chat_reply", session=session, chars=len(reply))
    finally:
        mcp_runtime.close()


def run_serve(
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout: int,
    workspace: str,
    host: str,
    port: int,
    no_memory: bool,
    mcp_config: str | None,
    scheduler: bool,
) -> int:
    obs = Observability(workspace)
    settings = SettingsStore(workspace).load()
    final_api_key = _resolve_api_key(api_key=api_key, provider=provider, settings=settings)

    load_dotenv(workspace)
    client = ChatClient.from_options(
        provider=provider,
        model=model,
        api_key=final_api_key,
        base_url=base_url,
        timeout_seconds=timeout,
    )
    _save_defaults(
        workspace=workspace,
        provider=client.cfg.provider,
        model=client.cfg.model,
        base_url=client.cfg.base_url,
        agent=settings.agent,
        timeout=timeout,
        session=settings.session,
        no_memory=no_memory,
        mcp_config=mcp_config,
        api_key=final_api_key,
    )
    cfg = ServerConfig(
        host=host,
        port=port,
        workspace=workspace,
        provider=client.cfg.provider,
        model=client.cfg.model,
        no_memory=no_memory,
        mcp_config=mcp_config,
        scheduler=scheduler,
        observability=obs,
    )
    return run_web_server(cfg=cfg, client=client)


def run_status(workspace: str) -> int:
    store = SettingsStore(workspace)
    settings = store.load()
    task_count = len(TaskStore(workspace).list())
    obs = Observability(workspace)
    security_path = Path(workspace).resolve() / ".mini_worker" / "security.json"
    mcp_path = None
    mcp_exists = False
    if settings.mcp_config:
        path = Path(settings.mcp_config)
        if not path.is_absolute():
            path = Path(workspace).resolve() / path
        mcp_path = str(path.resolve())
        mcp_exists = path.exists()
    payload = {
        "workspace": str(Path(workspace).resolve()),
        "config_path": str(store.path),
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "agent": settings.agent,
        "timeout": settings.timeout,
        "session": settings.session,
        "no_memory": settings.no_memory,
        "mcp_config": settings.mcp_config,
        "mcp_config_path": mcp_path,
        "mcp_config_exists": mcp_exists,
        "tasks_count": task_count,
        "metrics": obs.metrics().get("counters", {}),
        "security_config_path": str(security_path),
        "security_config_exists": security_path.exists(),
        "api_keys_configured": sorted(settings.api_keys.keys()),
        "providers": available_providers(),
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def run_config(args: argparse.Namespace) -> int:
    store = SettingsStore(args.workspace)
    settings = store.load()

    changed = False
    if args.provider is not None:
        settings.provider = args.provider
        changed = True
    if args.model is not None:
        settings.model = args.model
        changed = True
    if args.base_url is not None:
        settings.base_url = args.base_url.strip() or None
        changed = True
    if args.agent is not None:
        settings.agent = args.agent
        changed = True
    if args.session is not None:
        settings.session = args.session
        changed = True
    if args.timeout is not None:
        settings.timeout = args.timeout
        changed = True
    if args.mcp_config is not None:
        settings.mcp_config = args.mcp_config.strip() or None
        changed = True
    if args.no_memory:
        settings.no_memory = True
        changed = True
    if args.with_memory:
        settings.no_memory = False
        changed = True
    if args.api_key is not None:
        key_provider = args.api_key_provider or settings.provider
        cleaned_key = args.api_key.strip()
        if cleaned_key:
            settings.api_keys[key_provider] = cleaned_key
        else:
            settings.api_keys.pop(key_provider, None)
        changed = True

    settings.workspace = args.workspace
    if changed:
        store.save(settings)

    print(
        json.dumps(
            {
                "updated": changed,
                "config_path": str(store.path),
                **settings.to_dict(),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


def run_heartbeat(
    agent_name: str,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout: int,
    workspace: str,
    session: str,
    message: str,
    every: int,
    count: int,
    no_memory: bool,
    mcp_config: str | None,
) -> int:
    obs = Observability(workspace)
    if every < 1:
        raise ValueError("--every must be >= 1")
    if count < 1:
        raise ValueError("--count must be >= 1")

    settings = SettingsStore(workspace).load()
    final_api_key = _resolve_api_key(api_key=api_key, provider=provider, settings=settings)

    load_dotenv(workspace)
    client = ChatClient.from_options(
        provider=provider,
        model=model,
        api_key=final_api_key,
        base_url=base_url,
        timeout_seconds=timeout,
    )
    tools = ToolRegistry(workspace=workspace)
    mcp_runtime = MCPRuntime(workspace=workspace, config_path=mcp_config)
    try:
        mcp_runtime.mount(tools)
        memory = (
            None if no_memory else SessionMemory(workspace=workspace, session_id=session)
        )
        runtime = AgentRuntime(
            agent=get_agent(agent_name),
            client=client,
            tools=tools,
            memory=memory,
        )
        _save_defaults(
            workspace=workspace,
            provider=client.cfg.provider,
            model=client.cfg.model,
            base_url=client.cfg.base_url,
            agent=agent_name,
            timeout=timeout,
            session=session,
            no_memory=no_memory,
            mcp_config=mcp_config,
            api_key=final_api_key,
        )

        if mcp_runtime.mounted_tools:
            print(
                f"[mcp] mounted {len(mcp_runtime.mounted_tools)} tools from {len(mcp_runtime.clients)} server(s)"
            )
        for idx in range(1, count + 1):
            print(f"[heartbeat] cycle={idx}/{count} session={session}")
            reply = runtime.ask(
                message,
                event_callback=lambda evt: obs.record(
                    "runtime_event",
                    mode="heartbeat",
                    session=session,
                    phase=evt.get("phase"),
                    detail=evt,
                ),
            )
            print(f"agent> {reply}")
            obs.record("heartbeat_reply", session=session, chars=len(reply))
            if idx < count:
                time.sleep(every)
        return 0
    finally:
        mcp_runtime.close()


def _run_task_once(
    task: ScheduledTask, progress_callback: Callable[[dict[str, object]], None]
) -> tuple[bool, str]:
    settings = SettingsStore(task.workspace).load()
    api_key = settings.api_keys.get(task.provider)
    load_dotenv(task.workspace)
    client = ChatClient.from_options(
        provider=task.provider,
        model=task.model,
        api_key=api_key,
        base_url=task.base_url,
        timeout_seconds=settings.timeout,
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


def run_tasks(args: argparse.Namespace) -> int:
    store = TaskStore(args.workspace)
    obs = Observability(args.workspace)
    cmd = args.tasks_command
    if cmd == "add":
        task = store.add(
            name=args.name,
            prompt=args.prompt,
            provider=args.provider,
            model=args.model,
            agent=args.agent,
            session=args.session,
            workspace=args.workspace,
            base_url=args.base_url,
            interval_seconds=max(10, int(args.every)),
            no_memory=bool(args.no_memory),
            mcp_config=args.mcp_config,
        )
        obs.record("task_added", task_id=task.id, name=task.name)
        print(json.dumps(task.to_dict(), ensure_ascii=True, indent=2))
        return 0

    if cmd == "list":
        payload = [t.to_dict() for t in store.list()]
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    if cmd == "delete":
        ok = store.delete(args.id)
        if ok:
            obs.record("task_deleted", task_id=args.id)
        print(json.dumps({"ok": ok, "id": args.id}, ensure_ascii=True, indent=2))
        return 0

    if cmd == "run":
        executed = run_due_tasks(
            store,
            _run_task_once,
            on_event=lambda e, p: obs.record(e, **p),
        )
        print(json.dumps({"executed": executed}, ensure_ascii=True, indent=2))
        return 0

    if cmd == "start":
        poll = max(1, int(args.poll))
        print(f"[scheduler] running, workspace={args.workspace}, poll={poll}s")
        try:
            while True:
                executed = run_due_tasks(
                    store,
                    _run_task_once,
                    on_event=lambda e, p: obs.record(e, **p),
                )
                if executed:
                    print(f"[scheduler] executed={executed}")
                time.sleep(poll)
        except KeyboardInterrupt:
            print("\n[scheduler] stopped")
            return 0
    return 1


def main() -> int:
    defaults = SettingsStore(os.getcwd()).load()
    parser = build_parser(defaults)
    args = parser.parse_args()

    if args.command == "chat":
        return run_chat(
            agent_name=args.agent,
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
            timeout=args.timeout,
            workspace=args.workspace,
            session=args.session,
            no_memory=args.no_memory,
            mcp_config=args.mcp_config,
        )

    if args.command == "serve":
        return run_serve(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
            timeout=args.timeout,
            workspace=args.workspace,
            host=args.host,
            port=args.port,
            no_memory=args.no_memory,
            mcp_config=args.mcp_config,
            scheduler=args.scheduler,
        )

    if args.command == "status":
        return run_status(workspace=args.workspace)

    if args.command == "config":
        return run_config(args)

    if args.command == "heartbeat":
        return run_heartbeat(
            agent_name=args.agent,
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
            timeout=args.timeout,
            workspace=args.workspace,
            session=args.session,
            message=args.message,
            every=args.every,
            count=args.count,
            no_memory=args.no_memory,
            mcp_config=args.mcp_config,
        )

    if args.command == "tasks":
        return run_tasks(args)

    print("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
