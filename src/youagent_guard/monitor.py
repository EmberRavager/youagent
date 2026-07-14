from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import psutil

from .notifier import notify
from .rules import Finding, inspect_command, redact


DEFAULT_AGENT_NAMES = {
    "codex", "claude", "cursor", "windsurf", "aider", "opencode",
    "gemini", "openclaw", "continue", "copilot",
}


class GuardMonitor:
    def __init__(
        self,
        *,
        agent_names: Iterable[str] = DEFAULT_AGENT_NAMES,
        root_pids: Iterable[int] = (),
        action: str = "alert",
        poll_interval: float = 0.25,
        audit_path: Path | None = None,
    ) -> None:
        self.agent_names = {name.lower() for name in agent_names}
        self.root_pids = {int(pid) for pid in root_pids}
        self.action = action
        self.poll_interval = poll_interval
        self.audit_path = audit_path or Path.home() / ".youagent-guard" / "audit.jsonl"
        self._seen: set[tuple[int, float]] = set()

    def _is_agent_process(self, proc: psutil.Process) -> tuple[bool, str | None]:
        current = proc
        visited: set[int] = set()
        while current.pid not in visited:
            visited.add(current.pid)
            if current.pid in self.root_pids:
                return True, f"pid:{current.pid}"
            try:
                name = current.name().lower()
                exe_name = Path(current.exe()).name.lower() if current.exe() else ""
                cmd = " ".join(current.cmdline()).lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return False, None
            for candidate in self.agent_names:
                if name == candidate or exe_name == candidate or name.startswith(candidate) or f"/{candidate}" in cmd:
                    return True, candidate
            try:
                parent = current.parent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False, None
            if parent is None:
                return False, None
            current = parent
        return False, None

    def _audit(self, proc: psutil.Process, source: str, findings: list[Finding], command: str, outcome: str) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pid": proc.pid,
            "source": source,
            "command": redact(command),
            "findings": [asdict(item) for item in findings],
            "outcome": outcome,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _terminate(self, proc: psutil.Process) -> str:
        try:
            os.kill(proc.pid, signal.SIGSTOP)
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except psutil.TimeoutExpired:
                proc.kill()
            return "terminated"
        except (ProcessLookupError, psutil.NoSuchProcess):
            return "already_exited"
        except (PermissionError, psutil.AccessDenied):
            return "termination_denied"

    def scan_once(self) -> int:
        alerts = 0
        for proc in psutil.process_iter(["pid", "create_time", "cmdline"]):
            try:
                key = (proc.pid, float(proc.info["create_time"]))
                if key in self._seen:
                    continue
                self._seen.add(key)
                argv = proc.info.get("cmdline") or []
                if not argv:
                    continue
                protected, source = self._is_agent_process(proc)
                if not protected:
                    continue
                findings = inspect_command(argv)
                if not findings:
                    continue
                alerts += 1
                command = " ".join(argv)
                highest = "critical" if any(item.severity == "critical" for item in findings) else "high"
                outcome = "alerted"
                if self.action == "terminate":
                    outcome = self._terminate(proc)
                summary = "; ".join(item.title for item in findings[:3])
                notify(
                    f"YouAgent Guard: {highest.upper()}",
                    f"{source or 'AI agent'}: {summary}. Action: {outcome}",
                )
                self._audit(proc, source or "unknown-agent", findings, command, outcome)
                print(f"[guard] {highest} source={source} pid={proc.pid} action={outcome} {redact(command)}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return alerts

    def run(self) -> None:
        print(f"[guard] monitoring agents={sorted(self.agent_names)} action={self.action}")
        print(f"[guard] audit={self.audit_path}")
        while True:
            self.scan_once()
            time.sleep(self.poll_interval)
