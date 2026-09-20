"""Opt-in check against a real model. It spends free-tier tokens, so it is skipped unless asked:

    LIVE_LLM=1 uv run --env-file .env pytest backend/tests/llm/test_live_smoke.py -q -s
"""

from __future__ import annotations

import dataclasses
import os

import pytest
from app import config
from app.catalog.prompt_context import build_schema_context
from app.llm import client as client_module
from app.llm.client import PoolClient
from app.query.generator import generate

from tests.fixtures import make_session

pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_LLM") != "1", reason="spends real free-tier tokens; set LIVE_LLM=1"
)


def test_a_real_model_writes_sql_that_runs_on_the_fixture(monkeypatch):
    # The daily budget is the hard stop: whatever goes wrong, at most 4 requests leave here.
    tight = dataclasses.replace(config.settings, llm_calls_per_day=4, llm_cache_dir="")
    monkeypatch.setattr(config, "settings", tight)
    monkeypatch.setattr(client_module, "_budget", {"day": "", "calls": 0})
    session = make_session()

    generation, payload = generate(
        PoolClient(), role="sql", question="total gross pay by department",
        schema_context=build_schema_context(session.catalog), metric_context="",
        history=[], clarification=None,
    )

    print(f"\n{payload.provider} {payload.model} {payload.latency_ms} ms\n{generation.sql}")
    assert generation.status == "ok", generation
    rows = session.cursor().execute(generation.sql).fetchall()
    assert len(rows) == 3  # Engineering, HR, Sales
