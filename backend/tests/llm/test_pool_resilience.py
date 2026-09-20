"""PoolClient under rate limits: cooldowns, retry hints, token pacing, the bounded wait,
per-call options and the one honest sentence. Fake clients, a fake clock, no network."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import threading

import openai
import pytest
from app import config
from app.llm import client as client_module
from app.llm.client import LLMUnavailable, PoolClient

from .test_client import GROQ_KEY, NVIDIA_KEY, FakeOpenAI, _httpx, rate_limited, status_error

MESSAGES = [{"role": "user", "content": "Reply in JSON."}]
CHAIN = "groq:model-a,nvidia:model-b"


class FakeClock:
    """Time that moves only when somebody sleeps, so every wait is exact and instant."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.naps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.naps.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def two_entries_for_every_role(monkeypatch):
    for role in ("SQL", "CROSSCHECK", "NARRATE"):
        monkeypatch.setenv(f"LLM_{role}_CHAIN", CHAIN)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, llm_cache_dir=""))
    monkeypatch.setattr(client_module, "_budget", {"day": "", "calls": 0})
    monkeypatch.setattr(client_module, "_health", {})


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def pool(clock: FakeClock, **fakes: FakeOpenAI) -> PoolClient:
    """fakes are keyed a/b for model-a/model-b."""
    return PoolClient(
        client_factory=lambda pm: fakes[pm.model.rsplit("-", 1)[-1].removesuffix(":free")],
        clock=clock,
        sleep=clock.sleep,
    )


# --- 1. cooldowns -------------------------------------------------------------------------


def test_a_rate_limited_entry_is_skipped_without_a_call_until_its_cooldown_passes(clock):
    a = FakeOpenAI(rate_limited({"retry-after": "30"}), "a is back")
    b = FakeOpenAI("b1", "b2")
    client = pool(clock, a=a, b=b)

    assert client.complete(role="sql", messages=MESSAGES).provider == "nvidia"
    assert client.complete(role="sql", messages=MESSAGES).content == "b2"
    assert len(a.requests) == 1  # the second question never touched the limited model

    clock.now += 30
    assert client.complete(role="sql", messages=MESSAGES).content == "a is back"
    assert clock.naps == []


def test_cooldowns_are_shared_by_every_client_in_the_process(clock):
    a = FakeOpenAI(rate_limited())
    pool(clock, a=a, b=FakeOpenAI("b1")).complete(role="sql", messages=MESSAGES)
    untouched = FakeOpenAI()
    result = pool(clock, a=untouched, b=FakeOpenAI("b2")).complete(role="sql", messages=MESSAGES)
    assert result.content == "b2" and untouched.requests == []


