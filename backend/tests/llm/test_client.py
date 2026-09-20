"""PoolClient: failover, caching, output cleaning, the daily budget. No network, ever."""

from __future__ import annotations

import dataclasses
import logging
from types import SimpleNamespace

import openai
import pytest
from app import config
from app.llm import client as client_module
from app.llm.client import LLMUnavailable, PoolClient

try:  # the locked openai SDK builds its errors on httpx2; older ones use httpx
    import httpx2 as _httpx
except ImportError:  # pragma: no cover
    import httpx as _httpx

GROQ_KEY = "gsk-test-SECRET-groq"
NVIDIA_KEY = "nvapi-test-SECRET-nvidia"
MESSAGES = [{"role": "user", "content": "Reply in JSON."}]
SCHEMA = {"title": "Thing", "type": "object", "properties": {"a": {"type": "integer"}}}


class FakeOpenAI:
    """Looks like openai.OpenAI for the one call we make (the raw-response form, which is how
    the pool reads rate-limit headers); plays back replies or raises. `headers` ride along
    with every successful reply."""

    def __init__(self, *script: str | list | None | Exception, headers: dict | None = None):
        self.script = list(script)
        self.headers = headers or {}
        self.requests: list[dict] = []
        raw = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(with_raw_response=raw))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])
        return SimpleNamespace(headers=self.headers, parse=lambda: reply)


def status_error(cls, status: int, message: str, headers: dict | None = None, **more_body):
    """Shaped like the SDK's own errors: `body` is the provider's "error" object, and the
    exception text is the status plus that whole object."""
    request = _httpx.Request("POST", "https://provider.example/v1/chat/completions")
    response = _httpx.Response(status, headers=headers or {}, request=request)
    body = {"message": message, **more_body}
    return cls(f"Error code: {status} - {body}", response=response, body=body)


def rate_limited(headers: dict | None = None):
    return status_error(openai.RateLimitError, 429, "Rate limit reached", headers)


@pytest.fixture(autouse=True)
def two_providers(monkeypatch):
    """A two-entry chain through the real app.config.chain, a fresh budget and no cooldowns
    left over from the previous test (both are process-wide on purpose)."""
    monkeypatch.setenv("LLM_SQL_CHAIN", "groq:model-a,nvidia:model-b")
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, llm_cache_dir=""))
    monkeypatch.setattr(client_module, "_budget", {"day": "", "calls": 0})
    monkeypatch.setattr(client_module, "_health", {})


def pool(**fakes: FakeOpenAI) -> PoolClient:
    """fakes are keyed a/b for model-a/model-b. Sleeping is a no-op: waits are tested with a
    fake clock in test_pool_resilience.py."""
    return PoolClient(
        client_factory=lambda pm: fakes[pm.model.removeprefix("model-")], sleep=lambda s: None
    )


def test_rate_limit_on_the_first_provider_fails_over_and_the_result_names_the_second():
    a, b = FakeOpenAI(rate_limited()), FakeOpenAI("hello")
    result = pool(a=a, b=b).complete(role="sql", messages=MESSAGES)
    assert (result.content, result.provider, result.model) == ("hello", "nvidia", "model-b")
    assert result.cached is False
    assert len(a.requests) == 1 and len(b.requests) == 1


@pytest.mark.parametrize(
    "error",
    [
        status_error(openai.InternalServerError, 503, "upstream down"),
        openai.APITimeoutError(_httpx.Request("POST", "https://provider.example")),
        openai.APIConnectionError(request=_httpx.Request("POST", "https://provider.example")),
        status_error(openai.NotFoundError, 404, "model decommissioned"),
    ],
)
def test_server_errors_timeouts_connection_errors_and_retired_models_fail_over(error):
    result = pool(a=FakeOpenAI(error), b=FakeOpenAI("ok")).complete(role="sql", messages=MESSAGES)
    assert result.provider == "nvidia"


def test_every_request_is_deterministic_and_carries_the_model():
    a = FakeOpenAI("hi")
    pool(a=a).complete(role="sql", messages=MESSAGES)
    assert a.requests[0]["temperature"] == 0
    assert a.requests[0]["model"] == "model-a"
    assert a.requests[0]["messages"] == MESSAGES
    assert "response_format" not in a.requests[0]


def test_a_schema_is_requested_as_strict_json_schema():
    a = FakeOpenAI('{"a": 1}')
    pool(a=a).complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    wanted = a.requests[0]["response_format"]
    assert wanted["type"] == "json_schema"
    assert wanted["json_schema"]["strict"] is True and wanted["json_schema"]["schema"] == SCHEMA


