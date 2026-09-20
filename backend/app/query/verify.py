"""Catch answers that run fine and are still wrong.

A query can be valid, safe and fast and still overstate payroll because a join repeated rows,
or quietly skip an eighth of the staff because a column is empty for them. These checks use
only the catalog's profile statistics, so they are deterministic and cost no model call.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from itertools import islice
from typing import Any

from app.contracts import Catalog, ColumnProfile
from app.query.executor import ExecResult
from app.query.guard import GuardedQuery

_INFLATED_BY_REPEATS = {"sum": "total", "avg": "average", "count": "count"}  # not min/max
# An empty exit date means "still employed". Warning about it on every attrition question
# would teach the user to ignore caveats.
_EMPTY_IS_MEANINGFUL = {"exit_date"}


def _profiles(catalog: Catalog) -> dict[tuple[str, str], ColumnProfile]:
    return {(t.name, c.name): c for t in catalog.tables for c in t.columns}


# ---- fan-out ------------------------------------------------------------------------------


def fan_out_risks(query: GuardedQuery, catalog: Catalog) -> list[str]:
    """For each equality join use ColumnProfile.is_unique on both keys. Report (a) N:M joins
    and (b) SUM/AVG/COUNT over a column of the unique-key ("one") side of a 1:N join, which
    multiplies rows. Returns human sentences; empty when safe.

    The pipeline asks the model for a rewrite whenever this returns anything, so it stays
    quiet when it cannot be sure:
    ponytail: GuardedQuery has table names, not aliases or scopes. Self-joins are skipped
    (cannot tell which side is aggregated), a join on several keys is only called N:M when one
    key alone proves nothing (composite uniqueness is not profiled), and a join hidden inside
    a pass-through CTE is not seen. Upgrade path: check key uniqueness in DuckDB per scope.
    """
    profiles = _profiles(catalog)
    keys_by_pair: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for join in query.joins:
        ends = sorted([(join.left_table, join.left_column), (join.right_table, join.right_column)])
        if ends[0][0] != ends[1][0]:
            keys_by_pair[ends[0][0], ends[1][0]].append((ends[0][1], ends[1][1]))

    risks = []
    for (left, right), keys in keys_by_pair.items():
        left_unique = any(_is_unique(profiles.get((left, a))) for a, _ in keys)
        right_unique = any(_is_unique(profiles.get((right, b))) for _, b in keys)
        if left_unique and right_unique:
            continue
        if not left_unique and not right_unique:
            if len(keys) == 1:
                a, b = keys[0]
                risks.append(
                    f"Neither {left}.{a} nor {right}.{b} is unique, so this is a many-to-many"
                    " join: every matching row is paired with every other and rows are"
                    " multiplied. Totals and counts are likely too high.")
            continue
        one, many = (left, right) if left_unique else (right, left)
        for func, table, column in query.aggregated:
            if table == one and func in _INFLATED_BY_REPEATS:
                risks.append(
                    f"Each row of {one} can match several rows of {many}, so the join multiplies"
                    f" rows and the {_INFLATED_BY_REPEATS[func]} of {_label(profiles, one, column)}"
                    " counts the same value more than once.")
    return risks


def _is_unique(profile: ColumnProfile | None) -> bool:
    return profile is not None and profile.is_unique


def _label(profiles: dict[tuple[str, str], ColumnProfile], table: str, column: str) -> str:
    profile = profiles.get((table, column))
    return profile.label if profile else column


# ---- NULL and duplicate caveats -----------------------------------------------------------


def null_caveats(query: GuardedQuery, catalog: Catalog, threshold: float = 0.05) -> list[str]:
    """Sentences for referenced columns whose null_fraction >= threshold, plus tables whose
    health reports duplicates (removed or kept).

    SQL skips empty cells silently: avg(ctc) is the average of those who have a CTC. That is
    usually right, but the person presenting the number should know how many were skipped.
    A union view is checked through its member files, where the duplicates were counted.
    """
    profiles = _profiles(catalog)
    caveats = []
    for table, column in query.columns:
        profile = profiles.get((table, column))
        if profile is None or profile.role in _EMPTY_IS_MEANINGFUL:
            continue
        if profile.null_fraction >= threshold:
            caveats.append(
                f"{_percent(profile.null_fraction)} of the rows in {table} have no"
                f" {profile.label}. Those rows are left out of totals, averages and filters"
                " that use it.")

    members = {u.view_name: u.tables for u in catalog.unions}
    touched = {name for table in query.tables for name in (table, *members.get(table, []))}
    for table in catalog.tables:
        count = table.health.duplicate_rows
        if table.name not in touched or not count:
            continue
        rows, was, it = ("row", "was", "it") if count == 1 else ("rows", "were", "them")
        caveats.append(
            f"{count:,} exact duplicate {rows} {was} removed from {table.name} before answering."
            if table.health.duplicates_removed else
            f"{table.name} has {count:,} exact duplicate {rows} that {was} kept, so totals may"
            f" count {it} twice.")
    return caveats


def _percent(fraction: float) -> str:
    return f"{100 * fraction:.1f}".rstrip("0").rstrip(".") + "%"


# ---- cross-check equivalence --------------------------------------------------------------


def results_equivalent(a: ExecResult, b: ExecResult, rel_tol: float = 1e-6) -> bool:
    """Rows compared as multisets, ignoring column names and order; the smaller column set
    must be a subset of the larger; numbers compared with rel_tol; row order ignored.

    Two models rarely pick the same aliases, column order or ORDER BY, and one may add a
    helper column, so none of those count as disagreement. The values must agree.
    """
    if len(a.rows) != len(b.rows):
        return False
    small, large = sorted((a, b), key=lambda result: len(result.columns))
    small_rows = [tuple(_cell(v) for v in row) for row in small.rows]
    large_rows = [tuple(_cell(v) for v in row) for row in large.rows]

    # For each column of the narrower result, the columns of the wider one holding the same
    # values. This prunes the search to (almost always) a single candidate mapping.
    candidates = [
        [j for j in range(len(large.columns))
         if _same_rows([(row[i],) for row in small_rows], [(row[j],) for row in large_rows], rel_tol)]
        for i in range(len(small.columns))
    ]
    # ponytail: at most 200 mappings are tried. Only a result with many identical columns has
    # more, and giving up there reports "disagreed", which is the cautious answer.
    for mapping in islice(_injective(candidates), 200):
        projected = [tuple(row[j] for j in mapping) for row in large_rows]
        if _same_rows(small_rows, projected, rel_tol):
            return True
    return False


def _cell(value: Any) -> tuple[int, Any]:
    """(rank, value): comparable across Decimal/int/float and date/datetime, and sortable even
    when a column mixes NULLs with values, which bare Python values are not."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return (0, 0)
    if isinstance(value, bool):
        return (1, value)
    if isinstance(value, (int, float, Decimal)):
        return (2, float(value))
    if isinstance(value, datetime):
        at_midnight = value.time() == datetime.min.time()
        return (3, value.date().isoformat() if at_midnight else value.isoformat())
    if isinstance(value, date):
        return (3, value.isoformat())
    if isinstance(value, str):
        return (4, value.strip())
    return (5, repr(value))  # lists, structs, intervals


def _same_rows(xs: list[tuple], ys: list[tuple], rel_tol: float) -> bool:
    """Multiset equality with numeric tolerance: sort both, then compare pairwise. Text and
    dates lead the sort key so float noise in a measure cannot reorder otherwise equal rows."""
    def order(row: tuple) -> tuple[list, list]:
        return [c for c in row if c[0] != 2], [c for c in row if c[0] == 2]

    return all(
        _same_cell(c, d, rel_tol)
        for x, y in zip(sorted(xs, key=order), sorted(ys, key=order))
        for c, d in zip(x, y)
    )


def _same_cell(x: tuple[int, Any], y: tuple[int, Any], rel_tol: float) -> bool:
    if x[0] == y[0] == 2:
        return math.isclose(x[1], y[1], rel_tol=rel_tol, abs_tol=1e-9)
    return x == y


def _injective(candidates: list[list[int]], used: tuple[int, ...] = ()):
    """Every way to give each narrow column its own distinct wide column."""
    if len(used) == len(candidates):
        yield used
        return
    for j in candidates[len(used)]:
        if j not in used:
            yield from _injective(candidates, (*used, j))
