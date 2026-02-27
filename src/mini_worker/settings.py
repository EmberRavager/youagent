import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    base_url: str | None = None
    agent: str = "manus_like"
    timeout: int = 60
    workspace: str = "."
    session: str = "default"
    no_memory: bool = False
    mcp_config: str | None = None
    api_keys: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        settings = cls()
        settings.provider = str(data.get("provider", settings.provider))
        settings.model = str(data.get("model", settings.model))
        base_url = data.get("base_url", settings.base_url)
        settings.base_url = None if base_url in (None, "") else str(base_url)
        settings.agent = str(data.get("agent", settings.agent))
        settings.timeout = int(data.get("timeout", settings.timeout))
        settings.workspace = str(data.get("workspace", settings.workspace))
        settings.session = str(data.get("session", settings.session))
        settings.no_memory = bool(data.get("no_memory", settings.no_memory))
        mcp_config = data.get("mcp_config", settings.mcp_config)
        settings.mcp_config = None if mcp_config in (None, "") else str(mcp_config)

        raw_keys = data.get("api_keys", {})
        if isinstance(raw_keys, dict):
            settings.api_keys = {
                str(k): str(v) for k, v in raw_keys.items() if str(v).strip()
            }
        return settings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SettingsStore:
    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()
        self.path = self.workspace / ".mini_worker" / "config.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return AppSettings.from_dict(data)
        except Exception:
            return AppSettings()
        return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
