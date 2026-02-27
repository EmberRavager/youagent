import os
from dataclasses import dataclass


PROVIDER_PRESETS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "base_env": "OPENROUTER_BASE_URL",
    },
    "minimax": {
        "base_url": "https://api.minimaxi.com/v1",
        "key_env": "MINIMAX_API_KEY",
        "base_env": "MINIMAX_BASE_URL",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
        "base_env": "DEEPSEEK_BASE_URL",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "base_env": "GROQ_BASE_URL",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "key_env": "ANTHROPIC_API_KEY",
        "base_env": "ANTHROPIC_BASE_URL",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
        "base_env": "GEMINI_BASE_URL",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "key_env": "ZHIPU_API_KEY",
        "base_env": "ZHIPU_BASE_URL",
    },
    "volcengine": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "key_env": "VOLCENGINE_API_KEY",
        "base_env": "VOLCENGINE_BASE_URL",
    },
    "vllm": {
        "base_url": "http://127.0.0.1:8000/v1",
        "key_env": "VLLM_API_KEY",
        "base_env": "VLLM_BASE_URL",
    },
    "custom": {
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL",
    },
}


MINIMAX_MODEL_ALIASES = {
    "minmax": "MiniMax-M2.5",
    "minimax2.5": "MiniMax-M2.5",
    "m2.5": "MiniMax-M2.5",
    "minimax-m2.5": "MiniMax-M2.5",
}


@dataclass(frozen=True)
class APIConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: int = 60


def available_providers() -> list[str]:
    return sorted(PROVIDER_PRESETS.keys())


def resolve_api_config(
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout_seconds: int,
) -> APIConfig:
    selected = provider.lower().strip()
    cleaned_model = model.strip()
    if selected not in PROVIDER_PRESETS:
        options = ", ".join(available_providers())
        raise ValueError(f"Unknown provider '{provider}'. Available: {options}")

    preset = PROVIDER_PRESETS[selected]
    final_key = (
        api_key or os.getenv(preset["key_env"], "") or os.getenv("OPENAI_API_KEY", "")
    ).strip()
    final_base = (
        (
            base_url
            or os.getenv(preset["base_env"], "")
            or os.getenv("OPENAI_BASE_URL", "")
            or preset["base_url"]
        )
        .strip()
        .rstrip("/")
    )

    if not final_key:
        raise RuntimeError(
            f"API key missing. Provide --api-key or set {preset['key_env']} (or OPENAI_API_KEY)."
        )

    if not cleaned_model:
        raise ValueError("Model cannot be empty")

    if selected == "minimax":
        alias_key = cleaned_model.lower()
        cleaned_model = MINIMAX_MODEL_ALIASES.get(alias_key, cleaned_model)

    return APIConfig(
        provider=selected,
        model=cleaned_model,
        api_key=final_key,
        base_url=final_base,
        timeout_seconds=timeout_seconds,
    )
