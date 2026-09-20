"""Runtime settings, all from environment variables.

Why chains instead of one model: the project runs on free tiers only, so reliability
comes from failing over between providers. A chain is an ordered list of
"provider:model"; providers without an API key are skipped.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


def _env(name: str, default: str) -> str:
    """A variable set to an empty string (common in hosting dashboards) counts as unset."""
    return os.environ.get(name, "").strip() or default

# name -> (OpenAI-compatible base URL, env var holding the key or None if keyless)
PROVIDERS: dict[str, tuple[str, str | None]] = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": (_env("OLLAMA_BASE_URL", "http://localhost:11434/v1"), None),
    "custom": (_env("LLM_BASE_URL", ""), "LLM_API_KEY"),
}

# Providers reached at a URL the operator chose, which is itself the decision to trust them.
# Their key is optional; a "custom:" entry still needs LLM_BASE_URL, so it cannot resolve by accident.
KEYLESS_PROVIDERS = frozenset({"ollama", "custom"})

DEFAULT_CHAINS: dict[str, str] = {
    # Free-tier limits are per model, so a long chain over different models is the budget.
    # Entries whose provider has no API key are skipped. Order = preference.
    "sql": "groq:openai/gpt-oss-120b,nvidia:deepseek-ai/deepseek-v4-flash-0731,"
    "groq:qwen/qwen3.8-27b,gemini:gemma-4-31b-it,openrouter:qwen/qwen3.8-27b:free,"
    "openrouter:z-ai/glm-5.2:free,openrouter:nvidia/nemotron-3-super-120b-a12b:free,"
    "groq:openai/gpt-oss-20b",  # last resort: smaller, but an answer beats an error
    # A different model family from whichever model answered, so agreement means something.
    "crosscheck": "groq:qwen/qwen3.8-27b,nvidia:deepseek-ai/deepseek-v4-flash-0731,"
    "groq:openai/gpt-oss-120b,openrouter:z-ai/glm-5.2:free,gemini:gemma-4-31b-it",
    "narrate": "groq:openai/gpt-oss-20b,gemini:gemma-4-31b-it,groq:qwen/qwen3.8-27b,"
    "openrouter:google/gemma-4-31b-it:free",
}


@dataclass(frozen=True)
class ProviderModel:
    provider: str
    model: str
    base_url: str
    api_key: str = field(repr=False)  # a stray %r or traceback must never print it


def chain(role: str) -> list[ProviderModel]:
    """Resolve LLM_<ROLE>_CHAIN (or the default) to usable provider/model pairs, in order."""
    spec = _env(f"LLM_{role.upper()}_CHAIN", DEFAULT_CHAINS[role])
    out: list[ProviderModel] = []
    for item in filter(None, (s.strip() for s in spec.split(","))):
        provider, _, model = item.partition(":")
        if provider not in PROVIDERS or not model:
            log.warning("ignoring chain entry %r: expected provider:model with provider in %s", item, sorted(PROVIDERS))
            continue
        base_url, key_env = PROVIDERS[provider]
        key = os.environ.get(key_env, "").strip() if key_env else ""
        if provider in KEYLESS_PROVIDERS:
            # Ollama, a customer's gateway and a self-hosted vLLM server usually authenticate by
            # network, or not at all. The OpenAI client still wants a string, so "none" stands in.
            # Every other provider is skipped without a key: a live 401 would waste the failover.
            key = key or "none"
        if base_url and key:
            out.append(ProviderModel(provider, model, base_url, key))
    return out


@dataclass(frozen=True)
class Settings:
    max_upload_mb: int = int(_env("MAX_UPLOAD_MB", "25"))
    query_timeout_s: float = float(_env("QUERY_TIMEOUT_S", "10"))
    row_cap: int = int(_env("ROW_CAP", "5000"))
    duckdb_memory_limit: str = _env("DUCKDB_MEMORY_LIMIT", "512MB")
    duckdb_threads: int = int(_env("DUCKDB_THREADS", "2"))
    session_ttl_s: int = int(_env("SESSION_TTL_S", "7200"))
    max_sessions: int = int(_env("MAX_SESSIONS", "20"))
    # Abuse limits. There are no accounts, so "a user" is a client IP (see app.limits).
    asks_per_ip_per_hour: int = int(_env("ASKS_PER_IP_PER_HOUR", "40"))
    asks_per_ip_per_day: int = int(_env("ASKS_PER_IP_PER_DAY", "200"))
    asks_per_session: int = int(_env("ASKS_PER_SESSION", "150"))
    sessions_per_ip_per_hour: int = int(_env("SESSIONS_PER_IP_PER_HOUR", "20"))
    uploads_per_ip_per_hour: int = int(_env("UPLOADS_PER_IP_PER_HOUR", "30"))
    max_concurrent_asks: int = int(_env("MAX_CONCURRENT_ASKS", "6"))
    max_concurrent_asks_per_ip: int = int(_env("MAX_CONCURRENT_ASKS_PER_IP", "2"))
    # Which X-Forwarded-For entry is the client, counted from the right. 1 = the address the
    # nearest proxy appended. Raise it when the host puts a CDN in front of its own router.
    trusted_proxy_hops: int = int(_env("TRUSTED_PROXY_HOPS", "1"))
    # How long a question may wait for a rate-limited free model before giving up.
    llm_max_wait_s: float = float(_env("LLM_MAX_WAIT_S", "25"))
    llm_calls_per_day: int = int(_env("LLM_CALLS_PER_DAY", "3000"))
    crosscheck: bool = _env("CROSSCHECK", "on") == "on"
    llm_cache_dir: str = _env("LLM_CACHE_DIR", "")  # set by the eval runner only
    work_dir: Path = Path(_env("WORK_DIR", "/tmp/verity"))
    demo_data_dir: Path = Path(_env("DEMO_DATA_DIR", "demo_data"))


settings = Settings()
