"""Starter questions built from the schema by template, so every one is answerable."""

from __future__ import annotations

from app.contracts import Catalog


def suggest_questions(catalog: Catalog, limit: int = 6) -> list[str]:
    """Deterministic templates over roles/types (measure by category, trend over a date,
    a cross-file question when an active relationship exists, a glossary metric when its
    roles are present). No LLM call."""
    raise NotImplementedError
