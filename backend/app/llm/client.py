"""One narrow interface to any OpenAI-compatible model, with provider failover.

Why a pool: the project runs on free tiers only, so any single provider will rate-limit
or retire a model at some point. Reliability comes from walking an ordered chain
(app.config.chain) and recording which provider actually answered.

Why the pool has a memory: free limits are per model and reset within seconds or minutes.
An entry that fails is put on a cooldown and skipped, with no network call, until the time
the provider itself named. Without that, every question would spend a request (and the
user's time) rediscovering the same rate limit.

Why error reasons are fixed phrases: provider error bodies can echo request headers or
keys. Nothing a provider says is ever copied into an exception message or a log line; the
only thing read out of a provider's words is a number of seconds.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
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

# How long a chain entry is left alone after it fails. A 429 uses the provider's own hint.
RATE_LIMIT_DEFAULT_S = 20.0  # a 429 that does not say when to come back
# ponytail: the 120 s ceiling means a spent DAILY allowance (reset hours away) is re-probed
# every two minutes, one wasted request each time. Keep the unclamped hint if logs show it.
RATE_LIMIT_CLAMP_S = (1.0, 120.0)
TROUBLE_COOLDOWN_S = 15.0  # timeout, lost connection, 5xx, unreadable or empty reply
PARKED_S = 3600.0  # rejected key or retired model: it will not fix itself within the hour
MAX_WAITS = 2  # naps per call while the whole chain is cooling (role "sql" only)
MIN_RETRY_HINT_S = 5  # never tell a user "try again in 1 second"
REPLY_TOKENS = 600  # room kept for the answer when sizing a request against an allowance

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
    """No model could answer. The message is one complete sentence for the user, with no
    provider names, model ids, status codes or keys. `retry_after_s` is set only when waiting
    will help, so the UI can count down instead of guessing."""

    def __init__(self, message: str, retry_after_s: int | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


class LLMClient(Protocol):
    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult: ...


class _ProviderFailed(Exception):
    """One entry could not answer; the pool moves on. `reason` is a fixed phrase for the
    operator's log and `cool_s` is how long the pool should leave this entry alone."""

    def __init__(self, reason: str, cool_s: float = TROUBLE_COOLDOWN_S):
        super().__init__(reason)
        self.reason = reason
        self.cool_s = cool_s


@dataclass
class _Health:
    """What the pool remembers about one (provider, model). Times are monotonic seconds."""

    cooling_until: float = 0.0
    reason: str = ""  # why it is cooling: a fixed phrase, for the log only
    tokens_left: int | None = None  # last x-ratelimit-remaining-tokens; None = never told
    tokens_reset_at: float = 0.0  # when that allowance refills


# Process-wide for the same reason as the budget below: a rate limit belongs to the API key,
# not to whichever PoolClient object happened to hit it. One lock: routes run on threads.
# ponytail: in-memory and per process, so several workers would each rediscover a limit (one
# wasted request per worker per cooldown). The app runs one worker; share it if that changes.
_health_lock = threading.Lock()
_health: dict[tuple[str, str], _Health] = {}


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


# Where a 429 says when to come back, in the order they are trusted. Groq writes its reset
# headers and its error sentence as durations like "7.66s", "2m59.56s" or "380ms".
_RETRY_HEADERS = ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests")
_UNIT_S = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
_DURATION = r"(?:\d+(?:\.\d+)?(?:ms|h|m|s))+"
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_TRY_AGAIN_IN = re.compile(rf"try again in ({_DURATION})", re.IGNORECASE)


def _seconds(text: str) -> float | None:
    """'7', '7.66s' or '2m59.56s' as seconds. None for anything else (an HTTP date, say),
    so the caller falls through to its next hint."""
    text = text.strip().lower()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    if not re.fullmatch(_DURATION, text):
        return None
    return sum(float(number) * _UNIT_S[unit] for number, unit in _DURATION_PART.findall(text))


