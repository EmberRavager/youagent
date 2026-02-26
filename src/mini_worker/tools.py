import json
import os
import re
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import urlparse


def _safe_join(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise ValueError("Path escapes workspace")
    return candidate


def _blocked_shell(command: str) -> bool:
    blocked_tokens = [
        "rm -rf /",
        "mkfs",
        "shutdown",
        "reboot",
        "poweroff",
        "dd if=",
        "curl | sh",
        "wget | sh",
    ]
    lowered = command.lower()
    return any(token in lowered for token in blocked_tokens)


@dataclass
class ToolCallResult:
    ok: bool
    content: str


class ToolRegistry:
    def __init__(self, workspace: str | None = None):
        self.workspace = Path(workspace or os.getcwd()).resolve()

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files under a workspace-relative path",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative path",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read text file content",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "max_chars": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 200000,
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write text to a workspace file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "append": {"type": "boolean"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_shell",
                    "description": "Run a shell command in workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 120,
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_files",
                    "description": "Find files by glob-like pattern under workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative root path",
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Pattern like *.py or src/*.md",
                            },
                            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "grep_text",
                    "description": "Search text content with regex in workspace files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative root path",
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Regex pattern",
                            },
                            "include": {
                                "type": "string",
                                "description": "File include glob, default *",
                            },
                            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "description": "Fetch web content over HTTP/HTTPS",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "timeout": {"type": "integer", "minimum": 1, "maximum": 60},
                            "max_chars": {
                                "type": "integer",
                                "minimum": 100,
                                "maximum": 200000,
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_json",
                    "description": "Read a JSON file from workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_json",
                    "description": "Write JSON data to a workspace file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "data": {"description": "Any JSON value"},
                            "indent": {"type": "integer", "minimum": 0, "maximum": 8},
                        },
                        "required": ["path", "data"],
                    },
                },
            },
        ]

    def call(self, name: str, args: dict[str, Any]) -> ToolCallResult:
        try:
            if name == "list_files":
                return self._list_files(args)
            if name == "read_file":
                return self._read_file(args)
            if name == "write_file":
                return self._write_file(args)
            if name == "run_shell":
                return self._run_shell(args)
            if name == "find_files":
                return self._find_files(args)
            if name == "grep_text":
                return self._grep_text(args)
            if name == "fetch_url":
                return self._fetch_url(args)
            if name == "read_json":
                return self._read_json(args)
            if name == "write_json":
                return self._write_json(args)
            return ToolCallResult(False, f"Unknown tool: {name}")
        except Exception as exc:  # noqa: BLE001
            return ToolCallResult(False, f"{type(exc).__name__}: {exc}")

    def _list_files(self, args: dict[str, Any]) -> ToolCallResult:
        target = _safe_join(self.workspace, str(args.get("path", ".")))
        if not target.exists():
            return ToolCallResult(False, f"Path not found: {target}")
        if target.is_file():
            return ToolCallResult(True, str(target.relative_to(self.workspace)))

        entries = []
        for child in sorted(target.iterdir()):
            mark = "/" if child.is_dir() else ""
            entries.append(f"{child.relative_to(self.workspace)}{mark}")
        return ToolCallResult(True, "\n".join(entries) if entries else "(empty)")

    def _read_file(self, args: dict[str, Any]) -> ToolCallResult:
        target = _safe_join(self.workspace, args["path"])
        max_chars = int(args.get("max_chars", 20000))
        content = target.read_text(encoding="utf-8")
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated]"
        return ToolCallResult(True, content)

    def _write_file(self, args: dict[str, Any]) -> ToolCallResult:
        target = _safe_join(self.workspace, str(args["path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if bool(args.get("append", False)) else "w"
        content = args.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=True)
        with target.open(mode, encoding="utf-8") as fh:
            written = fh.write(content)
        return ToolCallResult(
            True,
            f"Wrote file: {target.relative_to(self.workspace)} ({written} chars)",
        )

    def _run_shell(self, args: dict[str, Any]) -> ToolCallResult:
        command = args["command"]
        if _blocked_shell(command):
            return ToolCallResult(False, "Command blocked by safety policy")

        timeout = int(args.get("timeout", 20))
        proc = subprocess.run(
            command,
            cwd=str(self.workspace),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        payload = {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
        }
        return ToolCallResult(True, json.dumps(payload, ensure_ascii=True))

    def _find_files(self, args: dict[str, Any]) -> ToolCallResult:
        root = _safe_join(self.workspace, args.get("path", "."))
        pattern = str(args["pattern"]).strip()
        limit = int(args.get("limit", 200))
        if not root.exists() or not root.is_dir():
            return ToolCallResult(False, f"Path not found or not directory: {root}")

        matches: list[str] = []
        for candidate in root.rglob("*"):
            if not candidate.is_file():
                continue
            rel = str(candidate.relative_to(self.workspace))
            if fnmatch(rel, pattern) or fnmatch(candidate.name, pattern):
                matches.append(rel)
            if len(matches) >= limit:
                break
        return ToolCallResult(True, "\n".join(matches) if matches else "(no matches)")

    def _grep_text(self, args: dict[str, Any]) -> ToolCallResult:
        root = _safe_join(self.workspace, args.get("path", "."))
        regex = re.compile(str(args["pattern"]))
        include = str(args.get("include", "*"))
        limit = int(args.get("limit", 200))
        if not root.exists() or not root.is_dir():
            return ToolCallResult(False, f"Path not found or not directory: {root}")

        hits: list[str] = []
        for candidate in root.rglob("*"):
            if not candidate.is_file() or not fnmatch(candidate.name, include):
                continue
            try:
                text = candidate.read_text(encoding="utf-8")
            except Exception:
                continue

            for idx, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    rel = str(candidate.relative_to(self.workspace))
                    hits.append(f"{rel}:{idx}: {line[:300]}")
                    if len(hits) >= limit:
                        return ToolCallResult(True, "\n".join(hits))
        return ToolCallResult(True, "\n".join(hits) if hits else "(no matches)")

    def _fetch_url(self, args: dict[str, Any]) -> ToolCallResult:
        url = str(args["url"]).strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return ToolCallResult(False, "Only http/https URLs are allowed")

        host = (parsed.hostname or "").lower()
        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"}
        if host in blocked_hosts:
            return ToolCallResult(False, "Host is blocked by safety policy")

        timeout = int(args.get("timeout", 20))
        max_chars = int(args.get("max_chars", 30000))
        req = request.Request(
            url=url,
            method="GET",
            headers={"User-Agent": "mini-worker/0.1"},
        )
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if len(body) > max_chars:
                body = body[:max_chars] + "\n...[truncated]"
            return ToolCallResult(True, body)

    def _read_json(self, args: dict[str, Any]) -> ToolCallResult:
        target = _safe_join(self.workspace, args["path"])
        data = json.loads(target.read_text(encoding="utf-8"))
        return ToolCallResult(True, json.dumps(data, ensure_ascii=True, indent=2))

    def _write_json(self, args: dict[str, Any]) -> ToolCallResult:
        target = _safe_join(self.workspace, args["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        indent = int(args.get("indent", 2))
        target.write_text(
            json.dumps(args["data"], ensure_ascii=True, indent=indent),
            encoding="utf-8",
        )
        return ToolCallResult(
            True, f"Wrote JSON file: {target.relative_to(self.workspace)}"
        )
