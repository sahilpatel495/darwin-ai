"""Detect same-schema tables (jan.csv, feb.csv) and expose them as one view."""

from __future__ import annotations

import duckdb

from app.contracts import TableProfile, UnionView


def detect_unions(tables: list[TableProfile], existing: list[UnionView]) -> list[UnionView]:
    """Group base tables whose normalised column names and types match exactly (>= 2 tables).

    view_name is the longest common prefix of the table names plus "_all" (fallback
    "combined_<n>"). New unions are "active"; a union the user rejected stays rejected.
    """
    raise NotImplementedError


def create_union_views(
    conn: duckdb.DuckDBPyConnection, unions: list[UnionView], tables: list[TableProfile]
) -> list[TableProfile]:
    """(Re)create one view per active union: UNION ALL BY NAME of members plus a
    `source_file` text column; drop views of rejected unions. Returns a TableProfile
    (is_view=True) per active view so the model can see it."""
    raise NotImplementedError
