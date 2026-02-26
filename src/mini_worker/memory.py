import json
from pathlib import Path
from typing import Any


class SessionMemory:
    def __init__(self, workspace: str, session_id: str):
        safe_session = "".join(
            ch for ch in session_id if ch.isalnum() or ch in {"-", "_"}
        )
        if not safe_session:
            safe_session = "default"
        self.path = (
            Path(workspace).resolve()
            / ".mini_worker"
            / "sessions"
            / f"{safe_session}.json"
        )

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        messages: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("role"), str):
                messages.append(item)
        return messages

    def save(self, messages: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(messages, ensure_ascii=True, indent=2), encoding="utf-8"
        )
