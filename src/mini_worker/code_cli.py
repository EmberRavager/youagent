import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .agents import AgentProfile
from .config import PROVIDER_PRESETS, available_providers
from .env import load_dotenv
from .llm import ChatClient
from .mcp import MCPRuntime
from .memory import SessionMemory
from .runtime import AgentRuntime
from .settings import SettingsStore
from .tools import ToolRegistry


IGNORED_DIRS = {
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

SNAPSHOT_MAX_FILES = 2000
SNAPSHOT_MAX_FILE_BYTES = 1_000_000

MODEL_EXAMPLES = {
    "openai": ["gpt-4.1-mini", "gpt-4.1", "o4-mini"],
    "openrouter": ["anthropic/claude-sonnet-4", "openai/gpt-4.1", "deepseek/deepseek-chat"],
    "minimax": ["MiniMax-M2.5"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "groq": ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"],
    "anthropic": ["claude-sonnet-4", "claude-3-7-sonnet-latest"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "zhipu": ["glm-4-plus", "glm-4-air"],
    "volcengine": ["doubao-seed-1-6", "deepseek-v3"],
    "vllm": ["local-model-name"],
    "custom": ["any-openai-compatible-model"],
}


@dataclass
class ProjectProfile:
    workspace: str
    project_types: list[str] = field(default_factory=list)
    package_manager: str | None = None
    entrypoints: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    important_files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        rel_parts = path.parts
    return any(part in IGNORED_DIRS for part in rel_parts)


def _iter_workspace_files(root: Path):
    for candidate in root.rglob("*"):
        if _is_ignored(candidate, root):
            continue
        if candidate.is_file() and not candidate.is_symlink():
            yield candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_files(root: Path, names: set[str], limit: int = 80) -> list[str]:
    hits: list[str] = []
    for candidate in _iter_workspace_files(root):
        if len(hits) >= limit:
            break
        if candidate.name in names:
            hits.append(_relative(candidate, root))
    return sorted(hits)


def scan_project(workspace: str) -> ProjectProfile:
    root = Path(workspace).resolve()
    profile = ProjectProfile(workspace=str(root))

    package_json = root / "package.json"
    if package_json.exists():
        profile.important_files.append("package.json")
        pkg = _read_json(package_json)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts", {}), dict) else {}

        if "vite" in deps:
            profile.project_types.append("Vite")
        if "react" in deps:
            profile.project_types.append("React")
        if "vue" in deps:
            profile.project_types.append("Vue")
        if "next" in deps:
            profile.project_types.append("Next.js")
        if "typescript" in deps:
            profile.project_types.append("TypeScript")
        if "express" in deps or "fastify" in deps:
            profile.project_types.append("Node.js API")

        if (root / "pnpm-lock.yaml").exists():
            profile.package_manager = "pnpm"
        elif (root / "yarn.lock").exists():
            profile.package_manager = "yarn"
        elif (root / "package-lock.json").exists():
            profile.package_manager = "npm"
        else:
            profile.package_manager = "npm"

        for script_name in ("test", "lint", "typecheck", "build"):
            if script_name in scripts:
                profile.test_commands.append(f"{profile.package_manager} run {script_name}")

    if (root / "pyproject.toml").exists():
        profile.project_types.append("Python")
        profile.important_files.append("pyproject.toml")
        if (root / "pytest.ini").exists() or (root / "tests").exists():
            profile.test_commands.append("pytest")

    if (root / "requirements.txt").exists():
        profile.project_types.append("Python")
        profile.important_files.append("requirements.txt")

    if (root / "pom.xml").exists():
        profile.project_types.append("Java / Maven")
        profile.important_files.append("pom.xml")
        profile.test_commands.append("mvn test")

    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        profile.project_types.append("Java / Gradle")
        profile.test_commands.append("./gradlew test")

    profile.entrypoints.extend(
        _find_files(
            root,
            {
                "main.ts",
                "main.tsx",
                "main.js",
                "main.jsx",
                "index.ts",
                "index.tsx",
                "app.py",
                "main.py",
                "Application.java",
            },
            limit=30,
        )
    )
    profile.important_files.extend(
        _find_files(
            root,
            {
                "README.md",
                "README_CN.md",
                "tsconfig.json",
                "vite.config.ts",
                "next.config.js",
                "Dockerfile",
                "docker-compose.yml",
            },
            limit=50,
        )
    )

    profile.project_types = sorted(set(profile.project_types)) or ["Unknown"]
    profile.entrypoints = sorted(set(profile.entrypoints))
    profile.important_files = sorted(set(profile.important_files))
    profile.test_commands = sorted(set(profile.test_commands))

    if not profile.entrypoints:
        profile.notes.append("No obvious entrypoint detected yet.")
    if not profile.test_commands:
        profile.notes.append("No obvious test command detected yet.")
    return profile


def _youagent_dir(workspace: str) -> Path:
    return Path(workspace).resolve() / ".youagent"


def save_project_profile(profile: ProjectProfile) -> Path:
    out_dir = _youagent_dir(profile.workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "project.json"
    path.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return (cleaned[:48] or "task").strip("-")


def _snapshot_root(workspace: str) -> Path:
    return _youagent_dir(workspace) / "snapshots"


def create_snapshot(workspace: str, prompt: str) -> Path:
    root = Path(workspace).resolve()
    snapshot_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slug(prompt)}"
    snapshot_dir = _snapshot_root(workspace) / snapshot_id
    before_dir = snapshot_dir / "before"
    before_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    count = 0
    for candidate in _iter_workspace_files(root):
        if count >= SNAPSHOT_MAX_FILES:
            skipped.append("snapshot file limit reached")
            break
        try:
            size = candidate.stat().st_size
            rel = _relative(candidate, root)
            if size > SNAPSHOT_MAX_FILE_BYTES:
                skipped.append(f"{rel} > {SNAPSHOT_MAX_FILE_BYTES} bytes")
                continue
            dest = before_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, dest)
            files[rel] = {"sha256": _sha256(candidate), "size": size}
            count += 1
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{candidate}: {type(exc).__name__}: {exc}")

    metadata = {
        "id": snapshot_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workspace": str(root),
        "max_files": SNAPSHOT_MAX_FILES,
        "max_file_bytes": SNAPSHOT_MAX_FILE_BYTES,
        "files": files,
        "skipped": skipped[:200],
    }
    (snapshot_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return snapshot_dir


def finalize_snapshot(workspace: str, snapshot_dir: Path) -> Path:
    root = Path(workspace).resolve()
    metadata_path = snapshot_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    before_files: dict[str, dict[str, Any]] = metadata.get("files", {})

    current_files: dict[str, dict[str, Any]] = {}
    for candidate in _iter_workspace_files(root):
        try:
            size = candidate.stat().st_size
            rel = _relative(candidate, root)
            if size > SNAPSHOT_MAX_FILE_BYTES:
                current_files[rel] = {"sha256": None, "size": size, "large": True}
            else:
                current_files[rel] = {"sha256": _sha256(candidate), "size": size}
        except Exception:
            continue

    changes: list[dict[str, Any]] = []
    for rel, before in before_files.items():
        current = current_files.get(rel)
        if current is None:
            changes.append({"path": rel, "action": "deleted"})
        elif current.get("sha256") != before.get("sha256"):
            changes.append({"path": rel, "action": "modified"})

    for rel in sorted(set(current_files) - set(before_files)):
        changes.append({"path": rel, "action": "created"})

    undo = {
        "snapshot_id": metadata.get("id"),
        "created_at": metadata.get("created_at"),
        "finalized_at": datetime.now().isoformat(timespec="seconds"),
        "workspace": str(root),
        "changes": changes,
        "limitations": [
            "Only regular workspace files up to the snapshot size limit are restored.",
            "External side effects from shell commands are not reversible.",
            "Ignored directories such as .git, node_modules, .venv, .youagent and build outputs are not snapshotted.",
        ],
    }
    undo_path = snapshot_dir / "undo.json"
    undo_path.write_text(json.dumps(undo, ensure_ascii=False, indent=2), encoding="utf-8")
    return undo_path


def _snapshot_dirs(workspace: str) -> list[Path]:
    root = _snapshot_root(workspace)
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "undo.json").exists())


def run_undo(args: argparse.Namespace) -> int:
    snapshots = _snapshot_dirs(args.workspace)
    if not snapshots:
        print("No undo snapshots found.")
        return 0

    if args.undo_command == "list":
        for path in snapshots[-20:]:
            undo = json.loads((path / "undo.json").read_text(encoding="utf-8"))
            print(f"{path.name} changes={len(undo.get('changes', []))}")
        return 0

    snapshot = snapshots[-1]
    undo = json.loads((snapshot / "undo.json").read_text(encoding="utf-8"))
    changes = undo.get("changes", [])
    if not changes:
        print(f"Latest snapshot has no file changes: {snapshot.name}")
        return 0

    if not args.yes:
        try:
            answer = input(f"Restore {len(changes)} change(s) from {snapshot.name}? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if answer not in {"y", "yes"}:
            print("Undo cancelled.")
            return 0

    workspace = Path(args.workspace).resolve()
    before_dir = snapshot / "before"
    restored = 0
    removed = 0
    for change in changes:
        rel = str(change.get("path", ""))
        action = str(change.get("action", ""))
        if not rel:
            continue
        target = (workspace / rel).resolve()
        if workspace not in target.parents and target != workspace:
            continue

        backup = before_dir / rel
        if action in {"modified", "deleted"} and backup.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            restored += 1
        elif action == "created" and target.exists() and target.is_file():
            target.unlink()
            removed += 1

    print(f"Undo complete: restored={restored}, removed_created={removed}")
    return 0


def write_trace(
    *,
    workspace: str,
    prompt: str,
    profile: ProjectProfile,
    events: list[dict[str, Any]],
    reply: str,
    snapshot_path: Path | None = None,
) -> Path:
    runs = _youagent_dir(workspace) / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = runs / f"{ts}-{_slug(prompt)}.md"

    lines = [
        "# YouAgent Code Trace",
        "",
        f"- Time: {datetime.now().isoformat(timespec='seconds')}",
        f"- Workspace: `{Path(workspace).resolve()}`",
    ]
    if snapshot_path is not None:
        lines.append(f"- Undo snapshot: `{snapshot_path}`")
    lines.extend(
        [
            "",
            "## Goal",
            "",
            prompt.strip(),
            "",
            "## Project Profile",
            "",
            "```json",
            profile.to_prompt_context(),
            "```",
            "",
            "## Runtime Events",
            "",
        ]
    )
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
        lines.append("No events captured.")

    lines.extend(
        [
            "",
            "## Final Answer",
            "",
            reply.strip() or "(empty)",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


CODING_AGENT = AgentProfile(
    name="coding_agent",
    system_prompt=(
        "You are YouAgent Code, a local-first coding agent harness. "
        "Use tools to inspect the repository before making claims. "
        "Be transparent: explain the plan, files inspected, commands used, and risks. "
        "Prefer safe, reversible actions. Do not modify files unless the user explicitly asks for changes. "
        "When suggesting modifications, prefer patch-style summaries and mention tests to run. "
        "Keep final answers concise and practical."
    ),
    max_tool_rounds=10,
)


def build_parser(defaults: Any) -> argparse.ArgumentParser:
    providers = available_providers()
    parser = argparse.ArgumentParser(
        prog="youagent-code",
        description="Local-first coding agent CLI with project scanning, model switching, undo and trace output.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", default=defaults.workspace)

    init = sub.add_parser("init", parents=[common], help="Scan project and write .youagent/project.json")
    init.add_argument("--json", action="store_true", help="Print raw project profile JSON")

    ask = sub.add_parser("ask", parents=[common], help="Ask the coding agent about this repository")
    ask.add_argument("prompt", nargs="+", help="Task or question for the coding agent")
    ask.add_argument("--provider", default=defaults.provider, choices=providers)
    ask.add_argument("--model", default=defaults.model)
    ask.add_argument("--api-key", default=None)
    ask.add_argument("--base-url", default=defaults.base_url)
    ask.add_argument("--timeout", type=int, default=defaults.timeout)
    ask.add_argument("--session", default="code")
    ask.add_argument("--no-memory", action="store_true", default=defaults.no_memory)
    ask.add_argument("--mcp-config", default=defaults.mcp_config)
    ask.add_argument("--no-trace", action="store_true", help="Do not write .youagent/runs trace file")
    ask.add_argument("--no-snapshot", action="store_true", help="Disable undo snapshot for this task")

    trace = sub.add_parser("trace", parents=[common], help="Show trace files")
    trace.add_argument("trace_command", nargs="?", default="last", choices=["last", "list"])

    undo = sub.add_parser("undo", parents=[common], help="Restore files from a previous YouAgent snapshot")
    undo.add_argument("undo_command", nargs="?", default="last", choices=["last", "list"])
    undo.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    model = sub.add_parser("model", parents=[common], help="Show or update model configuration")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_sub.add_parser("status", help="Show current model configuration")
    model_sub.add_parser("list", help="List supported providers and example model names")
    model_set = model_sub.add_parser("set", help="Set default provider/model for this workspace")
    model_set.add_argument("--provider", required=True, choices=providers)
    model_set.add_argument("--model", required=True)
    model_set.add_argument("--base-url", default=None)
    model_set.add_argument("--api-key", default=None)
    return parser


def run_init(args: argparse.Namespace) -> int:
    profile = scan_project(args.workspace)
    path = save_project_profile(profile)
    if args.json:
        print(profile.to_prompt_context())
    else:
        print(f"YouAgent Code initialized: {path}")
        print(f"Project types: {', '.join(profile.project_types)}")
        if profile.package_manager:
            print(f"Package manager: {profile.package_manager}")
        if profile.test_commands:
            print("Suggested commands:")
            for cmd in profile.test_commands:
                print(f"- {cmd}")
        print("Try: youagent-code ask \"这个项目是干嘛的？\"")
    return 0


def run_trace(args: argparse.Namespace) -> int:
    runs = _youagent_dir(args.workspace) / "runs"
    files = sorted(runs.glob("*.md")) if runs.exists() else []
    if not files:
        print("No trace files found. Run: youagent-code ask \"分析这个项目\"")
        return 0
    if args.trace_command == "list":
        for path in files[-20:]:
            print(path)
        return 0
    print(files[-1].read_text(encoding="utf-8"))
    return 0


def run_model(args: argparse.Namespace) -> int:
    store = SettingsStore(args.workspace)
    settings = store.load()

    if args.model_command == "status":
        payload = {
            "provider": settings.provider,
            "model": settings.model,
            "base_url": settings.base_url,
            "workspace": str(Path(args.workspace).resolve()),
            "config_path": str(store.path),
            "api_keys_configured": sorted(settings.api_keys.keys()),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.model_command == "list":
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
        print("\nNote: the low-level client uses OpenAI-compatible /chat/completions. For native-only models, use OpenRouter, vLLM or a custom compatible gateway.")
        return 0

    if args.model_command == "set":
        settings.provider = args.provider
        settings.model = args.model
        if args.base_url is not None:
            settings.base_url = args.base_url.strip() or None
        if args.api_key is not None and args.api_key.strip():
            settings.api_keys[args.provider] = args.api_key.strip()
        store.save(settings)
        print(
            json.dumps(
                {
                    "updated": True,
                    "provider": settings.provider,
                    "model": settings.model,
                    "base_url": settings.base_url,
                    "config_path": str(store.path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    return 1


def run_ask(args: argparse.Namespace) -> int:
    workspace = str(Path(args.workspace).resolve())
    settings = SettingsStore(workspace).load()
    api_key = args.api_key or settings.api_keys.get(args.provider)

    load_dotenv(workspace)
    profile = scan_project(workspace)
    save_project_profile(profile)

    client = ChatClient.from_options(
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        base_url=args.base_url,
        timeout_seconds=args.timeout,
    )
    tools = ToolRegistry(workspace=workspace)
    mcp_runtime = MCPRuntime(workspace=workspace, config_path=args.mcp_config)
    events: list[dict[str, Any]] = []
    prompt = " ".join(args.prompt).strip()
    snapshot_dir = None if args.no_snapshot else create_snapshot(workspace, prompt)
    augmented_prompt = (
        "You are working inside a local code repository.\n\n"
        "Repository profile:\n"
        f"{profile.to_prompt_context()}\n\n"
        "User task:\n"
        f"{prompt}\n\n"
        "Before answering, inspect files with tools when needed. "
        "In the final answer, include: plan, evidence, result, and suggested next command/test."
    )

    try:
        mcp_runtime.mount(tools)
        memory = None if args.no_memory else SessionMemory(workspace=workspace, session_id=args.session)
        runtime = AgentRuntime(agent=CODING_AGENT, client=client, tools=tools, memory=memory)
        reply = runtime.ask(
            augmented_prompt,
            event_callback=lambda evt: events.append(dict(evt)),
        )
        print(reply)
        undo_path = finalize_snapshot(workspace, snapshot_dir) if snapshot_dir is not None else None
        if undo_path is not None:
            undo = json.loads(undo_path.read_text(encoding="utf-8"))
            print(f"\n[undo] snapshot={snapshot_dir.name} changes={len(undo.get('changes', []))}")
            print("[undo] restore with: youagent-code undo last")
        if not args.no_trace:
            trace_path = write_trace(
                workspace=workspace,
                prompt=prompt,
                profile=profile,
                events=events,
                reply=reply,
                snapshot_path=snapshot_dir,
            )
            print(f"[trace] {trace_path}")
        return 0
    finally:
        mcp_runtime.close()


def main() -> int:
    # Convenience: allow `youagent-code "explain this repo"` as shorthand for `ask`.
    commands = {"init", "ask", "trace", "undo", "model", "-h", "--help"}
    argv = sys.argv[1:]
    if argv and argv[0] not in commands:
        argv = ["ask", *argv]

    defaults = SettingsStore(os.getcwd()).load()
    parser = build_parser(defaults)
    args = parser.parse_args(argv)

    if args.command == "init":
        return run_init(args)
    if args.command == "ask":
        return run_ask(args)
    if args.command == "trace":
        return run_trace(args)
    if args.command == "undo":
        return run_undo(args)
    if args.command == "model":
        return run_model(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
