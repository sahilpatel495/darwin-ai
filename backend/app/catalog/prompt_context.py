"""The single choke point for what a model is allowed to know about the data.

Why this exists: the privacy guarantee ("your rows never reach the model") is only
testable if exactly one function turns a Catalog into prompt text. Nothing else in
the codebase may serialise table contents into a prompt. Inputs are profiles
(statistics), never DataFrames or query results.

What can appear: table and column names, types, roles, null share, numeric/date
ranges, and the true distinct values of non-PII columns with <= 30 distinct values
(the model needs real filter literals such as "Bengaluru"), each at most 40 characters.
PII columns expose a name and a kind, nothing else.
"""

from __future__ import annotations

import json

from app.contracts import Catalog, ColumnProfile, ResolvedMetric, TableProfile

MAX_COLUMNS_PER_TABLE = 60  # wider tables list the remaining column names only
MAX_VALUES = 30
MAX_VALUE_CHARS = 40


def _column_line(col: ColumnProfile) -> str:
    tags = []
    if col.is_identifier:
        tags.append("id")
    if col.is_unique:
        tags.append("unique")
    if col.role:
        tags.append(f"role:{col.role}")
    head = f"  {col.name} {col.type}" + (f" [{', '.join(tags)}]" if tags else "")

    if col.pii:
        return f"{head} [PII:{col.pii}, values hidden]"

    parts = []
    if col.values and len(col.values) <= MAX_VALUES:
        # Category labels are short. Anything longer is free text (a possible injected
        # instruction), so it is dropped, not truncated.
        short = [v for v in col.values if len(v) <= MAX_VALUE_CHARS]
        hidden = " (long values hidden)" if len(short) < len(col.values) else ""
        parts.append("values: " + json.dumps(short, ensure_ascii=False) + hidden)
    elif col.min is not None and col.max is not None and col.type != "text":
        parts.append(f"range: {col.min}..{col.max}")
    if col.null_fraction >= 0.01:
        parts.append(f"{col.null_fraction:.0%} null")
    return head + (" | " + " | ".join(parts) if parts else "")


def _table_block(table: TableProfile) -> str:
    kind = "VIEW" if table.is_view else "TABLE"
    origin = table.source_file + (f" / sheet {table.sheet}" if table.sheet else "")
    lines = [f"{kind} {table.name} ({table.row_count} rows) from {origin}"]
    lines += [_column_line(c) for c in table.columns[:MAX_COLUMNS_PER_TABLE]]
    rest = table.columns[MAX_COLUMNS_PER_TABLE:]
    if rest:
        lines.append(f"  ... {len(rest)} more columns: " + ", ".join(c.name for c in rest))
    return "\n".join(lines)


def build_schema_context(catalog: Catalog) -> str:
    """Render the catalog as compact text for the SQL-generation prompt."""
    blocks = [_table_block(t) for t in catalog.tables]

    links = [r for r in catalog.relationships if r.status != "rejected"]
    if links:
        lines = ["RELATIONSHIPS (join keys; cardinality is left:right)"]
        for r in links:
            flag = "" if r.status == "active" else " (unconfirmed)"
            lines.append(
                f"  {r.left_table}.{r.left_column} {r.cardinality} "
                f"{r.right_table}.{r.right_column} "
                f"({min(r.match_left, r.match_right):.0%} of keys match){flag}"
            )
        blocks.append("\n".join(lines))

    unions = [u for u in catalog.unions if u.status == "active"]
    if unions:
        lines = ["UNION VIEWS (same-schema files stacked, with a source_file column)"]
        lines += [f"  {u.view_name} = " + " + ".join(u.tables) for u in unions]
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def build_metric_context(resolved: list[ResolvedMetric]) -> str:
    """Render matched glossary metrics. Empty string when nothing matched."""
    usable = [m for m in resolved if not m.missing_roles]
    if not usable:
        return ""
    lines = ["BUSINESS DEFINITIONS (use these exactly when the question refers to them)"]
    for m in usable:
        lines.append(f"  {m.metric.name}: {m.metric.definition}")
        lines.append(f"    SQL pattern: {m.sql_hint}")
    return "\n".join(lines)
