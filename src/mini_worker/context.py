from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


IGNORED_CONTEXT_DIRS = {
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

FILE_REF_PATTERN = re.compile(r"(?<![\w.])@([^\s`'\"<>]+)")


@dataclass(frozen=True)
class ContextBudget:
    max_files: int = 5
    max_file_chars: int = 20_000
    max_total_chars: int = 80_000


@dataclass(frozen=True)
class ContextBlock:
    prompt: str
    referenced_files: list[str]
    skipped: list[str]


def extract_file_refs(text: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for match in FILE_REF_PATTERN.finditer(text):
        raw = match.group(1).strip().rstrip(".,;:)"])
        if not raw or raw.startswith(("http://", "https://")):
            continue
        normalized = raw.replace("\\", "/")
        if normalized not in seen:
            refs.append(normalized)
            seen.add(normalized)
    return refs


def _safe_workspace_path(workspace: str, value: str) -> Path:
    root = Path(workspace).resolve()
    candidate = (root / value).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Path escapes workspace")
    return candidate


def _is_ignored(path: Path, workspace: str) -> bool:
    root = Path(workspace).resolve()
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in IGNORED_CONTEXT_DIRS for part in parts)


def build_file_context(workspace: str, user_text: str, budget: ContextBudget | None = None) -> ContextBlock:
    budget = budget or ContextBudget()
    refs = extract_file_refs(user_text)
    if not refs:
        return ContextBlock(prompt=user_text, referenced_files=[], skipped=[])

    included: list[str] = []
    skipped: list[str] = []
    blocks: list[str] = []
    total_chars = 0

    for ref in refs:
        if len(included) >= budget.max_files:
            skipped.append(f"{ref}: context file limit reached")
            continue
        try:
            path = _safe_workspace_path(workspace, ref)
        except ValueError as exc:
            skipped.append(f"{ref}: {exc}")
            continue
        if _is_ignored(path, workspace):
            skipped.append(f"{ref}: ignored directory")
            continue
        if not path.exists():
            skipped.append(f"{ref}: not found")
            continue
        if not path.is_file():
            skipped.append(f"{ref}: not a file")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{ref}: {type(exc).__name__}: {exc}")
            continue

        truncated = False
        if len(text) > budget.max_file_chars:
            text = text[: budget.max_file_chars]
            truncated = True
        if total_chars + len(text) > budget.max_total_chars:
            remaining = max(0, budget.max_total_chars - total_chars)
            if remaining <= 0:
                skipped.append(f"{ref}: context total limit reached")
                continue
            text = text[:remaining]
            truncated = True
        rel = str(path.relative_to(Path(workspace).resolve()))
        total_chars += len(text)
        included.append(rel)
        suffix = "\n...[truncated]" if truncated else ""
        blocks.append(f"### {rel}\n```\n{text}{suffix}\n```")

    if not blocks and skipped:
        skipped_block = "\n".join(f"- {item}" for item in skipped)
        return ContextBlock(
            prompt=f"{user_text}\n\n[File reference notes]\n{skipped_block}",
            referenced_files=included,
            skipped=skipped,
        )

    context = "\n\n".join(blocks)
    skipped_block = ""
    if skipped:
        skipped_block = "\n\nSkipped file references:\n" + "\n".join(f"- {item}" for item in skipped)
    prompt = (
        f"{user_text}\n\n"
        "The user explicitly referenced these workspace files. Use them as focused context; "
        "do not read the whole repository unless necessary.\n\n"
        f"--- BEGIN EXPLICIT FILE CONTEXT ---\n{context}\n--- END EXPLICIT FILE CONTEXT ---"
        f"{skipped_block}"
    )
    return ContextBlock(prompt=prompt, referenced_files=included, skipped=skipped)


def is_plan_request(text: str) -> bool:
    stripped = text.strip().lower()
    return stripped.startswith("/plan") or stripped.startswith("plan:")


def to_plan_prompt(text: str) -> str:
    stripped = text.strip()
    if stripped.lower().startswith("/plan"):
        stripped = stripped[5:].strip()
    elif stripped.lower().startswith("plan:"):
        stripped = stripped[5:].strip()
    return (
        "PLAN MODE. Do not write files, run risky shell commands, install packages, delete/move files, "
        "or make external side-effect changes. Inspect only as needed, then produce a concrete plan. "
        "Include files likely to change, commands to run, risks, validation steps, and what approval is needed.\n\n"
        f"User task:\n{stripped or '(no task provided)'}"
    )


def should_create_snapshot(original_text: str, prepared_text: str) -> bool:
    lower = original_text.lower()
    if is_plan_request(original_text):
        return False
    read_only_signals = [
        "解释",
        "说明",
        "分析",
        "看看",
        "为什么",
        "怎么",
        "what",
        "why",
        "explain",
        "analyze",
        "review",
        "inspect",
        "read",
    ]
    write_signals = [
        "修改",
        "改一下",
        "修复",
        "新增",
        "删除",
        "移动",
        "写入",
        "update",
        "change",
        "modify",
        "fix",
        "add",
        "delete",
        "move",
        "write",
        "create",
    ]
    if any(signal in lower for signal in write_signals):
        return True
    if any(signal in lower for signal in read_only_signals):
        return False
    return prepared_text != original_text and "/skill" in original_text
