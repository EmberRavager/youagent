from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    title: str
    reason: str


RULES: tuple[tuple[str, str, str, str], ...] = (
    ("destructive_delete", "critical", "Recursive deletion", r"(?i)(?:^|[;&|]\s*)(?:sudo\s+)?rm\s+(?:-[^\s]*r[^\s]*f|-[^\s]*f[^\s]*r)\b"),
    ("find_delete", "critical", "Bulk deletion", r"(?i)\bfind\b[^\n]*(?:-delete|-exec\s+rm)"),
    ("git_clean", "high", "Destructive Git clean", r"(?i)\bgit\s+clean\s+[^\n]*(?:-[^\s]*f)"),
    ("git_reset", "high", "Hard Git reset", r"(?i)\bgit\s+reset\s+--hard\b"),
    ("git_force_push", "high", "Forced Git push", r"(?i)\bgit\s+push\b[^\n]*(?:--force(?:-with-lease)?|-f\b)"),
    ("privilege_escalation", "high", "Privilege escalation", r"(?i)(?:^|[;&|]\s*)sudo\s+"),
    ("permission_recursive", "high", "Recursive permission change", r"(?i)\b(?:chmod|chown)\s+[^\n]*-[^\s]*R"),
    ("pipe_remote_shell", "critical", "Remote script piped to shell", r"(?i)\b(?:curl|wget)\b[^\n]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)\b"),
    ("docker_prune", "high", "Docker destructive cleanup", r"(?i)\bdocker\s+(?:system|volume)\s+(?:prune|rm)\b"),
    ("kubernetes_delete", "high", "Kubernetes resource deletion", r"(?i)\bkubectl\s+delete\s+(?:namespace|ns|pvc|secret|all)\b"),
    ("database_destroy", "critical", "Database destructive statement", r"(?i)\b(?:DROP\s+(?:DATABASE|SCHEMA|TABLE)|TRUNCATE\s+TABLE)\b"),
    ("secret_dump", "critical", "Potential secret disclosure", r"(?i)\b(?:cat|head|tail|less|more|sed|awk|grep)\b[^\n]*(?:\.env(?:\.|\b)|id_(?:rsa|ed25519)|credentials|\.npmrc|\.pypirc|\.netrc|\.git-credentials)"),
)

SENSITIVE_PARTS = (
    "/.ssh/",
    "/.aws/",
    "/.azure/",
    "/.kube/",
    "/.config/gcloud/",
    "/.docker/config.json",
    "/.git-credentials",
    "/.npmrc",
    "/.pypirc",
    "/.netrc",
)

SECRET_ENV_RE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?key|secret|token|password|passwd|private[_-]?key|database_url|dsn)"
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def _normalise_command(argv: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in argv)


def sensitive_path_in_command(command: str, home: Path | None = None) -> str | None:
    expanded = command.replace("~", str(home or Path.home()))
    lowered = expanded.lower()
    for marker in SENSITIVE_PARTS:
        if marker.lower() in lowered:
            return marker
    if re.search(r"(?i)(?:^|[/\s])\.env(?:\.[\w.-]+)?(?:$|[\s;&|])", expanded):
        return ".env"
    if re.search(r"(?i)(?:id_rsa|id_ed25519|service[-_]?account.*\.json|credentials\.json)", expanded):
        return "credential file"
    return None


def inspect_command(argv: Iterable[str] | str) -> list[Finding]:
    command = argv if isinstance(argv, str) else _normalise_command(argv)
    findings: list[Finding] = []
    for rule_id, severity, title, pattern in RULES:
        if re.search(pattern, command):
            findings.append(Finding(rule_id, severity, title, f"Matched dangerous command pattern: {title}"))

    marker = sensitive_path_in_command(command)
    if marker and not any(item.rule_id == "secret_dump" for item in findings):
        findings.append(Finding("sensitive_path", "critical", "Sensitive credential path", f"Command references protected path: {marker}"))

    if any(pattern.search(command) for pattern in SECRET_VALUE_PATTERNS):
        findings.append(Finding("secret_in_command", "critical", "Secret exposed in command line", "A credential-like value appears in process arguments"))
    return findings


def redact(text: str) -> str:
    result = text
    for pattern in SECRET_VALUE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    result = re.sub(
        r"(?i)((?:api[_-]?key|access[_-]?key|secret|token|password|passwd)\s*[=:]\s*)[^\s;&]+",
        r"\1[REDACTED]",
        result,
    )
    return result


def sanitized_environment(environment: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    clean: dict[str, str] = {}
    removed: list[str] = []
    for key, value in environment.items():
        if SECRET_ENV_RE.search(key):
            removed.append(key)
        else:
            clean[key] = value
    return clean, sorted(removed)