def test_a_400_about_response_format_steps_down_on_the_same_provider_and_is_remembered():
    complaint = "This model does not support response format `json_schema`"
    a = FakeOpenAI(
        status_error(openai.BadRequestError, 400, complaint),
        status_error(openai.BadRequestError, 400, "response_format json_object is not supported"),
        '{"a": 1}',
        '{"a": 2}',
    )
    b = FakeOpenAI()
    client = pool(a=a, b=b)
    result = client.complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert result.provider == "groq" and result.content == '{"a": 1}'
    assert [r.get("response_format", {}).get("type") for r in a.requests] == [
        "json_schema", "json_object", None,
    ]
    client.complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert "response_format" not in a.requests[3]  # no wasted 400s the second time
    assert b.requests == []


def test_an_unrelated_400_moves_to_the_next_provider():
    a = FakeOpenAI(status_error(openai.BadRequestError, 400, "context length exceeded"))
    b = FakeOpenAI('{"a": 1}')
    result = pool(a=a, b=b).complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert result.provider == "nvidia" and len(a.requests) == 1


def test_a_400_that_only_quotes_the_models_failed_output_does_not_step_the_format_down():
    # Groq's json_validate_failed echoes what the model wrote, and models echo our prompt's
    # "JSON object". That is a bad generation, not an unsupported format: fail over, and keep
    # strict JSON for this provider's next question.
    a = FakeOpenAI(
        status_error(
            openai.BadRequestError, 400, "Failed to generate JSON. Please adjust your prompt.",
            code="json_validate_failed", failed_generation="I will reply with one JSON object",
        ),
        '{"a": 1}',
    )
    b = FakeOpenAI('{"a": 2}')
    client = pool(a=a, b=b)
    assert client.complete(role="sql", messages=MESSAGES, json_schema=SCHEMA).provider == "nvidia"
    assert len(a.requests) == 1
    client.complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert a.requests[1]["response_format"]["type"] == "json_schema"


def test_a_provider_that_breaks_in_an_unexpected_way_fails_over_without_quoting_it(caplog):
    # A 200 with a body that is not JSON leaves the SDK as a bare JSONDecodeError.
    caplog.set_level(logging.INFO)  # routine failovers are info, not warnings
    broken = ValueError(f"Expecting value near Bearer {GROQ_KEY}")
    result = pool(a=FakeOpenAI(broken), b=FakeOpenAI("ok")).complete(role="sql", messages=MESSAGES)
    assert result.provider == "nvidia"
    assert "could not be read (ValueError)" in caplog.text and GROQ_KEY not in caplog.text


def test_a_reply_whose_content_is_not_text_counts_as_empty_and_fails_over():
    parts = [{"type": "text", "text": "hello"}]
    result = pool(a=FakeOpenAI(parts), b=FakeOpenAI("real")).complete(role="sql", messages=MESSAGES)
    assert result.provider == "nvidia"


def test_think_blocks_are_stripped():
    a = FakeOpenAI("\n<think>\nlet me reason {not json}\n</think>\nThe answer is here.")
    assert pool(a=a).complete(role="sql", messages=MESSAGES).content == "The answer is here."


def test_a_think_tag_inside_the_json_answer_does_not_eat_the_answer():
    reply = '{"a": 1, "note": "the question asked what <think> means"}'
    result = pool(a=FakeOpenAI(reply)).complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert result.content == reply


def test_json_is_extracted_from_prose_when_a_schema_was_requested():
    reply = 'Sure! Here you go:\n```json\n{"a": {"b": [1, 2]}, "c": "x}"}\n```\nHope that helps.'
    result = pool(a=FakeOpenAI(reply)).complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert result.content == '{"a": {"b": [1, 2]}, "c": "x}"}'


def test_prose_is_left_alone_when_no_schema_was_requested():
    reply = "Totals use {curly} braces sometimes."
    assert pool(a=FakeOpenAI(reply)).complete(role="sql", messages=MESSAGES).content == reply


@pytest.mark.parametrize("empty", [None, "", "<think>only thinking, cut off"])
def test_an_empty_reply_counts_as_a_failure_and_fails_over(empty):
    result = pool(a=FakeOpenAI(empty), b=FakeOpenAI("real")).complete(role="sql", messages=MESSAGES)
    assert result.provider == "nvidia"


