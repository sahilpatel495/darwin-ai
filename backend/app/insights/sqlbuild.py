"""Assemble SQL for the no-model half of the product, from catalog identifiers only.

Why this exists: the automatic overview and the guided analyses must be instant, identical
every time, and keep working when every free model is rate limited. So no model writes this
SQL — these helpers do, from names the catalog already knows.

The safety property, stated once so every caller can rely on it: **no string from a request is
ever interpolated into SQL.** A request names a column ("employees.ctc"); `resolve` looks that
name up in the catalog and hands back the catalog's own spelling, which `ident` quotes. Every
option (aggregate, date grain) is matched against a fixed allow-list, never pasted. A request
carrying quotes, semicolons or SQL keywords therefore fails to match something and raises
ValueError; it cannot reach the statement. The assembled SQL still goes through
`app.query.guard.validate_sql` before it runs: this module is the first lock, not the only one.

Every refusal is a plain sentence an analyst can act on, because these refusals are shown in
the UI next to the picker that caused them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from app.catalog.unions import quote
from app.contracts import Catalog, ColumnProfile, Relationship
from app.insights.models import ColumnKind

# func name the UI shows -> the SQL function. Fixed allow-list: an option that is not a key
# here never becomes SQL.
AGGREGATES: dict[str, str] = {
    "sum": "sum", "average": "avg", "count": "count",
    "median": "median", "min": "min", "max": "max",
}
GRAINS: tuple[str, ...] = ("week", "month", "quarter", "year")

_MEASURE_TYPES = frozenset({"currency", "integer", "decimal", "percent"})
# Above this many distinct values a text column is a list of things, not a set of groups:
# grouping by it produces one row per row and a chart nobody can read. 50 is well past the 12
# bars a chart draws and the 30 values the profiler keeps, and still far below "every name".
MAX_CATEGORY_VALUES = 50
_KIND_WORDS = {"measure": "numbers", "category": "labels", "date": "dates", "text": "free text"}


class Ref(NamedTuple):
    """A column reference that has been checked against the catalog.

    A tuple so callers can unpack `table, column, profile`, and named so the interesting ones
    read well. `table` and `column` are the catalog's spellings, which are the only names that
    may be quoted into SQL.
    """

    table: str
    column: str
    profile: ColumnProfile


def ident(name: str) -> str:
    """A double-quoted DuckDB identifier. Names come from the catalog, never from a request.

    Delegates to the ingest-side quoter so both halves of the app escape the same way.
    """
    return quote(name)


def column_kind(profile: ColumnProfile) -> ColumnKind:
    """Which picker slot a column can fill.

    Currency, integer, decimal and percent are things you add up; a date is something you
    bucket by; a short list of repeated labels is something you group by; anything else is free
    text, which the UI shows but never measures or groups.

    PII and identifier columns are forced to "text" here as well as being refused by `resolve`.
    Without that, an employee id stored as an integer would look like a measure and the UI
    would happily offer "average employee id by department".
    """
    if profile.pii or profile.is_identifier:
        return "text"
    if profile.type in _MEASURE_TYPES:
        return "measure"
    if profile.type == "date":
        return "date"
    if profile.type == "boolean":
        return "category"  # two values, always a group
    if profile.is_unique or profile.distinct_count > MAX_CATEGORY_VALUES:
        return "text"
    return "category"


def resolve(ref: str, catalog: Catalog, accepts: Sequence[ColumnKind] = ()) -> Ref:
    """Turn "table.column" from a request into a checked `Ref`, or raise ValueError.

    `accepts` is the slot's allowed kinds; empty means any kind. Raises with a plain sentence
    when the reference is not "table.column", when the table or column is unknown, when the
    column holds personal data or is an identifier, or when its kind does not fit the slot.
    """
    table_name, _, column_name = ref.partition(".")
    if not table_name or not column_name or "." in column_name:
        raise ValueError(f"{_shown(ref)} is not a column in your files."
                         " Pick a column from the list.")

    table = next((t for t in catalog.tables if t.name.lower() == table_name.lower()), None)
    if table is None:
        raise ValueError(f"There is no table named {_shown(table_name)} in your files."
                         " Pick a column from the list.")
    profile = next((c for c in table.columns if c.name.lower() == column_name.lower()), None)
    if profile is None:
        raise ValueError(f"There is no column named {_shown(column_name)} in {table.name}."
                         " Pick a column from the list.")

    slots = " or ".join(accepts) if accepts else "this"
    if profile.pii:
        raise ValueError(f"{profile.label} holds personal data, so it is never measured,"
                         " grouped by, or used as a category.")
    if profile.is_identifier:
        raise ValueError(f"{profile.label} identifies a row rather than describing one, so it"
                         " cannot be used as a measure or a category.")
    kind = column_kind(profile)
    if accepts and kind not in accepts:
        raise ValueError(f"{profile.label} holds {_KIND_WORDS[kind]}, so it cannot fill the"
                         f" {slots} slot. Pick a {slots} column.")
    return Ref(table.name, profile.name, profile)


def aggregate(func: str, column_sql: str) -> str:
    """One aggregate expression, e.g. aggregate("average", '"employees"."ctc"') -> avg(...).

    `count` ignores `column_sql` and returns count(*): the guided analyses count rows in a
    group ("how many people are in Sales"), and count(col) would silently answer a different
    question — how many of them have that cell filled in.

    # ponytail: no distinct count and no count-of-non-null. Ceiling: "how many distinct
    # managers" cannot be asked. Upgrade path: add "distinct_count" as its own allow-list key.
    """
    if func not in AGGREGATES:
        raise ValueError(f"{_shown(func)} is not something this can calculate."
                         f" Choose one of: {', '.join(AGGREGATES)}.")
    if func == "count":
        return "count(*)"
    return f"{AGGREGATES[func]}({column_sql})"


def date_bucket(column_sql: str, grain: str) -> str:
    """Round a date down to the start of its week, month, quarter or year, for trends.

    date_trunc keeps the column a real date, so presentation formats the axis the same way it
    formats every other date and the rows sort chronologically without extra work.
    """
    if grain not in GRAINS:
        raise ValueError(f"{_shown(grain)} is not a period this can group by."
                         f" Choose one of: {', '.join(GRAINS)}.")
    return f"date_trunc('{grain}', {column_sql})"


def from_clause(refs: Sequence[Ref], catalog: Catalog) -> str:
    """The FROM (and JOIN) the given columns need, using only relationships the analyst has
    left active.

    One table is a plain FROM. Two tables are joined on the single active relationship between
    them. This pre-aggregates nothing, so it refuses the cases where a join would change the
    numbers rather than only widen the rows: an N:M link repeats rows on both sides, and
    totals computed over it are simply wrong. A missing link is refused too, because the
    alternative — a cross join — silently multiplies every row by every other row.
    """
    tables = list(dict.fromkeys(ref.table for ref in refs))
    if not tables:
        raise ValueError("Pick at least one column before running this analysis.")
    if len(tables) == 1:
        return f"FROM {ident(tables[0])}"
    if len(tables) > 2:
        # ponytail: two tables per analysis. Ceiling: a three-file question has to be asked in
        # the chat instead. Upgrade path: walk catalog.relationships for a join path.
        named = ", ".join(tables)
        raise ValueError(f"This analysis can use columns from two files at a time, but these"
                         f" columns come from {len(tables)} ({named}). Drop one.")

    left, right = tables
    link = _active_link(left, right, catalog)
    if link is None:
        raise ValueError(f"{left} and {right} are not linked, so their rows cannot be combined."
                         " Confirm a link between them in the sidebar, or pick columns from"
                         " one file.")
    if link.cardinality == "N:M":
        raise ValueError(f"The link between {left} and {right} matches many rows to many rows,"
                         " so joining them would count the same row more than once. Ask this"
                         " one file at a time.")
    return (f"FROM {ident(left)} JOIN {ident(right)}"
            f" ON {ident(link.left_table)}.{ident(link.left_column)}"
            f" = {ident(link.right_table)}.{ident(link.right_column)}")


def _active_link(left: str, right: str, catalog: Catalog) -> Relationship | None:
    """The first active relationship joining these two tables, in either direction."""
    pair = {left, right}
    return next((r for r in catalog.relationships
                 if r.status == "active" and {r.left_table, r.right_table} == pair), None)


def _shown(text: str) -> str:
    """Request text quoted back in a refusal: one line, short enough to read.

    The request may be hostile, and this sentence goes to the browser as plain text (and never
    into SQL or a prompt), but a 5,000-character "column name" would still wreck the message.
    """
    flat = " ".join(str(text).split())
    return flat[:60] + "…" if len(flat) > 60 else flat or "(blank)"
