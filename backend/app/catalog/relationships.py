"""Detect join keys across tables by value overlap, with cardinality."""

from __future__ import annotations

import duckdb

from app.contracts import Relationship, TableProfile


def detect_relationships(
    conn: duckdb.DuckDBPyConnection, tables: list[TableProfile], existing: list[Relationship]
) -> list[Relationship]:
    """Return relationships for the current tables, preserving user decisions in `existing`.

    Candidates: column pairs across different base tables (not views) with compatible types
    where both are identifier-like or share a role or a similar name. Overlap is measured in
    DuckDB on distinct non-null values, both directions. Keep pairs with
    max(match_left, match_right) >= 0.5. status is "active" when min(match) >= 0.8, else
    "suggested"; a pair the user already set to active/rejected keeps that status.
    Cardinality comes from ColumnProfile.is_unique on each side. ids are stable:
    f"{left_table}.{left_column}->{right_table}.{right_column}" with tables sorted.
    """
    raise NotImplementedError
