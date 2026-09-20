"""Words around the numbers. The model copies pre-formatted strings; it never formats,
rounds or computes, and it never sees PII values."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts import ModelPayload, ResultTable
from app.llm.client import LLMClient


class Narration(BaseModel):
    text: str
    reading: str = ""  # one sentence describing what the SQL does, in plain English
    followups: list[str] = Field(default_factory=list)


def tokenise_pii(table: ResultTable, pii_columns: set[str]) -> tuple[ResultTable, dict[str, str]]:
    """Replace every value in PII columns with ⟦P1⟧, ⟦P2⟧... (same value -> same token).
    Returns the masked table and token -> original mapping."""
    raise NotImplementedError


def rehydrate(text: str, mapping: dict[str, str]) -> str:
    raise NotImplementedError


def ungrounded_numbers(text: str, table: ResultTable, question: str) -> list[str]:
    """Numeric tokens in `text` that are not a display string, a raw result value (any
    common rounding), the row count, or a number present in the question."""
    raise NotImplementedError


def template_answer(question: str, table: ResultTable) -> str:
    """Deterministic fallback sentence built only from display strings."""
    raise NotImplementedError


def narrate(
    llm: LLMClient, *, question: str, sql: str, table: ResultTable, caveats: list[str],
    pii_columns: set[str],
) -> tuple[Narration, ModelPayload, bool]:
    """tokenise -> one LLM call (first 30 rows, display strings only) -> grounding check ->
    one regeneration -> template fallback. Returns (narration, payload, used_fallback).
    A mangled or invented PII token also triggers the fallback."""
    raise NotImplementedError
