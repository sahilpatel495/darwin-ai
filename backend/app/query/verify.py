"""Catch answers that run fine and are still wrong.

A query can be valid, safe and fast and still overstate payroll because a join repeated rows,
or quietly skip an eighth of the staff because a column is empty for them. These checks use
only the catalog's profile statistics, so they are deterministic and cost no model call.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
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
    helper column, so none of those count as disagreement. The values must agree, up to the
    rounding one of them may have applied (see _same_when_rounded).
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
        return (math.isclose(x[1], y[1], rel_tol=rel_tol, abs_tol=1e-9)
                or _same_when_rounded(x[1], y[1]))
    return x == y


def _same_when_rounded(x: float, y: float) -> bool:
    """True when the coarser number is the finer one rounded to its own decimal places.

    One model writes ROUND(AVG(rating), 2) and the other plain AVG(rating): 3.38 and 3.3812
    are the same answer, but the tight tolerance called it a disagreement and badged a correct
    answer Low (final evaluation run, 2026-09-20). Rounding is a presentation choice, so it is
    not a second opinion about the number.

    Only 1 to 4 decimals count. At none, 430 would match 430.4, and a headcount or a rupee
    figure that differs is a real disagreement. Past four we are in float noise, which the
    tolerance already covers. A percentage against a fraction still disagrees: 28.6 is the
    coarser value at one decimal, and 0.286 rounded there is 0.3.

    ponytail: round() breaks a tie to the even digit and DuckDB's ROUND() away from zero, so a
    raw value sitting exactly on a half (3.385 against a reported 3.39) is still called a
    disagreement. Upgrade path if that ever shows up: compare |x - y| against half a place.
    """
    places = min(_decimals(x), _decimals(y))
    if not 1 <= places <= 4:
        return False
    return round(x, places) == round(y, places)  # both are exact at `places`, so == is safe


def _decimals(value: float) -> int:
    """Decimal places in the shortest text that round-trips this float, trailing zeros ignored,
    so 430.0 and 12.50 count as none and one. Infinities have no exponent and count as none."""
    exponent = Decimal(repr(value)).normalize().as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def _injective(candidates: list[list[int]], used: tuple[int, ...] = ()):
    """Every way to give each narrow column its own distinct wide column."""
    if len(used) == len(candidates):
        yield used
        return
    for j in candidates[len(used)]:
        if j not in used:
            yield from _injective(candidates, (*used, j))


# ---- a named period the SQL ignores -------------------------------------------------------

_MONTH_NAMES = ["january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november", "december"]
_MONTHS = {name[:3]: number for number, name in enumerate(_MONTH_NAMES, 1)}
_MONTH_WORDS = "|".join(sorted([*_MONTH_NAMES, *_MONTHS, "sept"], key=len, reverse=True))
_YEAR = r"(?:19|20)\d{2}"
# One period, with an optional fiscal quarter in front of it. The alternatives are ordered so
# that the longest reading wins: "FY 2024-25" is a fiscal year, not the year 2024, and
# "March 2025" is a month, not a year. A year followed by "-25" is neither, so it is left
# unread rather than guessed at.
# Matched against the question as written rather than a lower-cased copy: lowering can change
# the length (len("İ".lower()) is 2), which shifted the offsets and quoted "025" back at the user.
# ponytail: a bare 19xx/20xx number is read as a year wherever it appears, so "our top 2000
# earners" would name a period. Harmless here (the caveat also needs a query that pins nothing
# to that period) and cheap to tighten later by requiring a preposition in front.
_PERIOD = re.compile(
    r"(?:\bq(?P<quarter>[1-4])\s+(?:of\s+)?)?"
    r"(?:\bfy\s*'?(?P<fy>\d{4}|\d{2})(?:\s*[-/]\s*(?P<fy_end>\d{4}|\d{2}))?\b"
    rf"|\b(?P<month>{_MONTH_WORDS})\s+(?:of\s+)?(?P<month_year>{_YEAR})\b"
    rf"|\b(?P<year>{_YEAR})\b(?!\s*[-/]\s*\d))",
    re.IGNORECASE,
)


def period_risks(question: str, query: GuardedQuery, catalog: Catalog) -> list[str]:
    """One sentence per table the number comes from that holds dates outside a period the
    question names while the query filters it by no date at all. "What did we pay in 2025"
    over a register that also holds 2023 and 2024 answers a different question than the one
    asked, and nothing else in the pipeline notices: the SQL is valid, the join is clean and
    the number is real.

    Periods read here: a year; a fiscal year (FY26, FY2026 or FY 2025-26, all meaning
    1 Apr 2025 to 31 Mar 2026); a month with a year; a fiscal quarter with a year, counted
    from April, so Q1 2025 is Apr to Jun 2025. Relative periods ("last quarter", "this year")
    are out of scope: they need today's date and the customer's own calendar, and reading one
    wrong would put a false caveat on a right answer.

    Three things keep it quiet, all of them meaning the number cannot be counting the wrong
    rows: the query uses a date of that table; the table holds nothing outside the period, so
    there is nothing to filter out; or some table the query reads holds only this period, so
    joining to it already restricts the answer (on the sample data "total gross pay by
    department in 2025" reads the 2025-only register and employees, whose joining dates go
    back to 2015 and mean nothing here). A table joined only for a label is never named.
    Silent too whenever the question cannot be read with certainty, for the same reason. It
    never raises: every answered question passes through here.
    """
    period = _named_period(question)
    if period is None:
        return []
    first, last, label = period
    profiles = _profiles(catalog)
    spans = {table: _date_span(catalog, table) for table in dict.fromkeys(query.tables)}
    # ponytail: a table inside the period silences the whole query, even when it is joined in
    # a way that restricts nothing (a LEFT JOIN). A missing caveat beats a wrong one here.
    # Upgrade path: only count it when it is on the filtered side of an inner join.
    if any(span and first <= span[0] and span[1] <= last for span in spans.values()):
        return []
    dated = {table for table, column in query.columns
             if (profile := profiles.get((table, column))) and profile.type == "date"}
    # The number comes from the aggregated columns. count(*) names no table and a plain SELECT
    # aggregates nothing, and then every row of every table is part of the answer.
    measured = {table for _, table, _ in query.aggregated if table in spans} or set(spans)
    return [f"The question names {label}, but the query does not use any date from"
            f" {table}, which covers {_span_text(span)}."
            for table, span in spans.items()
            if span and table in measured and table not in dated]


def _named_period(question: str) -> tuple[date, date, str] | None:
    """The one period the question names, as (first day, last day, the words it used).

    None when it names none, when it names two different ones (a comparison needs both dates,
    so one caveat would be wrong), or when anything in it cannot be resolved.
    """
    found: dict[tuple[date, date], str] = {}
    try:
        for match in _PERIOD.finditer(question):
            period = _resolve_period(match)
            if period is None:
                return None
            found.setdefault(period, match.group().strip())
    except ValueError:  # an impossible year: unreadable, like any other doubt
        return None
    if len(found) != 1:
        return None
    (first, last), label = next(iter(found.items()))
    return first, last, label


def _resolve_period(match: re.Match[str]) -> tuple[date, date] | None:
    """One match turned into its first and last day, or None when it is not a period."""
    quarter = int(match["quarter"]) if match["quarter"] else 0
    if match["fy"]:
        ends = _four_digit(match["fy_end"] or match["fy"])
        if match["fy_end"] and _four_digit(match["fy"]) + 1 != ends:
            return None  # "FY 2024-2026" spans two fiscal years, so it is not one
        year, month, months = ends - 1, 4, 12  # FY26 is 1 Apr 2025 to 31 Mar 2026
    elif match["month"]:
        if quarter:
            return None  # "Q1 March 2025" is a quarter and a month, which is neither
        year, month, months = int(match["month_year"]), _MONTHS[match["month"][:3].lower()], 1
    else:
        year, month, months = int(match["year"]), 1, 12
    if quarter:
        month, months = 4 + 3 * (quarter - 1), 3  # Indian fiscal quarters: Q1 is Apr to Jun
    start = year * 12 + month - 1
    return _month_start(start), _month_start(start + months) - timedelta(days=1)


def _four_digit(text: str) -> int:
    """FY25, FY'25 and FY2025 all mean the fiscal year ending in 2025."""
    number = int(text)
    return number + 2000 if number < 100 else number


