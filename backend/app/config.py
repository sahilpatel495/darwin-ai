"""Runtime settings, all from environment variables.

Why chains instead of one model: the project runs on free tiers only, so reliability
comes from failing over between providers. A chain is an ordered list of
"provider:model"; providers without an API key are skipped.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# name -> (OpenAI-compatible base URL, env var holding the key or None if keyless)
PROVIDERS: dict[str, tuple[str, str | None]] = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": (os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), None),
    "custom": (os.environ.get("LLM_BASE_URL", ""), "LLM_API_KEY"),
}

DEFAULT_CHAINS: dict[str, str] = {
    # Groq's free limits are per model, so alternating models spreads the token budget.
    "sql": "groq:openai/gpt-oss-120b,nvidia:deepseek-ai/deepseek-v4-flash-0731,"
    "groq:qwen/qwen3.8-27b,gemini:gemma-4-31b-it,openrouter:qwen/qwen3.8-27b:free",
    # A different model family from the primary, so agreement means something.
    "crosscheck": "groq:qwen/qwen3.8-27b,nvidia:deepseek-ai/deepseek-v4-flash-0731,"
    "openrouter:z-ai/glm-5.2:free",
    "narrate": "groq:openai/gpt-oss-20b,gemini:gemma-4-31b-it,"
    "openrouter:google/gemma-4-31b-it:free",
}


@dataclass(frozen=True)
class ProviderModel:
    provider: str
    model: str
    base_url: str
    api_key: str


def chain(role: str) -> list[ProviderModel]:
    """Resolve LLM_<ROLE>_CHAIN (or the default) to usable provider/model pairs, in order."""
    spec = os.environ.get(f"LLM_{role.upper()}_CHAIN", DEFAULT_CHAINS[role])
    out: list[ProviderModel] = []
    for item in filter(None, (s.strip() for s in spec.split(","))):
        provider, _, model = item.partition(":")
        base_url, key_env = PROVIDERS[provider]
        key = os.environ.get(key_env, "") if key_env else "none"
        if base_url and key:
            out.append(ProviderModel(provider, model, base_url, key))
    return out


@dataclass(frozen=True)
class Settings:
    max_upload_mb: int = int(os.environ.get("MAX_UPLOAD_MB", "25"))
    query_timeout_s: float = float(os.environ.get("QUERY_TIMEOUT_S", "10"))
    row_cap: int = int(os.environ.get("ROW_CAP", "5000"))
    duckdb_memory_limit: str = os.environ.get("DUCKDB_MEMORY_LIMIT", "512MB")
    duckdb_threads: int = int(os.environ.get("DUCKDB_THREADS", "2"))
    session_ttl_s: int = int(os.environ.get("SESSION_TTL_S", "7200"))
    max_sessions: int = int(os.environ.get("MAX_SESSIONS", "20"))
    asks_per_ip_per_hour: int = int(os.environ.get("ASKS_PER_IP_PER_HOUR", "60"))
    llm_calls_per_day: int = int(os.environ.get("LLM_CALLS_PER_DAY", "3000"))
    crosscheck: bool = os.environ.get("CROSSCHECK", "on") == "on"
    llm_cache_dir: str = os.environ.get("LLM_CACHE_DIR", "")  # set by the eval runner only
    work_dir: Path = Path(os.environ.get("WORK_DIR", "/tmp/verity"))
    demo_data_dir: Path = Path(os.environ.get("DEMO_DATA_DIR", "demo_data"))


settings = Settings()
