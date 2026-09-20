"""One narrow interface to any OpenAI-compatible model, with provider failover.

Why a pool: the project runs on free tiers only, so any single provider will rate-limit
or retire a model at some point. Reliability comes from walking an ordered chain
(app.config.chain) and recording which provider actually answered.

Why error reasons are fixed phrases: provider error bodies can echo request headers or
keys. Nothing a provider says is ever copied into an exception message or a log line.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import openai
from pydantic import BaseModel

from app import config
from app.config import ProviderModel

log = logging.getLogger(__name__)

Role = Literal["sql", "crosscheck", "narrate"]
Messages = list[dict[str, str]]

REQUEST_TIMEOUT_S = 30
MAX_RETRY_AFTER_S = 10.0  # longer waits are not worth holding a user's question for

# Structured output, from strictest to none. Not every provider supports every rung.
_FORMATS = ("json_schema", "json_object", "none")
_FORMAT_COMPLAINT = re.compile(r"response.?format|json.?schema|json.?object", re.IGNORECASE)
# A reply that opens with an unclosed <think> was cut off mid-reasoning: all of it is dropped.
# Only at the very start, so a stray "<think>" inside a JSON string cannot eat the answer.
_THINK = re.compile(r"<think>.*?</think>|\A<think>.*", re.DOTALL)


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


class _ProviderFailed(Exception):
    """One provider could not answer; the pool moves on. `reason` is safe to show a user."""

    def __init__(self, reason: str, retry_after: float | None = None):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


# The daily budget protects the API keys on a public URL, so it is shared by every
# PoolClient in the process rather than trusting callers to reuse one instance.
# ponytail: in-memory, so a restart resets it and several workers each get a full budget.
# The app runs one worker and the provider-side spend cap is the hard limit; persist the
# counter under settings.work_dir if that ever changes.
_budget_lock = threading.Lock()
_budget: dict[str, Any] = {"day": "", "calls": 0}


def _spend_one_call() -> None:
    """Count one outbound request against today's (UTC) budget, or refuse it."""
    today = datetime.now(UTC).date().isoformat()
    with _budget_lock:
        if _budget["day"] != today:
            _budget.update(day=today, calls=0)
        if _budget["calls"] >= config.settings.llm_calls_per_day:
            raise LLMUnavailable(
                "This app has reached its daily limit of AI model calls. "
                "Please try again tomorrow, or run Verity locally with your own API key."
            )
        _budget["calls"] += 1


def _new_openai_client(pm: ProviderModel) -> openai.OpenAI:
    # max_retries=0: the pool is the retry policy. SDK retries would hide a rate limit
    # behind a long silent wait instead of moving to the next provider.
    return openai.OpenAI(
        base_url=pm.base_url, api_key=pm.api_key, timeout=REQUEST_TIMEOUT_S, max_retries=0
    )


def _extra_body(pm: ProviderModel) -> dict | None:
    """Ask each provider, in its own dialect, to keep reasoning text out of the reply."""
    if pm.provider == "openrouter":
        return {"reasoning": {"exclude": True}}
    if pm.model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    if pm.provider == "groq" and pm.model.startswith("qwen/"):
        return {"reasoning_format": "hidden"}
    return None


def _response_format(fmt: str, json_schema: dict | None) -> dict:
    if fmt == "json_schema":
        name = re.sub(r"\W", "_", str((json_schema or {}).get("title", "reply")))
        spec = {"name": name, "strict": True, "schema": json_schema}
        return {"response_format": {"type": "json_schema", "json_schema": spec}}
    if fmt == "json_object":
        return {"response_format": {"type": "json_object"}}
    return {}


def _plain_reason(exc: openai.APIError) -> str:
    """A fixed phrase per failure type. Never the provider's own text (see module docstring)."""
    if isinstance(exc, openai.APITimeoutError):
        return f"did not reply within {REQUEST_TIMEOUT_S} seconds"
    if isinstance(exc, openai.APIConnectionError):
        return "could not be reached"
    status = getattr(exc, "status_code", None)
    if status == 429:
        return "is rate limited (429)"
    if status in (401, 403):
        return f"rejected the API key ({status})"
    if status == 404:
        return "does not offer this model any more (404)"
    if isinstance(status, int) and status >= 500:
        return f"had a server error ({status})"
    return f"rejected the request ({status or 'unexpected error'})"


def _blames_the_format(exc: openai.BadRequestError) -> bool:
    """True when the provider says it cannot do the response_format we asked for.

    Only the provider's own sentence is searched. The rest of the error body can quote the
    model's failed output (Groq's json_validate_failed does), and our prompt itself says
    "JSON object", so searching everything would step a healthy provider down for good."""
    body = exc.body if isinstance(exc.body, dict) else {}
    return bool(_FORMAT_COMPLAINT.search(str(body.get("message") or exc)))


def _retry_after_s(exc: openai.APIError) -> float | None:
    response = getattr(exc, "response", None)
    try:
        return max(0.0, float(response.headers["retry-after"]))
    except (AttributeError, KeyError, ValueError):
        return None  # absent, or an HTTP date: not worth parsing for a 10-second window


def _outermost_json(text: str) -> str:
    """The first complete JSON object in `text`, so prose and code fences around it do no
    harm. Returns the text unchanged when there is none; the caller's validation reports it."""
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            _, end = decoder.raw_decode(text, start)
            return text[start:end]
        except ValueError:
            start = text.find("{", start + 1)
    return text


def _cache_path(pm: ProviderModel, messages: Messages, schema: dict | None) -> Path | None:
    folder = config.settings.llm_cache_dir
    if not folder:
        return None
    key = json.dumps({"model": pm.model, "messages": messages, "schema": schema}, sort_keys=True)
    return Path(folder) / f"{hashlib.sha256(key.encode()).hexdigest()}.json"


