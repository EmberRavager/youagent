import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class Observability:
    workspace: str
    _lock: Lock = field(default_factory=Lock, init=False)
    _recent: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=300), init=False)
    _counters: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        root = Path(self.workspace).resolve() / ".mini_worker" / "observability"
        root.mkdir(parents=True, exist_ok=True)
        self.events_path = root / "events.jsonl"
        self.metrics_path = root / "metrics.json"
        if self.metrics_path.exists():
            try:
                payload = json.loads(self.metrics_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self._counters = {
                        str(k): int(v) for k, v in payload.items() if isinstance(v, int)
                    }
            except Exception:
                self._counters = {}

    def record(self, event_type: str, **fields: Any) -> None:
        event = {
            "ts": int(time.time()),
            "event": event_type,
            **fields,
        }
        raw = json.dumps(event, ensure_ascii=True)
        with self._lock:
            self._recent.append(event)
            self._counters[event_type] = self._counters.get(event_type, 0) + 1
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(raw + "\n")
            self.metrics_path.write_text(
                json.dumps(self._counters, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "events_path": str(self.events_path),
                "metrics_path": str(self.metrics_path),
            }

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        max_items = max(1, min(limit, 300))
        with self._lock:
            data = list(self._recent)
        return data[-max_items:]
