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
from .skills import SkillRegistry
from .tools import ToolRegistry


BASE_SYSTEM_PROMPT = (
    "You are YouAgent, a local-first computer agent. "
    "You help users inspect folders, organize files, run safe shell commands, "
    "fetch web content, automate browser tasks, and manage local workflows. "
    "Use tools when needed, but avoid risky or destructive actions unless the user explicitly asks. "
    "Prefer reversible operations, explain what you did, and mention risks. "
    "For file deletion, system changes, package installation, or commands with external side effects, "
    "ask for confirmation or provide a safe plan first. "
    "When a workspace skill matches the task, follow that skill's steps and safety rules. "
    "Keep answers concise and practical."
)

AGENT_INSTRUCTION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
)
AGENT_INSTRUCTIONS_MAX_CHARS = 20_000

LOCAL_AGENT = AgentProfile(
    name="youagent_local",
    system_prompt=BASE_SYSTEM_PROMPT,
    max_tool_rounds=10,
)


LEGACY_COMMANDS = {"chat", "serve", "status", "config", "heartbeat", "tasks"}
ONE_SHOT_COMMANDS = {"ask", "trace", "undo", "model"}


def _print_help() -> None:
    print(
        """YouAgent - local-first computer agent

Usage:
  youagent                         Start interactive chat
  youagent <task>                  Run one-shot task
  youagent init                    Create AGENTS.md for this workspace
  youagent skills init             Create default skills in .youagent/skills
  youagent skills list             List workspace skills
  youagent skill <name> [args...]  Run a specific workspace skill
  youagent model status            Show current model
  youagent model list              List provider presets
  youagent model set <provider> <model>
  youagent undo last               Restore last file snapshot
  youagent trace last              Show latest trace
  youagent chat                    Use classic chat mode
  youagent serve                   Start Web UI

Slash commands in interactive mode:
  /help
  /init
  /skills
  /skills init
  /skill <name> [args...]
  /model
  /model list
  /model set <provider> <model>
  /undo
  /trace
  /exit
""".strip()
    )


def _root_entries(workspace: str, limit: int = 80) -> list[str]:
    root = Path(workspace).resolve()
    ignored = {
        ".git",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "dist",
        "build",
        "target",
        "__pycache__",
        ".next",
        ".nuxt",
        ".turbo",
        ".cache",
        ".mini_worker",
        ".youagent",
    }
    entries: list[str] = []
    try:
        for item in sorted(root.iterdir(), key=lambda path: path.name.lower()):
            if item.name in ignored:
                continue
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{item.name}{suffix}")
            if len(entries) >= limit:
                break
    except OSError:
        return []
    return entries


def _detected_workspace_notes(workspace: str) -> list[str]:
    root = Path(workspace).resolve()
    notes: list[str] = []
    if (root / "package.json").exists():
        notes.append("- JavaScript/TypeScript project detected from `package.json`.")
    if (root / "pyproject.toml").exists():
        notes.append("- Python project detected from `pyproject.toml`.")
    if (root / "requirements.txt").exists():
        notes.append("- Python dependencies detected from `requirements.txt`.")
    if (root / "pom.xml").exists():
        notes.append("- Maven project detected from `pom.xml`.")
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        notes.append("- Gradle project detected.")
    if (root / "Dockerfile").exists():
        notes.append("- Dockerfile detected.")
    if not notes:
        notes.append("- General local workspace. Inspect files before making assumptions.")
    return notes


def _default_agents_md(workspace: str) -> str:
    root = Path(workspace).resolve()
    entries = _root_entries(workspace)
    entries_block = "\n".join(f"- `{entry}`" for entry in entries) or "- No root entries listed."
    notes_block = "\n".join(_detected_workspace_notes(workspace))
    return f"""# AGENTS.md

Instructions for AI agents working in this workspace.

## Workspace

- Name: `{root.name}`
- Path: `{root}`

## Product / task intent

Use this workspace as a local-first working area. You may inspect files, summarize content, organize information, run safe commands, and help with local workflows.

If this is a code project, first understand the project structure before suggesting changes. If this is a normal folder, treat it as a local computer workspace and avoid assuming it is a repository.

## Detected notes

{notes_block}

## Root entries

{entries_block}

## Operating rules

1. Inspect before acting. Read relevant files or list folders before making claims.
2. Prefer safe, reversible actions.
3. Do not delete, move, overwrite, install packages, change system settings, or run risky shell commands without explicit user confirmation.
4. For file organization tasks, first produce a preview plan, then ask for confirmation before applying changes.
5. Keep changes inside the current workspace unless the user explicitly gives another path.
6. Explain important tool use, risks, and suggested verification steps.
7. When changing files, keep the change minimal and easy to undo.

## Useful commands

Add project-specific commands here, for example:

```bash
# run tests
# npm test
# pytest

# lint / typecheck
# npm run lint
# npm run typecheck
```

## Notes for future agents

- Update this file when you learn stable project rules, workflows, or user preferences.
- Do not store secrets, API keys, tokens, or private credentials in this file.
"""


