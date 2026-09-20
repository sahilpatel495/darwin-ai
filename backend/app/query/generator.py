"""Question -> structured plan + SQL. The model translates intent; it never computes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts import ModelPayload, ResolvedMetric
from app.llm.client import LLMClient, Role
from app.sessions import Turn


class Generation(BaseModel):
    status: Literal["ok", "clarify", "unanswerable", "meta"]
    interpretation: str = ""
    plan: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    sql: str = ""
    clarify_question: str = ""
    clarify_options: list[str] = Field(default_factory=list)  # "table.column" refs
    missing: str = ""  # for "unanswerable": which data would be needed
    metrics_used: list[str] = Field(default_factory=list)  # glossary keys


class RepairContext(BaseModel):
    previous_sql: str
    problem: str  # DuckDB error text, guard rejection, "returned no rows", or fan-out note


def generate(
    llm: LLMClient,
    *,
    role: Role,
    question: str,
    schema_context: str,
    metric_context: str,
    history: list[Turn],
    clarification: dict[str, str] | None,
    repair: RepairContext | None = None,
) -> tuple[Generation, ModelPayload]:
    """One structured call. The prompt budget is ~2K tokens: system rules + 6 short DuckDB
    few-shots + schema_context + metric_context + last 3 turns + the question.
    schema_context/metric_context come from app.catalog.prompt_context and are the ONLY data
    description allowed in the prompt. Invalid JSON gets one retry, then raises ValueError."""
    raise NotImplementedError
