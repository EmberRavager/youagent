from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .monitor import DEFAULT_AGENT_NAMES, GuardMonitor
from .rules import sanitized_environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="youagent-guard", description="Monitor local AI-agent processes for high-risk behavior")
    sub = parser.add_subparsers(dest="command", required=True)

    watch = sub.add_parser("watch", help="Watch known or user-specified AI agent processes")
    watch.add_argument("--agent", action="append", default=[], help="Executable/process name; may be repeated")
    watch.add_argument("--pid", type=int, action="append", default=[], help="Treat this PID and descendants as an agent")
    watch.add_argument("--action", choices=["alert", "terminate"], default="alert")
    watch.add_argument("--poll", type=float, default=0.25)
    watch.add_argument("--audit", type=Path, default=None)

    run = sub.add_parser("run", help="Launch an agent with secret-like environment variables removed")
    run.add_argument("--action", choices=["alert", "terminate"], default="terminate")
    run.add_argument("--poll", type=float, default=0.1)
    run.add_argument("--audit", type=Path, default=None)
    run.add_argument("program", nargs=argparse.REMAINDER)
    return parser


def _monitor(*, agents: list[str], pids: list[int], action: str, poll: float, audit: Path | None) -> int:
    names = set(DEFAULT_AGENT_NAMES)
    names.update(item.lower() for item in agents)
    GuardMonitor(agent_names=names, root_pids=pids, action=action, poll_interval=poll, audit_path=audit).run()
    return 0


def _run_agent(program: list[str], action: str, poll: float, audit: Path | None) -> int:
    if program and program[0] == "--":
        program = program[1:]
    if not program:
        raise SystemExit("program required, for example: youagent-guard run -- codex")
    environment, removed = sanitized_environment(dict(os.environ))
    child = subprocess.Popen(program, env=environment)
    if removed:
        print("[guard] stripped secret-like environment variables: " + ", ".join(removed))
    monitor = GuardMonitor(root_pids=[child.pid], action=action, poll_interval=poll, audit_path=audit)
    try:
        while child.poll() is None:
            monitor.scan_once()
            child.wait(timeout=poll)
    except subprocess.TimeoutExpired:
        return _run_until_exit(child, monitor, poll)
    except KeyboardInterrupt:
        child.terminate()
        return 130
    return int(child.returncode or 0)


def _run_until_exit(child: subprocess.Popen[bytes], monitor: GuardMonitor, poll: float) -> int:
    try:
        while child.poll() is None:
            monitor.scan_once()
            try:
                child.wait(timeout=poll)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        child.terminate()
        return 130
    return int(child.returncode or 0)


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "watch":
        return _monitor(agents=args.agent, pids=args.pid, action=args.action, poll=args.poll, audit=args.audit)
    if args.command == "run":
        return _run_agent(args.program, args.action, args.poll, args.audit)
    return 2


if __name__ == "__main__":
    sys.exit(main())
