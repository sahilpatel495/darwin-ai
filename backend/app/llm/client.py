"""One narrow interface to any OpenAI-compatible model, with provider failover."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

Role = Literal["sql", "crosscheck", "narrate"]


class LLMResult(BaseModel):
    content: str  # raw text (JSON when a schema was requested)
    provider: str
    model: str
    latency_ms: int = 0
    cached: bool = False


class LLMUnavailable(RuntimeError):
    """Every provider in the chain failed or none is configured."""


class LLMClient(Protocol):
    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult: ...


class PoolClient:
    """Walks app.config.chain(role) in order. 429/5xx/timeout -> next provider (honouring a
    short retry-after once). temperature 0. json_schema: try strict json_schema, fall back to
    json_object on a 400, and always tolerate prose around the JSON. Reasoning output is
    requested hidden and any <think>...</think> block is stripped. When
    settings.llm_cache_dir is set, responses are cached on disk keyed by
    sha256(model + messages + schema). Counts calls against settings.llm_calls_per_day."""

    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult:
        raise NotImplementedError
