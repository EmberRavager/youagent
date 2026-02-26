import json
from dataclasses import dataclass
from typing import Any
from urllib import request
from urllib.error import HTTPError

from .config import APIConfig, resolve_api_config


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 60


class ChatClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    @classmethod
    def from_options(
        cls,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
        timeout_seconds: int,
    ) -> "ChatClient":
        resolved: APIConfig = resolve_api_config(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        return cls(
            LLMConfig(
                provider=resolved.provider,
                api_key=resolved.api_key,
                base_url=resolved.base_url,
                model=resolved.model,
                timeout_seconds=resolved.timeout_seconds,
            )
        )

    def chat_completion(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
        }

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.cfg.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.cfg.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed: {exc.code} {body}") from exc
