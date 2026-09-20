"""The single choke point for what a model is allowed to know about the data.

Why this exists: the privacy guarantee ("your rows never reach the model") is only
testable if exactly one function turns a Catalog into prompt text. Nothing else in
the codebase may serialise table contents into a prompt. Inputs are profiles
(statistics), never DataFrames or query results.

What can appear: table and column names, types, roles, null share, numeric/date
ranges, and the true distinct values of non-PII columns with <= 30 distinct values
(the model needs real filter literals such as "Bengaluru"). PII columns expose a name and
a kind, nothing else.

Two things never appear, whatever profiling decided upstream (defence in depth):
- a category value that is long (free text, possibly an injected instruction) or that looks
  like personal data (one email inside a "Remarks" column is still an email);
- the uploaded file or sheet name. The cleaned table name already identifies it, and a file
  name is attacker-controlled text.
"""

from __future__ import annotations

import json
import re

from app.contracts import Catalog, ColumnProfile, ResolvedMetric, TableProfile

MAX_COLUMNS_PER_TABLE = 60  # wider tables list the remaining column names only
MAX_VALUES = 30
MAX_VALUE_CHARS = 40
MAX_VALUE_WORDS = 4  # "Better opportunity elsewhere" is a label; a sentence is not

_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
_PAN_OR_IFSC = re.compile(r"\b([A-Z]{5}\d{4}[A-Z]|[A-Z]{4}0[A-Z0-9]{6})\b", re.IGNORECASE)
_SEPARATORS = re.compile(r"[\s\-()+]")
_LONG_NUMBER = re.compile(r"\d{9,}")  # phone, Aadhaar, UAN, bank account; an ISO date is 8 digits


def _is_safe_value(value: str) -> bool:
    """A category label the model may see: short, and nothing that looks like personal data."""
    if len(value) > MAX_VALUE_CHARS or len(value.split()) > MAX_VALUE_WORDS:
        return False
    if _EMAIL.search(value) or _PAN_OR_IFSC.search(value):
        return False
    return not _LONG_NUMBER.fullmatch(_SEPARATORS.sub("", value))


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
    # Identifier values are row-level data and useless as filter literals, so never listed.
    if col.values and len(col.values) <= MAX_VALUES and not col.is_identifier:
        safe = [v for v in col.values if _is_safe_value(v)]  # dropped, never truncated
        hidden = " (some values hidden)" if len(safe) < len(col.values) else ""
        parts.append("values: " + json.dumps(safe, ensure_ascii=False) + hidden)
    elif col.min is not None and col.max is not None and col.type != "text":
        parts.append(f"range: {col.min}..{col.max}")
    if col.null_fraction >= 0.01:
        parts.append(f"{col.null_fraction:.0%} null")
    return head + (" | " + " | ".join(parts) if parts else "")


def _table_block(table: TableProfile) -> str:
    kind = "VIEW" if table.is_view else "TABLE"
    lines = [f"{kind} {table.name} ({table.row_count} rows)"]
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
                f"({r.match_left:.0%} of left keys and {r.match_right:.0%} of right keys match){flag}"
            )
        blocks.append("\n".join(lines))

    unions = [u for u in catalog.unions if u.status == "active"]
    if unions:
        lines = ["UNION VIEWS (same-schema files stacked, with a source_file column)"]
        lines += [f"  {u.view_name} = " + " + ".join(u.tables) for u in unions]
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def build_metric_context(resolved: list[ResolvedMetric]) -> str:
    """Render matched glossary metrics. Empty string when nothing matched.

    A metric whose columns are absent is stated too, so the model refuses and names the gap
    instead of improvising a different definition."""
    if not resolved:
        return ""
    lines = ["BUSINESS DEFINITIONS (use these exactly when the question refers to them)"]
    for m in resolved:
        if m.missing_roles:
            lines.append(
                f"  {m.metric.name} cannot be computed from this data: no column for "
                f"{', '.join(m.missing_roles)}. If the question needs it, return unanswerable "
                "and say which data is missing."
            )
            continue
        lines.append(f"  [{m.metric.key}] {m.metric.name}: {m.metric.definition}")
        lines.append(f"    SQL pattern: {m.sql_hint}")
    return "\n".join(lines)
