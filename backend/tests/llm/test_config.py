"""config.chain(): which chain entries become usable provider/model pairs.

Failover behaviour (cooldowns, pacing, retry hints) lives in test_client.py and
test_pool_resilience.py. This file is only about reading the chain out of the environment,
where the question is which entries are silently dropped: a dropped entry is a fallback the
operator believes they configured and never gets.
"""

from __future__ import annotations

import pytest
from app import config


@pytest.fixture
def gateway(monkeypatch):
    """A one-entry "custom:" chain pointed at a customer's gateway. PROVIDERS reads LLM_BASE_URL
    once, at import, so the entry itself is patched rather than the variable."""
    monkeypatch.setitem(config.PROVIDERS, "custom", ("https://gateway.internal/v1", "LLM_API_KEY"))
    monkeypatch.setenv("LLM_SQL_CHAIN", "custom:internal-sql-model")


def test_a_custom_gateway_resolves_without_a_key(monkeypatch, gateway):
    """Customer gateways and self-hosted vLLM servers usually authenticate by network. Skipping
    them for an empty key left the operator with a chain entry that could never run."""
    monkeypatch.setenv("LLM_API_KEY", "")

    (entry,) = config.chain("sql")

    assert (entry.provider, entry.model) == ("custom", "internal-sql-model")
    assert entry.base_url == "https://gateway.internal/v1"
    assert entry.api_key == "none"  # the OpenAI client demands a string; this one says nothing


def test_a_whitespace_only_key_counts_as_unset(monkeypatch, gateway):
    """Hosting dashboards and `cp .env.example .env` both produce blank values."""
    monkeypatch.setenv("LLM_API_KEY", "  \t ")
    assert config.chain("sql")[0].api_key == "none"

    monkeypatch.setenv("LLM_SQL_CHAIN", "groq:some-model")
    monkeypatch.setenv("GROQ_API_KEY", "  \t ")
    assert config.chain("sql") == [], "a hosted provider with a blank key would only 401"


def test_a_key_that_is_set_is_used_as_it_is(monkeypatch, gateway):
    monkeypatch.setenv("LLM_API_KEY", "gateway-token")
    assert config.chain("sql")[0].api_key == "gateway-token"


def test_a_custom_entry_without_a_base_url_is_still_skipped(monkeypatch):
    """The placeholder key must not make `custom:` resolve to nowhere: LLM_BASE_URL is what
    says the operator meant it."""
    monkeypatch.setitem(config.PROVIDERS, "custom", ("", "LLM_API_KEY"))
    monkeypatch.setenv("LLM_SQL_CHAIN", "custom:internal-sql-model")
    monkeypatch.setenv("LLM_API_KEY", "")

    assert config.chain("sql") == []