@pytest.mark.parametrize(
    ("headers", "message", "seconds"),
    [
        ({"retry-after": "7"}, "Rate limit reached", 7.0),
        ({"x-ratelimit-reset-tokens": "7.66s"}, "Rate limit reached", 7.66),
        ({"x-ratelimit-reset-requests": "1m5.5s"}, "Rate limit reached", 65.5),
        ({}, "Rate limit reached for model x. Please try again in 7.66s. Need more?", 7.66),
        ({}, "Limit hit, try again in 1m2.5s.", 62.5),
        # the order: retry-after, then the reset headers (tokens first), then the sentence
        ({"retry-after": "3", "x-ratelimit-reset-tokens": "9s"}, "try again in 50s", 3.0),
        ({"x-ratelimit-reset-tokens": "9s", "x-ratelimit-reset-requests": "40s"}, "", 9.0),
        ({"x-ratelimit-reset-requests": "40s"}, "try again in 50s", 40.0),
        # an HTTP date is not worth parsing: fall through to the next hint
        ({"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}, "try again in 12s", 12.0),
        ({}, "Rate limit reached", 20.0),  # no hint at all: the default
        ({"retry-after": "0"}, "", 1.0),  # clamped up ...
        ({"x-ratelimit-reset-tokens": "380ms"}, "", 1.0),
        ({"x-ratelimit-reset-requests": "2m59.56s"}, "", 120.0),  # ... and down
        ({"retry-after": "86400"}, "", 120.0),
    ],
)
def test_every_retry_hint_format_is_read_and_clamped(headers, message, seconds):
    error = status_error(openai.RateLimitError, 429, message, headers)
    assert client_module._rate_limit_hint_s(error) == pytest.approx(seconds)


@pytest.mark.parametrize(
    "error",
    [
        status_error(openai.InternalServerError, 503, "upstream down"),
        openai.APITimeoutError(_httpx.Request("POST", "https://provider.example")),
        openai.APIConnectionError(request=_httpx.Request("POST", "https://provider.example")),
    ],
)
def test_a_server_error_timeout_or_lost_connection_cools_the_entry_for_15_seconds(clock, error):
    a, b = FakeOpenAI(error, "a is back"), FakeOpenAI("b1", "b2")
    client = pool(clock, a=a, b=b)
    client.complete(role="sql", messages=MESSAGES)
    clock.now += 14
    assert client.complete(role="sql", messages=MESSAGES).provider == "nvidia"
    clock.now += 1
    assert client.complete(role="sql", messages=MESSAGES).content == "a is back"


def test_a_rejected_key_parks_the_entry_for_an_hour_and_warns_once_without_the_key(clock, caplog):
    leaky = status_error(openai.AuthenticationError, 401, f"Incorrect API key provided: {GROQ_KEY}")
    a, b = FakeOpenAI(leaky, "a is back"), FakeOpenAI("b1", "b2")
    client = pool(clock, a=a, b=b)

    client.complete(role="sql", messages=MESSAGES)
    clock.now += 3599
    assert client.complete(role="sql", messages=MESSAGES).provider == "nvidia"
    assert len(a.requests) == 1
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "groq" in warnings[0] and "model-a" in warnings[0]
    assert GROQ_KEY not in caplog.text

    clock.now += 1
    assert client.complete(role="sql", messages=MESSAGES).content == "a is back"


def too_long():
    return status_error(openai.BadRequestError, 400, "context length exceeded")


def test_a_refused_request_costs_no_cooldown_and_is_not_asked_twice_for_one_question(clock):
    # A 400 is about this request, not the provider's health: the next question may use the
    # model at once, but this question must not replay the same refusal after the wait.
    a = FakeOpenAI(too_long(), "fine with the next question")
    b = FakeOpenAI(rate_limited({"retry-after": "8"}), "b answered")
    client = pool(clock, a=a, b=b)

    assert client.complete(role="sql", messages=MESSAGES).content == "b answered"
    assert clock.naps == [8.0] and len(a.requests) == 1

    assert client.complete(role="sql", messages=MESSAGES).content == "fine with the next question"


def test_a_request_every_model_refuses_is_not_blamed_on_busy_models(clock):
    a, b = FakeOpenAI(too_long()), FakeOpenAI(too_long())
    with pytest.raises(LLMUnavailable) as raised:
        pool(clock, a=a, b=b).complete(role="sql", messages=MESSAGES)
    assert "busy" not in str(raised.value) and "shorter" in str(raised.value)
    assert raised.value.retry_after_s is None  # waiting would not help
    assert clock.naps == [] and len(a.requests) == 1 and len(b.requests) == 1


# --- 2. token pacing ----------------------------------------------------------------------


def test_token_pacing_skips_an_entry_that_cannot_fit_the_request_until_its_reset(clock):
    left = {"x-ratelimit-remaining-tokens": "5000", "x-ratelimit-reset-tokens": "30s"}
    a, b = FakeOpenAI("a1", "a2", "a3", headers=left), FakeOpenAI("b1")
    client = pool(clock, a=a, b=b)
    big = [{"role": "user", "content": "x" * 20_000}]  # about 5,600 tokens with the reply

    assert client.complete(role="sql", messages=MESSAGES).content == "a1"
    assert client.complete(role="sql", messages=MESSAGES).content == "a2"  # ~600 tokens fits
    assert client.complete(role="sql", messages=big).content == "b1"  # certain refusal: skipped
    assert len(a.requests) == 2

    clock.now += 30  # the allowance has refilled, so the old number means nothing
    assert client.complete(role="sql", messages=big).content == "a3"


@pytest.mark.parametrize(
    "headers",
    [{}, {"x-ratelimit-remaining-tokens": "soon"}, {"x-ratelimit-remaining-tokens": "10"}],
)
def test_missing_or_odd_pacing_headers_change_nothing(clock, headers):
    a = FakeOpenAI("a1", "a2", headers=headers)
    client = pool(clock, a=a)
    client.complete(role="sql", messages=MESSAGES)
    assert client.complete(role="sql", messages=MESSAGES).content == "a2"


def test_the_real_sdk_hands_over_headers_the_way_the_fakes_pretend(clock):
    """The one test with a real openai.OpenAI (over an in-memory transport, so still no
    network): it keeps the fakes honest about the SDK's raw-response interface."""

    def provider(request):
        if b'"model-a"' in request.content:
            limited = {"error": {"message": "Rate limit reached"}}
            return _httpx.Response(429, headers={"x-ratelimit-reset-tokens": "7.66s"}, json=limited)
        nearly_spent = {"x-ratelimit-remaining-tokens": "100", "x-ratelimit-reset-tokens": "30s"}
        choice = {"index": 0, "finish_reason": "stop",
                  "message": {"role": "assistant", "content": "hi"}}
        body = {"id": "x", "object": "chat.completion", "created": 0, "model": "model-b",
                "choices": [choice]}
        return _httpx.Response(200, headers=nearly_spent, json=body)

    def real_client(pm):
        transport = _httpx.MockTransport(provider)
        return openai.OpenAI(base_url="https://provider.example/v1", api_key=pm.api_key,
                             max_retries=0, http_client=_httpx.Client(transport=transport))

    client = PoolClient(client_factory=real_client, clock=clock, sleep=clock.sleep)
    assert client.complete(role="narrate", messages=MESSAGES).content == "hi"
    # model-a: cooled by the 429's header. model-b: 100 tokens left cannot fit ~600.
    with pytest.raises(LLMUnavailable) as raised:
        client.complete(role="narrate", messages=MESSAGES)
    assert raised.value.retry_after_s == 8  # 7.66 s, rounded up


# --- 3. the bounded wait ------------------------------------------------------------------


def test_sql_waits_for_the_soonest_entry_when_everything_is_cooling_then_succeeds(clock):
    a = FakeOpenAI(rate_limited({"retry-after": "8"}), "second time lucky")
    b = FakeOpenAI(rate_limited({"retry-after": "90"}))
    told: list[float] = []
    client = pool(clock, a=a, b=b).with_options(on_wait=told.append)

    result = client.complete(role="sql", messages=MESSAGES)

    assert (result.provider, result.content) == ("groq", "second time lucky")
    assert clock.naps == [8.0] and told == [8.0]
    assert len(b.requests) == 1  # still cooling after the wait, so not asked again


def test_a_wait_longer_than_the_limit_is_refused_with_one_honest_sentence(clock):
    a = FakeOpenAI(rate_limited({"retry-after": "40"}))
    b = FakeOpenAI(rate_limited({"retry-after": "90"}))
    with pytest.raises(LLMUnavailable) as raised:
        pool(clock, a=a, b=b).complete(role="sql", messages=MESSAGES)
    assert str(raised.value) == (
        "All the free AI models are busy right now. Try again in about 40 seconds."
    )
    assert raised.value.retry_after_s == 40
    assert clock.naps == []


def test_the_seconds_are_rounded_up(clock):
    a = FakeOpenAI(rate_limited({"x-ratelimit-reset-tokens": "30.2s"}))
    with pytest.raises(LLMUnavailable, match="about 31 seconds") as raised:
        pool(clock, a=a, b=FakeOpenAI(rate_limited({"retry-after": "90"}))).complete(
            role="sql", messages=MESSAGES
        )
    assert raised.value.retry_after_s == 31


def test_the_wait_limit_comes_from_settings(clock, monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, llm_max_wait_s=5))
    a, b = FakeOpenAI(rate_limited({"retry-after": "8"})), FakeOpenAI(rate_limited())
    with pytest.raises(LLMUnavailable):
        pool(clock, a=a, b=b).complete(role="sql", messages=MESSAGES)
    assert clock.naps == []


def test_a_call_waits_at_most_twice(clock):
    a = FakeOpenAI(*[rate_limited({"retry-after": "5"})] * 3)
    b = FakeOpenAI(rate_limited({"retry-after": "90"}))
    with pytest.raises(LLMUnavailable) as raised:
        pool(clock, a=a, b=b).complete(role="sql", messages=MESSAGES)
    assert clock.naps == [5.0, 5.0] and len(a.requests) == 3
    assert raised.value.retry_after_s == 5


def test_the_waits_of_one_call_never_add_up_to_more_than_the_limit(clock):
    a = FakeOpenAI(*[rate_limited({"retry-after": "20"})] * 2)
    b = FakeOpenAI(rate_limited({"retry-after": "90"}))
    with pytest.raises(LLMUnavailable) as raised:
        pool(clock, a=a, b=b).complete(role="sql", messages=MESSAGES)
    assert clock.naps == [20.0]  # a second 20 s nap would make 40 s: over the 25 s limit
    assert raised.value.retry_after_s == 20


@pytest.mark.parametrize("role", ["crosscheck", "narrate"])
def test_crosscheck_and_narrate_never_sleep(clock, role):
    a = FakeOpenAI(rate_limited({"retry-after": "2"}))
    b = FakeOpenAI(rate_limited({"retry-after": "3"}))
    told: list[float] = []
    with pytest.raises(LLMUnavailable) as raised:
        pool(clock, a=a, b=b).with_options(on_wait=told.append).complete(
            role=role, messages=MESSAGES
        )
    assert clock.naps == [] and told == []
    assert raised.value.retry_after_s == 5  # never promise less than 5 seconds
    assert "about 5 seconds" in str(raised.value)


# --- 4. per-call options ------------------------------------------------------------------


def test_a_failing_on_wait_callback_never_breaks_the_call(clock):
    a, b = FakeOpenAI(rate_limited({"retry-after": "8"}), "answered"), FakeOpenAI(rate_limited())

    def broken(seconds: float) -> None:
        raise RuntimeError("the browser went away")

    client = pool(clock, a=a, b=b).with_options(on_wait=broken)
    assert client.complete(role="sql", messages=MESSAGES).content == "answered"


def test_avoid_model_is_honoured_and_the_view_shares_the_pools_state(clock):
    a, b = FakeOpenAI("a1"), FakeOpenAI(rate_limited({"retry-after": "60"}))
    client = pool(clock, a=a, b=b)
    with pytest.raises(LLMUnavailable):
        client.with_options(avoid_model="model-a").complete(role="crosscheck", messages=MESSAGES)
    assert a.requests == []  # never checks an answer with the model that wrote it

    # the view's 429 cooled model-b for the pool itself: same state, one request in total
    assert client.complete(role="crosscheck", messages=MESSAGES).content == "a1"
    assert len(b.requests) == 1


def test_avoid_model_also_skips_the_same_model_under_another_providers_id(clock, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("LLM_CROSSCHECK_CHAIN", "openrouter:vendor/model-a:free,nvidia:model-b")
    a, b = FakeOpenAI(), FakeOpenAI("b1")
    view = pool(clock, a=a, b=b).with_options(avoid_model="model-a")
    assert view.complete(role="crosscheck", messages=MESSAGES).provider == "nvidia"


def test_avoid_model_does_not_reuse_the_avoided_models_cached_answer(clock, monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_cache_dir=str(tmp_path))
    )
    client = pool(clock, a=FakeOpenAI("from a"), b=FakeOpenAI("from b"))
    assert client.complete(role="crosscheck", messages=MESSAGES).content == "from a"
    view = client.with_options(avoid_model="model-a")
    assert view.complete(role="crosscheck", messages=MESSAGES).content == "from b"


def test_avoiding_the_only_model_is_an_honest_error_not_a_crash(clock, monkeypatch):
    monkeypatch.setenv("LLM_CROSSCHECK_CHAIN", "groq:model-a")
    with pytest.raises(LLMUnavailable, match="second AI model"):
        pool(clock).with_options(avoid_model="model-a").complete(
            role="crosscheck", messages=MESSAGES
        )


# --- threads, the cache, secrets ----------------------------------------------------------


def test_threads_hitting_the_pool_together_do_not_corrupt_its_state(clock):
    threads, calls_each = 8, 25
    a = FakeOpenAI(*[rate_limited()] * threads)
    b = FakeOpenAI(*["ok"] * (threads * calls_each))
    client = pool(clock, a=a, b=b)
    answers: list[str] = []
    crashes: list[BaseException] = []
    start = threading.Barrier(threads)

    def worker() -> None:
        try:
            start.wait()
            for _ in range(calls_each):
                answers.append(client.complete(role="sql", messages=MESSAGES).provider)
        except BaseException as crash:  # noqa: BLE001 - reported by the assertion below
            crashes.append(crash)

    running = [threading.Thread(target=worker) for _ in range(threads)]
    for t in running:
        t.start()
    for t in running:
        t.join()

    assert crashes == []
    assert answers == ["nvidia"] * (threads * calls_each)
    assert 1 <= len(a.requests) <= threads  # at most one probe each before the cooldown landed
    health = client_module._health
    assert set(health) == {("groq", "model-a")}  # model-b sent no headers and never failed
    assert health[("groq", "model-a")].cooling_until == clock.now + 20


def test_the_disk_cache_still_hits_with_the_key_format_unchanged(clock, monkeypatch, tmp_path):
    """An evaluation run depends on cache files written before this change, so the key is
    spelled out here by hand: sha256 of {"model", "messages", "schema"}, sorted keys."""
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_cache_dir=str(tmp_path))
    )
    schema = {"title": "Thing", "type": "object"}
    key = json.dumps({"model": "model-b", "messages": MESSAGES, "schema": schema}, sort_keys=True)
    saved = {"content": '{"a": 1}', "provider": "nvidia", "model": "model-b"}
    (tmp_path / f"{hashlib.sha256(key.encode()).hexdigest()}.json").write_text(json.dumps(saved))

    untouched = FakeOpenAI()
    hit = pool(clock, a=untouched, b=untouched).complete(
        role="sql", messages=MESSAGES, json_schema=schema
    )
    assert hit.cached is True and hit.content == '{"a": 1}' and untouched.requests == []


