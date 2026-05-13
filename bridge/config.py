"""
ZGX AI Bridge configuration.
All settings loaded from environment variables with defaults.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # Bridge server
    bridge_host: str = "0.0.0.0"
    bridge_port: int = 8080
    log_level: str = "info"

    # vLLM connection
    vllm_base_url: str = "http://localhost:8090/v1"
    vllm_model: str = "Qwen/Qwen3-14B-AWQ"
    vllm_timeout_seconds: int = 120

    # Auth
    api_keys: list[str] = field(default_factory=lambda: ["dev-test-key"])

    # Sessions
    session_ttl_minutes: int = 30
    session_max_turns: int = 50

    # Context
    context_max_size_bytes: int = 32768

    # System prompt
    system_prompt_base: str = (
        "You are a helpful AI assistant embedded in an enterprise application. "
        "Answer questions using the provided application context. "
        "Be concise and professional. "
        "Do not fabricate data that is not present in the context."
    )


def load_config() -> Config:
    """Load config from environment variables, falling back to defaults."""
    api_keys_raw = os.environ.get("BRIDGE_API_KEYS", "dev-test-key")
    api_keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]

    return Config(
        bridge_host=os.environ.get("BRIDGE_HOST", "0.0.0.0"),
        bridge_port=int(os.environ.get("BRIDGE_PORT", "8080")),
        log_level=os.environ.get("BRIDGE_LOG_LEVEL", "info"),
        vllm_base_url=os.environ.get("VLLM_BASE_URL", "http://localhost:8090/v1"),
        vllm_model=os.environ.get("VLLM_MODEL", "Qwen/Qwen3-14B-AWQ"),
        vllm_timeout_seconds=int(os.environ.get("VLLM_TIMEOUT_SECONDS", "120")),
        api_keys=api_keys,
        session_ttl_minutes=int(os.environ.get("SESSION_TTL_MINUTES", "30")),
        session_max_turns=int(os.environ.get("SESSION_MAX_TURNS", "50")),
        context_max_size_bytes=int(os.environ.get("CONTEXT_MAX_SIZE_BYTES", "32768")),
        system_prompt_base=os.environ.get(
            "SYSTEM_PROMPT_BASE",
            Config.system_prompt_base,
        ),
    )
