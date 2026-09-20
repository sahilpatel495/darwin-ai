"""Run guarded SQL with a timeout and a row cap."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import duckdb


class QueryTimeout(RuntimeError): ...


class QueryError(RuntimeError): ...


@dataclass
class ExecResult:
    columns: list[str]
    duck_types: list[str]  # DuckDB type names per column, e.g. "DOUBLE", "DATE", "VARCHAR"
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0


def execute(
    cursor: duckdb.DuckDBPyConnection, sql: str, *, timeout_s: float = 10, row_cap: int = 5000
) -> ExecResult:
    """threading.Timer(timeout_s, cursor.interrupt) -> QueryTimeout; fetchmany(row_cap + 1) to
    detect truncation; any duckdb.Error -> QueryError with the engine's message."""
    raise NotImplementedError
