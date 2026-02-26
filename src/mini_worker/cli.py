import argparse
import sys

from .agents import get_agent
from .env import load_dotenv
from .llm import ChatClient
from .memory import SessionMemory
from .runtime import AgentRuntime
from .server import ServerConfig, run_web_server
from .tools import ToolRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="youagent")
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Start interactive agent chat")
    chat.add_argument(
        "--agent", default="manus_like", choices=["manus_like", "miniagent_like"]
    )
    chat.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "openrouter", "minimax", "custom"],
    )
    chat.add_argument("--model", default="gpt-4.1-mini")
    chat.add_argument("--api-key", default=None)
    chat.add_argument("--base-url", default=None)
    chat.add_argument("--timeout", type=int, default=60)
    chat.add_argument("--workspace", default=".")
    chat.add_argument("--session", default="default")
    chat.add_argument("--no-memory", action="store_true")

    serve = sub.add_parser("serve", help="Start local web client")
    serve.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "openrouter", "minimax", "custom"],
    )
    serve.add_argument("--model", default="gpt-4.1-mini")
    serve.add_argument("--api-key", default=None)
    serve.add_argument("--base-url", default=None)
    serve.add_argument("--timeout", type=int, default=60)
    serve.add_argument("--workspace", default=".")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7788)
    serve.add_argument("--no-memory", action="store_true")
    return parser


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
) -> int:
    load_dotenv(workspace)
    agent = get_agent(agent_name)
    client = ChatClient.from_options(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout,
    )
    tools = ToolRegistry(workspace=workspace)
    memory = (
        None if no_memory else SessionMemory(workspace=workspace, session_id=session)
    )
    runtime = AgentRuntime(agent=agent, client=client, tools=tools, memory=memory)

    print(
        f"[{agent.name}] ready | provider={provider} model={model} session={session} | type 'exit' to quit."
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
            reply = runtime.ask(user_text)
        except Exception as exc:  # noqa: BLE001
            print(f"agent error: {exc}")
            continue

        print(f"agent> {reply}")


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
) -> int:
    load_dotenv(workspace)
    client = ChatClient.from_options(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout,
    )
    cfg = ServerConfig(
        host=host,
        port=port,
        workspace=workspace,
        provider=provider,
        model=model,
        no_memory=no_memory,
    )
    return run_web_server(cfg=cfg, client=client)


def main() -> int:
    parser = build_parser()
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
        )

    print("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
