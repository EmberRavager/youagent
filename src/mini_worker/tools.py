import json
import os
import re
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable
from urllib import request

from .security import SecurityPolicy


def _safe_join(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise ValueError("Path escapes workspace")
    return candidate


@dataclass
class ToolCallResult:
    ok: bool
    content: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], ToolCallResult]


class ToolRegistry:
    def __init__(self, workspace: str | None = None):
        self.workspace = Path(workspace or os.getcwd()).resolve()
        self.security = SecurityPolicy.load(str(self.workspace))
        self._tools: dict[str, ToolSpec] = {}
        self._register_builtin_tools()

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def register_tool(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[[dict[str, Any]], ToolCallResult],
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already exists: {name}")
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def add_mcp_tool(
        self,
        *,
        mcp_server: str,
        mcp_tool_name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[[dict[str, Any]], ToolCallResult],
    ) -> str:
        safe_server = re.sub(r"[^a-zA-Z0-9_]", "_", mcp_server).strip("_").lower()
        safe_tool = re.sub(r"[^a-zA-Z0-9_]", "_", mcp_tool_name).strip("_").lower()
        tool_name = f"mcp_{safe_server}_{safe_tool}"
        self.register_tool(
            name=tool_name,
            description=f"[mcp:{mcp_server}] {description}".strip(),
            parameters=parameters,
            handler=handler,
        )
        return tool_name

    def call(self, name: str, args: dict[str, Any]) -> ToolCallResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolCallResult(False, f"Unknown tool: {name}")
        try:
            return spec.handler(args)
        except Exception as exc:  # noqa: BLE001
            return ToolCallResult(False, f"{type(exc).__name__}: {exc}")

    def _register_builtin_tools(self) -> None:
        self.register_tool(
            name="list_files",
            description="List files under a workspace-relative path",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative path",
                    },
                },
                "required": ["path"],
            },
            handler=self._list_files,
        )
        self.register_tool(
            name="read_file",
            description="Read text file content",
            parameters={
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
            handler=self._read_file,
        )
        self.register_tool(
            name="write_file",
            description="Write text to a workspace file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean"},
                },
                "required": ["path", "content"],
            },
            handler=self._write_file,
        )
        self.register_tool(
            name="run_shell",
            description="Run a shell command in workspace",
            parameters={
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
            handler=self._run_shell,
        )
        self.register_tool(
            name="find_files",
            description="Find files by glob-like pattern under workspace",
            parameters={
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
            handler=self._find_files,
        )
        self.register_tool(
            name="grep_text",
            description="Search text content with regex in workspace files",
            parameters={
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
            handler=self._grep_text,
        )
        self.register_tool(
            name="fetch_url",
            description="Fetch web content over HTTP/HTTPS",
            parameters={
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
            handler=self._fetch_url,
        )
        self.register_tool(
            name="read_json",
            description="Read a JSON file from workspace",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=self._read_json,
        )
        self.register_tool(
            name="write_json",
            description="Write JSON data to a workspace file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "data": {"description": "Any JSON value"},
                    "indent": {"type": "integer", "minimum": 0, "maximum": 8},
                },
                "required": ["path", "data"],
            },
            handler=self._write_json,
        )
        self.register_tool(
            name="playwright_browse",
            description=(
                "Use Playwright browser automation. action=content returns visible text, "
                "action=screenshot saves image file in workspace."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["content", "screenshot"],
                    },
                    "selector": {"type": "string"},
                    "path": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
                    "max_chars": {"type": "integer", "minimum": 100, "maximum": 200000},
                },
                "required": ["url"],
            },
            handler=self._playwright_browse,
        )

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
        timeout = int(args.get("timeout", 20))
        allowed, reason = self.security.check_shell(command=command, timeout=timeout)
        if not allowed:
            return ToolCallResult(False, reason or "Command blocked by policy")
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
        allowed, reason = self.security.check_url(url)
        if not allowed:
            return ToolCallResult(False, reason or "URL blocked by policy")

        timeout = int(args.get("timeout", 20))
        max_chars = min(
            int(args.get("max_chars", 30000)),
            int(self.security.max_fetch_chars),
        )
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

    def _playwright_browse(self, args: dict[str, Any]) -> ToolCallResult:
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolCallResult(False, "url is required")
        allowed, reason = self.security.check_url(url)
        if not allowed:
            return ToolCallResult(False, reason or "URL blocked by policy")

        action = str(args.get("action", "content")).strip().lower()
        if action not in {"content", "screenshot"}:
            return ToolCallResult(False, "action must be 'content' or 'screenshot'")

        timeout = int(args.get("timeout", 30))
        timeout = min(max(1, timeout), 120)
        selector = str(args.get("selector", "")).strip() or None
        max_chars = min(
            int(args.get("max_chars", 20000)),
            int(self.security.max_playwright_chars),
        )
        out_path = str(args.get("path", "playwright_screenshot.png")).strip()
        screenshot_path = _safe_join(self.workspace, out_path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "url": url,
            "action": action,
            "selector": selector,
            "maxChars": max_chars,
            "screenshotPath": str(screenshot_path),
            "timeoutMs": timeout * 1000,
        }
        js = r"""
const payload = JSON.parse(process.env.MW_PLAYWRIGHT_PAYLOAD || "{}");
async function main() {
  const { chromium } = require("playwright");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(payload.url, { waitUntil: "domcontentloaded", timeout: payload.timeoutMs });
  if (payload.selector) {
    await page.waitForSelector(payload.selector, { timeout: payload.timeoutMs });
  }
  if (payload.action === "screenshot") {
    await page.screenshot({ path: payload.screenshotPath, fullPage: true });
    console.log(JSON.stringify({ ok: true, mode: "screenshot", path: payload.screenshotPath }));
  } else {
    const text = await page.evaluate((selector) => {
      const node = selector ? document.querySelector(selector) : document.body;
      if (!node) return "";
      return (node.innerText || "").trim();
    }, payload.selector || null);
    console.log(JSON.stringify({ ok: true, mode: "content", text: String(text || "").slice(0, payload.maxChars) }));
  }
  await browser.close();
}
main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
""".strip()
        env = dict(os.environ)
        env["MW_PLAYWRIGHT_PAYLOAD"] = json.dumps(payload, ensure_ascii=True)
        proc = subprocess.run(
            ["node", "-e", js],
            cwd=str(self.workspace),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            if "Cannot find module 'playwright'" in stderr:
                return ToolCallResult(
                    False,
                    "Playwright not installed. Install Node.js Playwright first.",
                )
            return ToolCallResult(False, f"Playwright failed: {stderr[-1200:]}")
        stdout = (proc.stdout or "").strip()
        if not stdout:
            return ToolCallResult(False, "Playwright returned empty output")
        try:
            data = json.loads(stdout.splitlines()[-1])
        except Exception:
            return ToolCallResult(True, stdout[-12000:])
        if data.get("mode") == "screenshot":
            rel = screenshot_path.relative_to(self.workspace)
            return ToolCallResult(True, f"Saved screenshot: {rel}")
        return ToolCallResult(True, str(data.get("text", "")))
