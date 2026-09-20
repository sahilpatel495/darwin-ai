"""Allow-list SQL guard. Deny-lists were bypassed twice in the wild; we list what is allowed."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts import Catalog


class GuardError(ValueError):
    def __init__(self, code: str, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.code = code  # parse | multi | not_select | write | table_function | qualified |
        self.message = message  # unknown_table | unknown_column | function
        self.suggestion = suggestion  # e.g. "Did you mean exit_reason?"


@dataclass
class JoinRef:
    left_table: str
    left_column: str
    right_table: str
    right_column: str


@dataclass
class GuardedQuery:
    sql: str  # re-rendered by sqlglot in the duckdb dialect
    tables: list[str] = field(default_factory=list)  # real catalog tables/views referenced
    columns: list[tuple[str, str]] = field(default_factory=list)  # (table, column) resolved
    joins: list[JoinRef] = field(default_factory=list)  # equality joins between real tables
    aggregated: list[tuple[str, str, str]] = field(default_factory=list)  # (func, table, column)


def validate_sql(sql: str, catalog: Catalog) -> GuardedQuery:
    """Parse as DuckDB; exactly one statement; Select or set operation only; no write/command
    nodes; no table functions (generate_series allowed); no catalog/schema-qualified names;
    every real table in the catalog (CTEs resolved via scopes); deny-listed functions
    rejected; every column resolved against the catalog, unknown ones raise unknown_column
    with a difflib closest-match suggestion. Raises GuardError."""
    raise NotImplementedError