def _rate_limit_hint_s(exc: openai.APIError) -> float:
    """How long a 429 asks us to stay away: the first hint that parses, clamped. Only a
    number is taken from the provider's headers or sentence, never its words."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    hints = [headers.get(name, "") for name in _RETRY_HEADERS]
    if said := _TRY_AGAIN_IN.search(str(exc)):
        hints.append(said.group(1))
    found = next((s for s in map(_seconds, hints) if s is not None), RATE_LIMIT_DEFAULT_S)
    low, high = RATE_LIMIT_CLAMP_S
    return min(max(found, low), high)


def _cooldown_s(exc: openai.APIError) -> float:
    """How long to leave an entry alone after this failure.

    0 means the provider is healthy and refused this one request (too long, say). That is
    no reason to keep other questions away from it, but asking it the same thing again
    would replay the same refusal, so the pool drops it for the current call only."""
    status = getattr(exc, "status_code", None)
    if status == 429:
        return _rate_limit_hint_s(exc)
    if status in (401, 403, 404):  # a bad key or a retired model needs a human, not a retry
        return PARKED_S
    if isinstance(status, int) and 400 <= status < 500:
        return 0.0
    return TROUBLE_COOLDOWN_S  # timeout, lost connection, 5xx


def _estimated_tokens(messages: Messages) -> int:
    """Rough size of a request: four characters per token, plus room for the reply.

    ponytail: a heuristic, not a tokenizer. It only has to spot a request that is certain to
    be refused; a wrong guess costs one 429, which the cooldown then absorbs."""
    return sum(len(m.get("content") or "") for m in messages) // 4 + REPLY_TOKENS


def _same_model(model: str, other: str | None) -> bool:
    """True when two ids name the same weights: "qwen/qwen3.8-27b" on one provider is
    "qwen/qwen3.8-27b:free" on another, and a model agreeing with itself proves nothing."""

    def bare(name: str) -> str:
        return name.rsplit("/", 1)[-1].removesuffix(":free")

    return other is not None and bare(model) == bare(other)


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
    """Walks app.config.chain(role) in order and remembers who is rate limited.

    A failed entry goes on a cooldown (the provider's own retry hint for a 429, 15 s for a
    timeout or 5xx, an hour for a rejected key or a retired model) and is skipped without a
    network call until it passes. A request the provider refuses outright (a 400) says
    nothing about its health, so it costs no cooldown. An entry whose remaining token
    allowance cannot fit the request is skipped like a cooling one. Role "sql" will nap
    until the soonest entry is free, within
    settings.llm_max_wait_s; "crosscheck" and "narrate" never wait, because the pipeline
    already degrades gracefully without them.

    temperature 0. json_schema: try strict json_schema, fall back to json_object on a 400,
    and always tolerate prose around the JSON. Reasoning output is requested hidden and any
    <think>...</think> block is stripped. When settings.llm_cache_dir is set, responses are
    cached on disk keyed by sha256(model + messages + schema). Counts calls against
    settings.llm_calls_per_day. `clock` and `sleep` are injectable so tests run instantly."""

    def __init__(
        self,
        client_factory: Callable[[ProviderModel], Any] | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._client_factory = client_factory or _new_openai_client
        self._clock = clock
        self._sleep = sleep
        self._clients: dict[ProviderModel, Any] = {}
        # Index into _FORMATS of the strictest format each provider has not rejected, so an
        # unsupported format costs one wasted request per process, not one per question.
        self._format_floor: dict[ProviderModel, int] = {}

    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult:
        return self._complete(role, messages, json_schema, None, None)

    def with_options(
        self,
        *,
        avoid_model: str | None = None,
        on_wait: Callable[[float], None] | None = None,
    ) -> LLMClient:
        """The same pool (same cooldowns, cache and daily budget) with per-call options
        pinned, so callers such as app.query.generator keep calling plain complete(...).

        avoid_model: skip that model, so a cross-check never runs on the model whose answer
        it is checking. on_wait(seconds): called just before a bounded wait, so the UI can
        say "retrying in 8 seconds"."""
        return _PoolView(self, avoid_model, on_wait)

    def _complete(
        self,
        role: Role,
        messages: Messages,
        json_schema: dict | None,
        avoid_model: str | None,
        on_wait: Callable[[float], None] | None,
    ) -> LLMResult:
        """One call: the disk cache, then a walk down the chain, then (role "sql" only) a
        nap until the soonest entry is free and another walk. Shared by complete() and by
        every with_options view, which is why they all see the same cooldowns."""
        chain = config.chain(role)
        if not chain:
            raise LLMUnavailable(
                "No AI model is configured. Add a provider API key (for example GROQ_API_KEY) "
                "to the .env file and restart the app."
            )
        providers = [pm for pm in chain if not _same_model(pm.model, avoid_model)]
        if not providers:
            raise LLMUnavailable("No second AI model is configured to double-check this answer.")
        # Any model in this chain having answered this exact prompt before is good enough:
        # the eval runner must not re-spend tokens because the first provider is busy today.
        for pm in providers:
            if hit := _cache_read(_cache_path(pm, messages, json_schema)):
                return hit

        need = _estimated_tokens(messages)
        waited = 0.0
        for walk in range(MAX_WAITS + 1):
            for pm in list(providers):  # a copy: a refusal of this request drops the entry
                if self._blocked_for(pm, need)[0] > 0:
                    continue  # cooling: skipped without a network call
                try:
                    return self._ask(pm, messages, json_schema)
                except _ProviderFailed as failed:
                    self._note_failure(pm, failed)
                    if failed.cool_s == 0:
                        providers.remove(pm)
            if not providers:  # every model refused the request itself: waiting cannot help
                raise LLMUnavailable(
                    "The AI models could not work with this question. "
                    "Try asking it in a shorter or simpler way."
                )
            # Nobody answered. Only the user's own question is worth holding the request
            # open for, and only for llm_max_wait_s in total however the naps are split.
            wait = min(self._blocked_for(pm, need)[0] for pm in providers)
            out_of_patience = waited + wait > config.settings.llm_max_wait_s
            if role != "sql" or walk == MAX_WAITS or out_of_patience:
                break
            if wait > 0:  # 0 = an entry came free while the others were being tried
                waited += wait
                self._announce(on_wait, wait)
                self._sleep(wait)
        raise self._gave_up(role, providers, need)

    def _blocked_for(self, pm: ProviderModel, need: int) -> tuple[float, str]:
        """(seconds until this entry may be tried, why). (0.0, "") means go ahead."""
        now = self._clock()
        with _health_lock:
            health = _health.get((pm.provider, pm.model))
            if health is None:
                return 0.0, ""
            if health.cooling_until > now:
                return health.cooling_until - now, health.reason
            # Token pacing: do not spend a request that is certain to be refused. Once the
            # reset time has passed the remembered number means nothing, so it is ignored.
            starved = health.tokens_left is not None and health.tokens_left < need
            if starved and health.tokens_reset_at > now:
                return health.tokens_reset_at - now, "has too few tokens left this minute"
        return 0.0, ""

    def _note_failure(self, pm: ProviderModel, failed: _ProviderFailed) -> None:
        """Put the entry on cooldown and tell the operator why (never the user, never a key)."""
        if failed.cool_s == 0:  # it refused this request only: see _cooldown_s
            log.info("LLM %s (%s) %s; not asked again for this question",
                     pm.provider, pm.model, failed.reason)
            return
        with _health_lock:
            health = _health.setdefault((pm.provider, pm.model), _Health())
            health.cooling_until = self._clock() + failed.cool_s
            health.reason = failed.reason
        # A parked entry needs a human, so it is a warning; being skipped for the next hour
        # is what makes it appear once rather than once per question. A rate limit on a free
        # tier is routine: info.
        level = logging.WARNING if failed.cool_s >= PARKED_S else logging.INFO
        log.log(level, "LLM %s (%s) %s; leaving it alone for %.0f s",
                pm.provider, pm.model, failed.reason, failed.cool_s)

    def _remember_allowance(self, pm: ProviderModel, headers: Any) -> None:
        """After a success, note what is left of this minute's tokens (Groq says; most
        providers do not, and then pacing is simply off for them)."""
        try:
            left = int(headers["x-ratelimit-remaining-tokens"])
            reset_s = _seconds(headers["x-ratelimit-reset-tokens"])
        except (KeyError, TypeError, ValueError):
            return
        if reset_s is None:
            return
        with _health_lock:
            health = _health.setdefault((pm.provider, pm.model), _Health())
            health.tokens_left, health.tokens_reset_at = left, self._clock() + reset_s

    @staticmethod
    def _announce(on_wait: Callable[[float], None] | None, seconds: float) -> None:
        if on_wait is None:
            return
        try:
            on_wait(seconds)
        except Exception:  # noqa: BLE001 - a progress message must never cost the answer
            log.info("The on_wait callback failed; the call carries on without it.")

    def _gave_up(self, role: Role, providers: list[ProviderModel], need: int) -> LLMUnavailable:
        """One honest sentence for the user; who is blocked, and why, for the operator."""
        states = [(pm, *self._blocked_for(pm, need)) for pm in providers]
        log.info("No model could take this %s call: %s", role, "; ".join(
            f"{pm.provider} ({pm.model}) {why or 'is free again'}, {seconds:.0f} s to go"
            for pm, seconds, why in states))
        n = max(MIN_RETRY_HINT_S, math.ceil(min(seconds for _, seconds, _ in states)))
        return LLMUnavailable(
            f"All the free AI models are busy right now. Try again in about {n} seconds.",
            retry_after_s=n,
        )

    def _client(self, pm: ProviderModel) -> Any:
        if pm not in self._clients:
            self._clients[pm] = self._client_factory(pm)
        return self._clients[pm]

    def _ask(self, pm: ProviderModel, messages: Messages, json_schema: dict | None) -> LLMResult:
        started = self._clock()
        text = _THINK.sub("", self._raw_reply(pm, messages, json_schema).strip()).strip()
        if not text:
            raise _ProviderFailed("returned an empty reply")
        result = LLMResult(
            content=_outermost_json(text) if json_schema else text,
            provider=pm.provider,
            model=pm.model,
            latency_ms=int((self._clock() - started) * 1000),
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
                # The raw form is the only way to the rate-limit headers. parse() sits inside
                # the try because a 200 whose body is not JSON now fails there, not in create.
                raw = self._client(pm).chat.completions.with_raw_response.create(**request)
                reply = raw.parse()
            except openai.BadRequestError as exc:
                if fmt == "none" or not _blames_the_format(exc):
                    raise _ProviderFailed(_plain_reason(exc), _cooldown_s(exc)) from None
                step += 1
                self._format_floor[pm] = step
                continue
            except openai.APIError as exc:
                raise _ProviderFailed(_plain_reason(exc), _cooldown_s(exc)) from None
            except Exception as exc:  # noqa: BLE001
                # Deliberately broad. A 200 whose body is not JSON escapes the SDK as a bare
                # JSONDecodeError; one misbehaving provider must not stop the whole chain.
                # Only the error's type name is kept, never its text (see module docstring).
                unreadable = f"sent a reply that could not be read ({type(exc).__name__})"
                raise _ProviderFailed(unreadable) from None
            self._remember_allowance(pm, raw.headers)
            try:  # some gateways answer 200 with no choices when their upstream failed
                content = reply.choices[0].message.content
            except (AttributeError, IndexError, TypeError):
                return ""
            return content if isinstance(content, str) else ""  # a list of parts is no answer


@dataclass(frozen=True)
class _PoolView:
    """What PoolClient.with_options returns: no state of its own, so cooldowns learned
    through a view protect every other caller too."""

    pool: PoolClient
    avoid_model: str | None
    on_wait: Callable[[float], None] | None

    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult:
        return self.pool._complete(role, messages, json_schema, self.avoid_model, self.on_wait)