def _write_agents_md(workspace: str, force: bool = False) -> Path | None:
    path = Path(workspace).resolve() / "AGENTS.md"
    if path.exists() and not force:
        return None
    path.write_text(_default_agents_md(workspace), encoding="utf-8")
    return path


def _find_agent_instructions(workspace: str) -> Path | None:
    root = Path(workspace).resolve()
    for rel in AGENT_INSTRUCTION_FILES:
        candidate = root / rel
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_agent_instructions(workspace: str) -> tuple[str | None, str]:
    path = _find_agent_instructions(workspace)
    if path is None:
        return None, ""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")
    content = content.strip()
    if len(content) > AGENT_INSTRUCTIONS_MAX_CHARS:
        content = content[:AGENT_INSTRUCTIONS_MAX_CHARS] + "\n\n[truncated]"
    return str(path), content


def _agent_for_workspace(workspace: str) -> tuple[AgentProfile, str | None, str]:
    instruction_path, instructions = _load_agent_instructions(workspace)
    skills_prompt = SkillRegistry(workspace).catalog_prompt()
    prompt_parts = [BASE_SYSTEM_PROMPT]
    if instructions:
        prompt_parts.append(
            "Workspace instructions loaded from agent-readable documentation. "
            "Follow these instructions when they do not conflict with the user request or safety rules.\n\n"
            f"--- BEGIN WORKSPACE INSTRUCTIONS ({instruction_path}) ---\n"
            f"{instructions}\n"
            "--- END WORKSPACE INSTRUCTIONS ---"
        )
    if skills_prompt:
        prompt_parts.append(
            "Workspace skills are reusable task playbooks. Prefer them when the user task matches.\n\n"
            f"--- BEGIN WORKSPACE SKILLS ---\n{skills_prompt}\n--- END WORKSPACE SKILLS ---"
        )
    prompt = "\n\n".join(prompt_parts)
    return (
        AgentProfile(
            name="youagent_local",
            system_prompt=prompt,
            max_tool_rounds=LOCAL_AGENT.max_tool_rounds,
        ),
        instruction_path,
        skills_prompt,
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


def _run_init(workspace: str, force: bool = False) -> int:
    path = _write_agents_md(workspace, force=force)
    if path is None:
        existing = Path(workspace).resolve() / "AGENTS.md"
        print(f"AGENTS.md already exists: {existing}")
        print("Use `youagent init --force` to overwrite it.")
        return 0
    print(f"Created {path}")
    print("YouAgent will load this file automatically on the next request/session.")
    return 0


def _run_skills(workspace: str, args: list[str]) -> int:
    registry = SkillRegistry(workspace)
    command = args[0] if args else "list"
    if command == "init":
        written = registry.ensure_defaults(overwrite="--force" in args)
        if not written:
            print(f"Skills already exist in {registry.skills_dir}")
            print("Use `youagent skills init --force` to overwrite defaults.")
            return 0
        print(f"Created {len(written)} skill(s) in {registry.skills_dir}")
        for path in written:
            print(f"- {path.name}")
        return 0
    if command in {"list", "ls"}:
        skills = registry.list_skills()
        if not skills:
            print("No skills found. Run: youagent skills init")
            return 0
        for skill in skills:
            rel = skill.path.relative_to(Path(workspace).resolve())
            desc = f" - {skill.description}" if skill.description else ""
            print(f"- {skill.name} ({rel}){desc}")
        return 0
    print("Usage: youagent skills init|list")
    return 1


def _skill_task_prompt(workspace: str, skill_name: str, user_args: str) -> str | None:
    registry = SkillRegistry(workspace)
    skill = registry.get(skill_name)
    if skill is None:
        print(f"Skill not found: {skill_name}")
        print("Run `youagent skills list` to see available skills.")
        return None
    return registry.render_task_prompt(skill, user_args)


def _handle_slash_command(text: str, workspace: str) -> bool:
    parts = text.strip().split()
    command = parts[0].lower() if parts else ""

    if command in {"/exit", "/quit"}:
        raise KeyboardInterrupt
    if command == "/help":
        _print_help()
        return True
    if command == "/init":
        force = "--force" in parts
        _run_init(workspace, force=force)
        return True
    if command == "/skills":
        _run_skills(workspace, parts[1:])
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


def _build_runtime(workspace: str) -> tuple[AgentRuntime, MCPRuntime, str, str, str | None, str]:
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
    agent, instruction_path, skills_prompt = _agent_for_workspace(workspace)
    runtime = AgentRuntime(agent=agent, client=client, tools=tools, memory=memory)
    return runtime, mcp_runtime, client.cfg.provider, client.cfg.model, instruction_path, skills_prompt


def _prepare_user_text(workspace: str, user_text: str) -> str | None:
    parts = user_text.strip().split(maxsplit=2)
    if not parts or parts[0] != "/skill":
        return user_text
    if len(parts) < 2:
        print("Usage: /skill <name> [args...]")
        return None
    return _skill_task_prompt(workspace, parts[1], parts[2] if len(parts) > 2 else "")


def interactive_chat(workspace: str) -> int:
    workspace = str(Path(workspace).resolve())
    try:
        runtime, mcp_runtime, provider, model, instruction_path, skills_prompt = _build_runtime(workspace)
    except Exception as exc:  # noqa: BLE001
        print(f"failed to start YouAgent: {type(exc).__name__}: {exc}")
        print("Configure a model with: youagent model set <provider> <model>")
        return 1

    try:
        print(f"YouAgent ready | provider={provider} model={model} workspace={workspace}")
        if instruction_path:
            print(f"Loaded instructions: {instruction_path}")
        else:
            print("No AGENTS.md found. Run /init to create one.")
        if skills_prompt:
            print("Loaded workspace skills. Run /skills to list them.")
        else:
            print("No skills found. Run /skills init to create defaults.")
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
                    if user_text.startswith("/init") or user_text.startswith("/skills init"):
                        runtime, mcp_runtime, provider, model, instruction_path, skills_prompt = _build_runtime(workspace)
                        if instruction_path:
                            print(f"Reloaded instructions: {instruction_path}")
                        if skills_prompt:
                            print("Reloaded workspace skills.")
                    continue
            except KeyboardInterrupt:
                print()
                return 0

            prepared_text = _prepare_user_text(workspace, user_text)
            if prepared_text is None:
                continue
            events: list[dict[str, Any]] = []
            snapshot_dir = create_snapshot(workspace, user_text)
            try:
                reply = runtime.ask(
                    prepared_text,
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
        runtime, mcp_runtime, provider, model, instruction_path, skills_prompt = _build_runtime(workspace)
    except Exception as exc:  # noqa: BLE001
        print(f"failed to start YouAgent: {type(exc).__name__}: {exc}")
        return 1

    prepared_task = _prepare_user_text(workspace, task) or task
    events: list[dict[str, Any]] = []
    snapshot_dir = create_snapshot(workspace, task)
    try:
        if instruction_path:
            print(f"[instructions] {instruction_path}")
        if skills_prompt:
            print("[skills] loaded")
        reply = runtime.ask(prepared_task, event_callback=lambda evt: events.append(dict(evt)))
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

    if argv[0] == "init":
        return _run_init(workspace, force="--force" in argv)

    if argv[0] == "skills":
        return _run_skills(workspace, argv[1:])

    if argv[0] == "skill":
        if len(argv) < 2:
            print("Usage: youagent skill <name> [args...]")
            return 1
        prompt = _skill_task_prompt(workspace, argv[1], " ".join(argv[2:]))
        if prompt is None:
            return 1
        return one_shot(prompt, workspace)

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
