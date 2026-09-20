"""Table structure: which row is the header, and which trailing rows are totals.

Why this matters: HR reports are made for people. They start with a title block and end
with a Grand Total. Read naively, the title becomes the column names and the total is
summed along with the rows it already adds up, so every total comes out doubled.
"""

from __future__ import annotations

import re

from app.ingest.cleaning import clean_cell, is_null, parse_amount, parse_date

Grid = list[list[str | None]]

HEADER_SEARCH_ROWS = 15
MIN_HEADER_FILL = 0.5  # a title is one or two cells in a wide sheet; a header names most columns
CLOSE_TO_BEST = 0.7  # a header with a blank cell or a repeated name still scores this well
# Matched against a cleaned cell (trimmed, single spaces), and only as the whole cell, so a
# customer called "Totally Fine Corp" is safe. "Sub Total" counts: a register often ends
# with the last department's subtotal and then the grand total, and both double-count.
_TOTAL_LABEL = re.compile(r"(grand |sub[ -]?)?totals? ?:?", re.IGNORECASE)


def drop_empty_columns(grid: Grid) -> Grid:
    """Remove columns that are blank in every row, header included.

    These are formatting leftovers (a styled but unused column in Excel, a trailing comma
    on every CSV line). They carry no name and no data, so they are not reported.
    """
    width = max((len(row) for row in grid), default=0)
    keep = [i for i in range(width) if any(not is_null(row[i]) for row in grid if i < len(row))]
    if len(keep) == width and all(len(row) == width for row in grid):
        return grid  # nothing to drop: do not copy a large table
    return [[row[i] if i < len(row) else None for i in keep] for row in grid]


def detect_header_row(grid: Grid) -> int:
    """Index of the header row among the first 15 rows; rows above it are title rows.

    Each row is scored by how full it is, how much of it is wording rather than numbers or
    dates, and how distinct its cells are. A header is full, all words and all different;
    a data row contains numbers and dates; a title row is mostly empty, so rows less than
    half full are not candidates at all.

    The winner is the *first* row scoring close to the best, not the single best. When the
    data is all text, a data row looks exactly like a header, and a header with one blank
    cell would lose to it: the first data row would become the column names and silently
    drop out of every count. Position is the only evidence left, and headers come first.

    ponytail: rows are judged on their own. A title row that is over half full of words
    in a narrow table can still win. Upgrade path: also compare each candidate with the
    value types in the rows beneath it.
    """
    width = max((len(row) for row in grid), default=0)
    rows = grid[:HEADER_SEARCH_ROWS]
    scores = [_header_score(row, width) for row in rows]
    best = max(scores, default=0.0)
    if best == 0.0:  # nothing is even half full: take the first row that has any content
        return next((i for i, row in enumerate(rows) if not all(is_null(c) for c in row)), 0)
    return next(i for i, score in enumerate(scores) if score >= CLOSE_TO_BEST * best)


def _header_score(row: list[str | None], width: int) -> float:
    cells = [cell for cell in row if not is_null(cell)]
    filled = len(cells) / width if width else 0.0
    if filled < MIN_HEADER_FILL:
        return 0.0
    wording = sum(_is_wording(cell) for cell in cells) / len(cells)
    distinct = len({cell.strip().lower() for cell in cells}) / len(cells)
    return filled * wording * distinct


def _is_wording(cell: str) -> bool:
    text = cell.strip()
    return parse_amount(text) is None and parse_date(text) is None and not text.endswith("%")


def drop_footer_totals(rows: Grid) -> tuple[Grid, int, int]:
    """Drop trailing total rows. Returns (rows kept, total rows dropped, note rows dropped).

    A total row is one whose first non-empty cell is exactly "Total", "Grand Total" or
    "Sub Total". Sign-off lines under a total ("Prepared by ...": one cell in a table at
    least three wide) are dropped with it, because if they shielded the total it would
    stay in the data and be double-counted. With no total above them such lines are kept:
    we do not guess.
    """
    cut = len(rows)
    totals = 0
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if _is_total_row(row):
            totals += 1
            cut = index
        elif not (sum(not is_null(cell) for cell in row) == 1 and len(row) >= 3):
            break
    return rows[:cut], totals, len(rows) - cut - totals


def count_inner_totals(rows: Grid) -> int:
    """Total rows left in the table once the footer is gone: subtotals between groups.

    They are counted so the user can be warned, not dropped. Inside the table we cannot
    be sure a row is a subtotal, and deleting rows on a guess is worse than saying so.
    """
    return sum(_is_total_row(row) for row in rows)


def _is_total_row(row: list[str | None]) -> bool:
    # clean_cell, not the raw cell: the pattern assumes single spaces, and on raw text a
    # cell of "total" plus 100,000 spaces made the regex engine backtrack for a minute.
    first = next((text for cell in row if (text := clean_cell(cell)) is not None), None)
    return first is not None and _TOTAL_LABEL.fullmatch(first) is not None
