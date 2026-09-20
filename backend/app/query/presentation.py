"""Turn a result into what the user sees: display strings and a chart spec. Rules only."""

from __future__ import annotations

from typing import Any

from app.contracts import Catalog, ChartSpec, ResultTable
from app.query.executor import ExecResult
from app.query.guard import GuardedQuery

ValueKind = str  # "currency" | "percent" | "integer" | "decimal" | "date" | "text"


def column_kinds(result: ExecResult, query: GuardedQuery, catalog: Catalog) -> list[ValueKind]:
    """currency when a source column is currency and the aggregate is not COUNT; percent when
    the alias ends with _pct (prompt convention); else from the DuckDB type."""
    raise NotImplementedError


def to_display(value: Any, kind: ValueKind) -> str:
    """Indian formatting: 1234567 -> "12,34,567"; currency -> "₹12.35 L" / "₹1.20 Cr" from
    1 lakh up, else "₹45,000"; percent -> "12.5%"; dates -> "04 Apr 2025"; None -> "—"."""
    raise NotImplementedError


def build_table(result: ExecResult, kinds: list[ValueKind]) -> ResultTable: 
    raise NotImplementedError


def choose_chart(table: ResultTable, kinds: list[ValueKind], question: str) -> ChartSpec:
    """1x1 -> kpi; date + measure(s) -> line; category + measure: <= 12 groups -> sorted bar,
    more -> top 12 bar with a note; 2 categories + measure -> grouped_bar; 2 measures ->
    scatter; otherwise table."""
    raise NotImplementedError
