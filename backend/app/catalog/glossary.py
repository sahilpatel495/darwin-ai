"""HR semantic layer: vetted metric definitions and deterministic ambiguity detection."""

from __future__ import annotations

from app.contracts import Catalog, Clarification, Metric, ResolvedMetric

DEFAULT_GLOSSARY: list[Metric] = []  # seeded by the data-engine agent, see docs/PLAN.md

# term -> roles it could mean. "salary" is the canonical example.
AMBIGUOUS_TERMS: dict[str, list[str]] = {}


def match_metrics(question: str, catalog: Catalog) -> list[ResolvedMetric]:
    """Metrics whose name or a synonym appears in the question (case-insensitive, word
    boundaries), each bound to this session's columns via ColumnProfile.role. A metric whose
    required roles are absent is still returned, with `missing_roles` set and sql_hint ""."""
    raise NotImplementedError


def find_ambiguity(
    question: str, catalog: Catalog, clarification: dict[str, str] | None
) -> Clarification | None:
    """Return clarify options when an AMBIGUOUS_TERMS term appears in the question, two or
    more of its candidate roles exist in the data, the question names none of those columns
    or roles explicitly, and `clarification` does not already resolve the term."""
    raise NotImplementedError