def _cache_read(path: Path | None) -> LLMResult | None:
    if path is None:
        return None
    try:
        saved = json.loads(path.read_text("utf-8"))
        return LLMResult(content=saved["content"], provider=saved["provider"],
                         model=saved["model"], cached=True)
    except (OSError, ValueError, KeyError, TypeError):
        return None  # missing or damaged entry: just ask the model again


def _cache_write(path: Path | None, result: LLMResult) -> None:
    if path is None:
        return
    saved = result.model_dump(include={"content", "provider", "model"})
    draft = path.with_suffix(f".{threading.get_ident()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(json.dumps(saved), "utf-8")
        os.replace(draft, path)  # atomic: the cross-check thread never reads half a file
    except OSError:
        log.warning("Could not write the LLM cache entry %s; the answer is unaffected.", path.name)


class PoolClient:
    """Walks app.config.chain(role) in order. 429/5xx/timeout -> next provider (honouring a
    short retry-after once). temperature 0. json_schema: try strict json_schema, fall back to
    json_object on a 400, and always tolerate prose around the JSON. Reasoning output is
    requested hidden and any <think>...</think> block is stripped. When
    settings.llm_cache_dir is set, responses are cached on disk keyed by
    sha256(model + messages + schema). Counts calls against settings.llm_calls_per_day."""

    def __init__(self, client_factory: Callable[[ProviderModel], Any] | None = None):
        self._client_factory = client_factory or _new_openai_client
        self._clients: dict[ProviderModel, Any] = {}
        # Index into _FORMATS of the strictest format each provider has not rejected, so an
        # unsupported format costs one wasted request per process, not one per question.
        self._format_floor: dict[ProviderModel, int] = {}

    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult:
        providers = config.chain(role)
        if not providers:
            raise LLMUnavailable(
                "No AI model is configured. Add a provider API key (for example GROQ_API_KEY) "
                "to the .env file and restart the app."
            )
        # Any model in this chain having answered this exact prompt before is good enough:
        # the eval runner must not re-spend tokens because the first provider is busy today.
        for pm in providers:
            if hit := _cache_read(_cache_path(pm, messages, json_schema)):
                return hit

        failures: list[str] = []
        soonest: tuple[float, ProviderModel] | None = None
        for pm in providers:
            try:
                return self._ask(pm, messages, json_schema)
            except _ProviderFailed as failed:
                failures.append(self._note_failure(pm, failed.reason))
                wait = failed.retry_after
                worth_waiting = wait is not None and wait <= MAX_RETRY_AFTER_S
                if worth_waiting and (soonest is None or wait < soonest[0]):
                    soonest = (wait, pm)

        if soonest is not None:  # everyone failed, but one provider said "back in a moment"
            wait, pm = soonest
            time.sleep(wait)
            try:
                return self._ask(pm, messages, json_schema)
            except _ProviderFailed as failed:
                failures.append(self._note_failure(pm, f"{failed.reason} again after a short wait"))

        raise LLMUnavailable(
            "No AI model could answer just now: " + "; ".join(failures)
            + ". Please wait a minute and ask again."
        )

    @staticmethod
    def _note_failure(pm: ProviderModel, reason: str) -> str:
        note = f"{pm.provider} ({pm.model}) {reason}"
        log.warning("LLM provider failed: %s", note)
        return note

    def _client(self, pm: ProviderModel) -> Any:
        if pm not in self._clients:
            self._clients[pm] = self._client_factory(pm)
        return self._clients[pm]

    def _ask(self, pm: ProviderModel, messages: Messages, json_schema: dict | None) -> LLMResult:
        started = time.monotonic()
        text = _THINK.sub("", self._raw_reply(pm, messages, json_schema).strip()).strip()
        if not text:
            raise _ProviderFailed("returned an empty reply")
        result = LLMResult(
            content=_outermost_json(text) if json_schema else text,
            provider=pm.provider,
            model=pm.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        _cache_write(_cache_path(pm, messages, json_schema), result)
        return result

    def _raw_reply(self, pm: ProviderModel, messages: Messages, json_schema: dict | None) -> str:
        """Ask one provider, stepping down the structured-output formats it rejects."""
        step = self._format_floor.get(pm, 0) if json_schema else len(_FORMATS) - 1
        while True:
            fmt = _FORMATS[step]
            request: dict[str, Any] = {"model": pm.model, "messages": messages, "temperature": 0}
            request.update(_response_format(fmt, json_schema))
            if extra := _extra_body(pm):
                request["extra_body"] = extra
            _spend_one_call()
            try:
                reply = self._client(pm).chat.completions.create(**request)
            except openai.BadRequestError as exc:
                if fmt == "none" or not _blames_the_format(exc):
                    raise _ProviderFailed(_plain_reason(exc)) from None
                step += 1
                self._format_floor[pm] = step
                continue
            except openai.APIError as exc:
                raise _ProviderFailed(_plain_reason(exc), _retry_after_s(exc)) from None
            except Exception as exc:  # noqa: BLE001
                # Deliberately broad. A 200 whose body is not JSON escapes the SDK as a bare
                # JSONDecodeError; one misbehaving provider must not stop the whole chain.
                # Only the error's type name is kept, never its text (see module docstring).
                unreadable = f"sent a reply that could not be read ({type(exc).__name__})"
                raise _ProviderFailed(unreadable) from None
            try:  # some gateways answer 200 with no choices when their upstream failed
                content = reply.choices[0].message.content
            except (AttributeError, IndexError, TypeError):
                return ""
            return content if isinstance(content, str) else ""  # a list of parts is no answer