def test_cache_hit_makes_no_call(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_cache_dir=str(tmp_path))
    )
    a = FakeOpenAI('{"a": 1}')
    first = pool(a=a).complete(role="sql", messages=MESSAGES, json_schema=SCHEMA)
    assert first.cached is False and len(list(tmp_path.glob("*.json"))) == 1

    untouched = FakeOpenAI()
    again = pool(a=untouched, b=untouched).complete(
        role="sql", messages=MESSAGES, json_schema=SCHEMA
    )
    assert again.cached is True and again.content == '{"a": 1}'
    assert (again.provider, again.model) == ("groq", "model-a")
    assert untouched.requests == []

    other = FakeOpenAI("fresh")
    different = [{"role": "user", "content": "Another prompt, in JSON."}]
    assert pool(a=other).complete(role="sql", messages=different).cached is False


def test_cache_files_never_contain_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_cache_dir=str(tmp_path))
    )
    pool(a=FakeOpenAI("hi")).complete(role="sql", messages=MESSAGES)
    text = "".join(p.read_text("utf-8") for p in tmp_path.iterdir())
    assert GROQ_KEY not in text and NVIDIA_KEY not in text


def test_budget_exceeded_raises_before_any_call(monkeypatch):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_calls_per_day=2)
    )
    a = FakeOpenAI("one", "two", "three")
    client = pool(a=a)
    client.complete(role="sql", messages=MESSAGES)
    client.complete(role="sql", messages=MESSAGES)
    with pytest.raises(LLMUnavailable, match="limit"):
        client.complete(role="sql", messages=MESSAGES)
    assert len(a.requests) == 2


def test_the_budget_is_shared_by_every_client_and_resets_on_a_new_day(monkeypatch):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_calls_per_day=1)
    )
    pool(a=FakeOpenAI("one")).complete(role="sql", messages=MESSAGES)
    with pytest.raises(LLMUnavailable):
        pool(a=FakeOpenAI("two")).complete(role="sql", messages=MESSAGES)
    client_module._budget["day"] = "2000-01-01"  # yesterday, as far as the counter knows
    assert pool(a=FakeOpenAI("three")).complete(role="sql", messages=MESSAGES).content == "three"


def test_all_providers_failing_tells_the_user_nothing_about_providers_and_the_log_everything(caplog):
    caplog.set_level(logging.INFO)
    leaky = status_error(openai.AuthenticationError, 401, f"Incorrect API key provided: {GROQ_KEY}")
    down = status_error(openai.InternalServerError, 502, "bad gateway")
    a, b = FakeOpenAI(leaky), FakeOpenAI(down)
    with pytest.raises(LLMUnavailable) as raised:
        pool(a=a, b=b).complete(role="sql", messages=MESSAGES)
    text = str(raised.value)
    assert text.startswith("All the free AI models are busy right now.")
    for detail in ("groq", "nvidia", "model-a", "model-b", "401", "502"):
        assert detail not in text and detail in caplog.text  # the operator still gets the reasons
    for secret in (GROQ_KEY, NVIDIA_KEY):
        assert secret not in text and secret not in caplog.text


def test_no_configured_provider_says_what_to_do(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("NVIDIA_API_KEY")
    with pytest.raises(LLMUnavailable, match="API key"):
        pool().complete(role="sql", messages=MESSAGES)


# Cooldowns, retry hints, token pacing and the bounded wait: see test_pool_resilience.py.


@pytest.mark.parametrize(
    ("chain", "extra"),
    [
        ("groq:openai/gpt-oss-120b", {"reasoning_effort": "low"}),
        ("groq:qwen/qwen3.8-27b", {"reasoning_format": "hidden"}),
        ("openrouter:qwen/qwen3.8-27b:free", {"reasoning": {"exclude": True}}),
        ("nvidia:deepseek-ai/deepseek-v4-flash-0731", None),
    ],
)
def test_reasoning_is_kept_out_of_the_reply_per_model(monkeypatch, chain, extra):
    monkeypatch.setenv("LLM_SQL_CHAIN", chain)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    fake = FakeOpenAI("hi")
    PoolClient(client_factory=lambda pm: fake).complete(role="sql", messages=MESSAGES)
    assert fake.requests[0].get("extra_body") == extra


def test_real_clients_use_a_30_second_timeout_and_leave_retries_to_the_pool(monkeypatch):
    monkeypatch.setenv("LLM_SQL_CHAIN", "groq:model-a")
    real = PoolClient()._client(config.chain("sql")[0])
    assert isinstance(real, openai.OpenAI)
    assert real.max_retries == 0 and real.timeout == 30


def test_a_cache_that_cannot_be_written_never_costs_the_user_their_answer(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("a file where the cache folder should be")
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, llm_cache_dir=str(blocker))
    )
    assert pool(a=FakeOpenAI("still answered")).complete(role="sql", messages=MESSAGES).content
