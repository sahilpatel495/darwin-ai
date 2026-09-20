"""Decide whether the app's result table contains the expected answer.

Why this file is strict and separately tested: it produces the accuracy number on the Trust
Report. A false pass inflates a figure someone may quote to their CHRO; a false fail sends the
tuning loop after a bug that is not there. When a rule could go either way it goes strict,
because failures are listed and get looked at, while passes are trusted.

The rules, in plain words:
- A single expected value matches any cell of a one-row result.
- Expected rows are compared as a multiset: row order and column names are ignored (pass
  `ordered=True` for rankings). The result may have extra columns; every expected column must
  be found, and columns are paired up by their values, not their names.
- Two whole numbers must be equal exactly: a headcount that is off by one is wrong however
  large it is. Otherwise numbers match within `rel_tol`, or when they agree after rounding to
  2 decimals, or to 1 decimal when one side is itself a 1-decimal number (the SQL rules ask
  for `round(100.0 * a / b, 1)` on percentages). A tie may be rounded either way: DuckDB
  turns 6.25 into 6.3 and Python into 6.2, and both are right. Whole-number rounding is
  never forgiven: 4 is not 4.4.
- Dates compare by value whether they arrive as `date`, `Timestamp` or ISO text; `2025-04`
  means 1 April 2025, the same reading the ingestion step uses.
- Text is trimmed and case-insensitive. A number and numeric text compare as numbers, because
  pandas reads the id `000123` from a clean CSV as 123 while DuckDB keeps it as text.
- Missing values (None, NaN, NaT) match each other and nothing else. `True` is not 1.
- A single expected value that is itself missing is refused with a ValueError: it would pass
  on any one-row result that has a blank cell, and it means the truth function is broken.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import Decimal
from numbers import Real
from typing import Any

from app.contracts import ResultTable

Row = Sequence[Any]

_ISO_DATE_TEXT = re.compile(r"^\d{4}-\d{2}(-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?)?$")
_ABS_TOL = 1e-9  # lets 0.0 match 0.0000000001; relative tolerance alone cannot


def matches(expected: Any, table: ResultTable, ordered: bool = False, rel_tol: float = 1e-6) -> bool:
    """True when `table` holds the expected answer. `expected` is what a truth function
    returned: one value, one tuple (a row), a list of tuples, or a dict/Series/DataFrame.

    Raises ValueError when `expected` itself cannot be graded (ragged rows, a missing value).
    The runner checks every expected value this way before it asks anything, so a golden-set
    bug costs no tokens and never surfaces halfway through a run."""
    got = [[_canonical(cell) for cell in row] for row in table.rows]
    expected_rows = _as_rows(expected)
    if expected_rows is None:
        wanted = _canonical(expected)
        if wanted is None:
            raise ValueError("The expected value is missing (None or NaN). Fix the truth function.")
        return len(got) == 1 and any(_cells_match(wanted, cell, rel_tol) for cell in got[0])
    wanted_rows = [[_canonical(cell) for cell in row] for row in expected_rows]
    if len({len(row) for row in wanted_rows}) > 1:
        raise ValueError("Every expected row must have the same number of values. Fix the truth function.")
    return _rows_match(wanted_rows, got, ordered, rel_tol)


# --------------------------------------------------------------------------
# Shapes and values
# --------------------------------------------------------------------------


def _as_rows(expected: Any) -> list[tuple] | None:
    """Expected rows as tuples, or None when `expected` is a single value. Duck-typed so this
    module needs no pandas import: a DataFrame has `itertuples`, a dict or Series has `items`."""
    if hasattr(expected, "itertuples"):
        # A grouped frame keeps its labels in the index. Dropping them would leave only the
        # numbers to compare, and a result with the wrong labels would pass.
        plain_index = type(expected.index).__name__ == "RangeIndex"
        frame = expected if plain_index else expected.reset_index()
        return list(frame.itertuples(index=False, name=None))
    if hasattr(expected, "items"):
        return [(*key, value) if isinstance(key, tuple) else (key, value) for key, value in expected.items()]
    if isinstance(expected, tuple):
        return [expected]
    if isinstance(expected, list):
        return [tuple(row) if isinstance(row, (list, tuple)) else (row,) for row in expected]
    return None


def _canonical(value: Any) -> Any:
    """Reduce a cell to one of: None, bool, float, date, datetime, folded text. Both sides go
    through this, so a pandas Timestamp and the ISO string in a JSON-safe table end up equal."""
    if hasattr(value, "item") and not isinstance(value, str):
        value = value.item()  # numpy scalar -> Python scalar
    if value is None or type(value).__name__ in ("NaTType", "NAType"):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (Real, Decimal)):
        number = float(value)
        return None if math.isnan(number) else number
    if isinstance(value, datetime):
        return value.date() if value.time() == time.min else value.replace(tzinfo=None)
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if _ISO_DATE_TEXT.match(text):
        try:
            return _canonical(datetime.fromisoformat(text if len(text) > 7 else text + "-01"))
        except ValueError:
            pass  # looks like a date but is not one (month 13): keep it as text
    return text.casefold()


def _cells_match(expected: Any, got: Any, rel_tol: float) -> bool:
    if expected is None or got is None or isinstance(expected, bool) or isinstance(got, bool):
        return expected is got
    expected, got = _as_number_if_other_is(expected, got), _as_number_if_other_is(got, expected)
    if isinstance(expected, float) and isinstance(got, float):
        return _numbers_match(expected, got, rel_tol)
    return type(expected) is type(got) and expected == got


def _as_number_if_other_is(value: Any, other: Any) -> Any:
    """'000123' next to 123.0 becomes 123.0. Text next to text is left alone, so ids stay ids."""
    if isinstance(value, str) and isinstance(other, float):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _numbers_match(expected: float, got: float, rel_tol: float) -> bool:
    def close(a: float, b: float) -> bool:
        return math.isclose(a, b, rel_tol=rel_tol, abs_tol=_ABS_TOL)

    def already_rounded(value: float, decimals: int) -> bool:
        return close(round(value, decimals), value)

    def agree_at(decimals: int) -> bool:
        """Equal once both are rounded. A side that is already rounded also matches anything
        within half a unit of it, because a tie has two honest roundings: DuckDB rounds 6.25
        away from zero (6.3), Python rounds it to even (6.2)."""
        if close(round(expected, decimals), round(got, decimals)):
            return True
        one_side_is_rounded = already_rounded(expected, decimals) or already_rounded(got, decimals)
        return one_side_is_rounded and abs(expected - got) <= 0.5 * 10**-decimals + _ABS_TOL

    if expected.is_integer() and got.is_integer():
        # Counts and whole-rupee totals. A relative tolerance would forgive 1,000,001 for
        # 1,000,000, and whole numbers carry no float noise that needs forgiving.
        return expected == got
    if close(expected, got) or agree_at(2):
        return True
    return (already_rounded(expected, 1) or already_rounded(got, 1)) and agree_at(1)


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------


def _rows_match(wanted: list[list], got: list[list], ordered: bool, rel_tol: float) -> bool:
    if len(wanted) != len(got):
        return False
    if not wanted:
        return True
    width, got_width = len(wanted[0]), len(got[0])
    if width > got_width:
        return False

    def same(a: list[Row], b: list[Row]) -> bool:
        return _same_sequence(a, b, rel_tol) if ordered else _same_multiset(a, b, rel_tol)

    # Pair columns by value. A column can only stand in for an expected column if, on its own,
    # it holds the same values; that prunes the search before whole rows are compared.
    candidates = [
        [c for c in range(got_width) if same([(row[j],) for row in wanted], [(row[c],) for row in got])]
        for j in range(width)
    ]
    for mapping in itertools.product(*candidates):
        if len(set(mapping)) == width and same(wanted, [[row[c] for c in mapping] for row in got]):
            return True
    return False


def _same_sequence(wanted: list[Row], got: list[Row], rel_tol: float) -> bool:
    return all(_row_matches(w, g, rel_tol) for w, g in zip(wanted, got, strict=True))


def _same_multiset(wanted: list[Row], got: list[Row], rel_tol: float) -> bool:
    """Each expected row must claim one result row that nothing else has claimed.

    ponytail: greedy first-fit. Numbers are forgiven 0.05 at most (a rounded percentage), so
    two different result rows do not both fit one expected row in practice; if tolerances
    ever widen, switch to bipartite matching.
    Sorting both sides first means the partner is usually next in line, so this stays close to
    linear under the app's 5,000-row cap.
    """
    remaining = sorted(got, key=_sort_key)
    for row in sorted(wanted, key=_sort_key):
        for index, candidate in enumerate(remaining):
            if _row_matches(row, candidate, rel_tol):
                del remaining[index]
                break
        else:
            return False
    return True


def _row_matches(wanted: Row, got: Row, rel_tol: float) -> bool:
    return all(_cells_match(w, g, rel_tol) for w, g in zip(wanted, got, strict=True))


def _sort_key(row: Row) -> tuple:
    """Order rows of mixed types without ever comparing a string to a number. Sorting is only
    a speed-up; correctness never depends on the two sides sorting alike."""
    def cell_key(cell: Any) -> tuple[int, float, str]:
        if cell is None:
            return (0, 0.0, "")
        if isinstance(cell, (bool, float)):
            return (1, float(cell), "")
        return (2, 0.0, cell if isinstance(cell, str) else cell.isoformat())

    return tuple(cell_key(cell) for cell in row)