def _month_start(months_since_year_zero: int) -> date:
    """First of the month, counted in whole months, so Q4 rolling into January needs no case."""
    year, month = divmod(months_since_year_zero, 12)
    return date(year, month + 1, 1)


def _date_span(catalog: Catalog, table: str) -> tuple[date, date] | None:
    """Earliest and latest date in any date column of the table, or None when it has none.

    Across columns on purpose: "how many joined in 2025" reads employees, where the joining
    dates go back to 2017 even though every exit date is this year.
    """
    profile = next((t for t in catalog.tables if t.name == table), None)
    if profile is None:
        return None
    bounds = [(_iso(c.min), _iso(c.max)) for c in profile.columns if c.type == "date"]
    lows = [low for low, _ in bounds if low]
    highs = [high for _, high in bounds if high]
    return (min(lows), max(highs)) if lows and highs else None


def _iso(value: str | None) -> date | None:
    """ColumnProfile.min/max are stringified, so a date arrives as "2025-01-31" and a timestamp
    with a time after it. Anything else is not a date this check can reason about."""
    try:
        return date.fromisoformat(value[:10]) if value else None
    except (TypeError, ValueError):
        return None


def _span_text(span: tuple[date, date]) -> str:
    """Months, not days: the question asked about a period, not about a row."""
    first, last = (f"{day:%b %Y}" for day in span)
    return first if first == last else f"{first} to {last}"
