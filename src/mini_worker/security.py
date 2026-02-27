import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class SecurityPolicy:
    allow_shell: bool = True
    blocked_shell_tokens: list[str] = field(
        default_factory=lambda: [
            "rm -rf /",
            "mkfs",
            "shutdown",
            "reboot",
            "poweroff",
            "dd if=",
            "curl | sh",
            "wget | sh",
            ":(){:|:&};:",
            "chmod -R 777 /",
        ]
    )
    blocked_hosts: list[str] = field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.169.254",
            "::1",
        ]
    )
    allowed_hosts: list[str] = field(default_factory=list)
    max_shell_timeout: int = 60
    max_fetch_chars: int = 200000
    max_playwright_chars: int = 120000

    @classmethod
    def load(cls, workspace: str) -> "SecurityPolicy":
        path = Path(workspace).resolve() / ".mini_worker" / "security.json"
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        if not isinstance(payload, dict):
            return cls()
        policy = cls()
        policy.allow_shell = bool(payload.get("allow_shell", policy.allow_shell))
        policy.blocked_shell_tokens = [
            str(x).lower() for x in payload.get("blocked_shell_tokens", policy.blocked_shell_tokens)
        ]
        policy.blocked_hosts = [str(x).lower() for x in payload.get("blocked_hosts", policy.blocked_hosts)]
        policy.allowed_hosts = [str(x).lower() for x in payload.get("allowed_hosts", policy.allowed_hosts)]
        policy.max_shell_timeout = int(payload.get("max_shell_timeout", policy.max_shell_timeout))
        policy.max_fetch_chars = int(payload.get("max_fetch_chars", policy.max_fetch_chars))
        policy.max_playwright_chars = int(
            payload.get("max_playwright_chars", policy.max_playwright_chars)
        )
        return policy

    def check_shell(self, command: str, timeout: int) -> tuple[bool, str | None]:
        if not self.allow_shell:
            return False, "Shell execution is disabled by security policy"
        lowered = command.lower()
        if any(token in lowered for token in self.blocked_shell_tokens):
            return False, "Command blocked by security policy"
        if timeout > self.max_shell_timeout:
            return False, f"Timeout exceeds policy limit ({self.max_shell_timeout}s)"
        return True, None

    def check_url(self, url: str) -> tuple[bool, str | None]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False, "Only http/https URLs are allowed"
        host = (parsed.hostname or "").lower()
        if host in self.blocked_hosts:
            return False, "Host is blocked by security policy"
        if self.allowed_hosts:
            matched = any(
                host == allowed or host.endswith(f".{allowed}")
                for allowed in self.allowed_hosts
            )
            if not matched:
                return False, "Host is not in allowlist"
        return True, None


def default_security_template() -> dict[str, Any]:
    return {
        "allow_shell": True,
        "blocked_shell_tokens": SecurityPolicy().blocked_shell_tokens,
        "blocked_hosts": SecurityPolicy().blocked_hosts,
        "allowed_hosts": [],
        "max_shell_timeout": 60,
        "max_fetch_chars": 200000,
        "max_playwright_chars": 120000,
    }