def test_a_cached_answer_is_served_even_while_every_model_is_cooling(clock, monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_cache_dir=str(tmp_path))
    )
    client = pool(clock, a=FakeOpenAI("kept", rate_limited()), b=FakeOpenAI(rate_limited()))
    client.complete(role="narrate", messages=MESSAGES)
    with pytest.raises(LLMUnavailable):
        client.complete(role="narrate", messages=[{"role": "user", "content": "another"}])
    assert client.complete(role="narrate", messages=MESSAGES).cached is True


def test_no_api_key_reaches_an_exception_or_a_log_record(clock, caplog):
    caplog.set_level(logging.DEBUG)
    a = FakeOpenAI(status_error(openai.AuthenticationError, 401, f"Bad key: {GROQ_KEY}"))
    b = FakeOpenAI(
        status_error(
            openai.RateLimitError, 429, f"Bearer {NVIDIA_KEY} is limited, try again in 3s",
            {"retry-after": f"{NVIDIA_KEY}"},
        ),
        ValueError(f"unreadable reply near {NVIDIA_KEY}"),
        rate_limited({"retry-after": "60"}),
    )
    with pytest.raises(LLMUnavailable) as raised:
        pool(clock, a=a, b=b).complete(role="sql", messages=MESSAGES)

    # The 3 s hint was read out of the leaky sentence, yet none of that sentence was kept.
    assert clock.naps == [3.0, 15.0]
    logged = " ".join(r.getMessage() for r in caplog.records) + caplog.text
    for secret in (GROQ_KEY, NVIDIA_KEY):
        assert secret not in str(raised.value) and secret not in repr(raised.value)
        assert secret not in logged
    assert raised.value.__context__ is None  # no provider error rides along into a traceback
    assert "groq" in logged and "model-a" in logged  # the operator still learns who failed
    for detail in ("groq", "nvidia", "model-", "401", "429"):
        assert detail not in str(raised.value)


def test_the_other_sentences_are_unchanged_and_carry_no_retry_hint(clock, monkeypatch):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_calls_per_day=0)
    )
    with pytest.raises(LLMUnavailable, match="daily limit") as spent:
        pool(clock, a=FakeOpenAI("never sent")).complete(role="sql", messages=MESSAGES)
    assert spent.value.retry_after_s is None

    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("NVIDIA_API_KEY")
    with pytest.raises(LLMUnavailable, match=r"\.env") as unset:
        pool(clock).complete(role="sql", messages=MESSAGES)
    assert unset.value.retry_after_s is None
