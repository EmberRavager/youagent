import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ScheduledTask:
    id: str
    name: str
    prompt: str
    provider: str
    model: str
    agent: str
    session: str
    workspace: str
    base_url: str | None
    interval_seconds: int
    next_run_at: int
    enabled: bool = True
    no_memory: bool = False
    mcp_config: str | None = None
    status: str = "idle"
    step_index: int = 0
    step_total: int = 1
    last_run_at: int | None = None
    last_error: str | None = None
    last_reply: str | None = None
    runs: int = 0
    updated_at: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduledTask":
        now = int(time.time())
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            name=str(data.get("name") or "task"),
            prompt=str(data.get("prompt") or "").strip(),
            provider=str(data.get("provider") or "openai"),
            model=str(data.get("model") or "gpt-4.1-mini"),
            agent=str(data.get("agent") or "miniagent_like"),
            session=str(data.get("session") or "default"),
            workspace=str(data.get("workspace") or "."),
            base_url=None if data.get("base_url") in (None, "") else str(data.get("base_url")),
            interval_seconds=max(10, int(data.get("interval_seconds") or 300)),
            next_run_at=int(data.get("next_run_at") or now),
            enabled=bool(data.get("enabled", True)),
            no_memory=bool(data.get("no_memory", False)),
            mcp_config=None if data.get("mcp_config") in (None, "") else str(data.get("mcp_config")),
            status=str(data.get("status") or "idle"),
            step_index=max(0, int(data.get("step_index") or 0)),
            step_total=max(1, int(data.get("step_total") or 1)),
            last_run_at=(
                None if data.get("last_run_at") in (None, "") else int(data.get("last_run_at"))
            ),
            last_error=None if data.get("last_error") in (None, "") else str(data.get("last_error")),
            last_reply=None if data.get("last_reply") in (None, "") else str(data.get("last_reply")),
            runs=max(0, int(data.get("runs") or 0)),
            updated_at=int(data.get("updated_at") or now),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskStore:
    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()
        self.path = self.workspace / ".mini_worker" / "tasks.json"
        self._lock = threading.Lock()

    def list(self) -> list[ScheduledTask]:
        with self._lock:
            return self._load_unlocked()

    def add(
        self,
        *,
        name: str,
        prompt: str,
        provider: str,
        model: str,
        agent: str,
        session: str,
        workspace: str,
        base_url: str | None,
        interval_seconds: int,
        no_memory: bool,
        mcp_config: str | None,
    ) -> ScheduledTask:
        now = int(time.time())
        task = ScheduledTask(
            id=uuid.uuid4().hex[:12],
            name=name.strip() or "task",
            prompt=prompt.strip(),
            provider=provider,
            model=model,
            agent=agent,
            session=session,
            workspace=workspace,
            base_url=base_url,
            interval_seconds=max(10, interval_seconds),
            next_run_at=now,
            no_memory=no_memory,
            mcp_config=mcp_config,
            updated_at=now,
        )
        with self._lock:
            tasks = self._load_unlocked()
            tasks.append(task)
            self._save_unlocked(tasks)
        return task

    def delete(self, task_id: str) -> bool:
        with self._lock:
            tasks = self._load_unlocked()
            remain = [t for t in tasks if t.id != task_id]
            if len(remain) == len(tasks):
                return False
            self._save_unlocked(remain)
            return True

    def update(self, task_id: str, **fields: Any) -> ScheduledTask | None:
        with self._lock:
            tasks = self._load_unlocked()
            found: ScheduledTask | None = None
            for task in tasks:
                if task.id != task_id:
                    continue
                found = task
                for key, value in fields.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                task.updated_at = int(time.time())
                break
            if found is None:
                return None
            self._save_unlocked(tasks)
            return found

    def due(self, now_ts: int | None = None) -> list[ScheduledTask]:
        now = now_ts or int(time.time())
        tasks = self.list()
        return [
            task
            for task in tasks
            if task.enabled and task.status != "running" and task.next_run_at <= now
        ]

    def _load_unlocked(self) -> list[ScheduledTask]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        out: list[ScheduledTask] = []
        for item in payload:
            if isinstance(item, dict):
                out.append(ScheduledTask.from_dict(item))
        return out

    def _save_unlocked(self, tasks: list[ScheduledTask]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([t.to_dict() for t in tasks], ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def run_due_tasks(
    store: TaskStore,
    runner: Callable[[ScheduledTask, Callable[[dict[str, Any]], None]], tuple[bool, str]],
    *,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> int:
    due_tasks = store.due()
    executed = 0
    for task in due_tasks:
        executed += 1
        store.update(
            task.id,
            status="running",
            step_index=0,
            step_total=1,
            last_error=None,
            last_reply=None,
            last_run_at=int(time.time()),
        )
        if on_event:
            on_event("task_started", {"task_id": task.id, "name": task.name})

        def progress(evt: dict[str, Any]) -> None:
            phase = str(evt.get("phase", ""))
            if phase == "tool_start":
                current = int(evt.get("tool_index", 0))
                total = max(1, int(evt.get("tool_total", 1)))
                store.update(task.id, step_index=current, step_total=total, status="running")
            if on_event:
                on_event("task_progress", {"task_id": task.id, **evt})

        ok = False
        detail = ""
        try:
            ok, detail = runner(task, progress)
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail = f"{type(exc).__name__}: {exc}"

        now = int(time.time())
        if ok:
            store.update(
                task.id,
                status="idle",
                step_index=1,
                step_total=1,
                last_reply=detail,
                last_error=None,
                runs=task.runs + 1,
                next_run_at=now + max(10, task.interval_seconds),
                last_run_at=now,
            )
            if on_event:
                on_event("task_succeeded", {"task_id": task.id, "name": task.name})
        else:
            store.update(
                task.id,
                status="error",
                step_index=0,
                step_total=1,
                last_error=detail,
                runs=task.runs + 1,
                next_run_at=now + max(10, task.interval_seconds),
                last_run_at=now,
            )
            if on_event:
                on_event("task_failed", {"task_id": task.id, "name": task.name, "error": detail})
    return executed
