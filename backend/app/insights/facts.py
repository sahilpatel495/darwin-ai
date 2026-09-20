"""Say what a result means, deterministically, in one sentence and up to three short facts.

Why: a tile with a chart and no words makes the analyst do the reading. A model could do the
reading, but then the overview would cost tokens, differ between runs, and stop working the
moment the free tier is exhausted — and this half of the product exists precisely to keep
working then. So the sentence is computed from the rows.

Two rules make these lines safe to show next to a model-written answer:
- every number is a display string from `presentation.to_display`, so "₹20.40 Cr" here and
  "₹20.40 Cr" in an answer are the same number formatted the same way;
- a claim is only made when the rows support it. A ratio needs a positive denominator, a
  share needs the whole total (never a truncated one), "Top 3" needs more than three groups,
  and a tie names every winner rather than picking one. DECISIONS #20 is about exactly this:
  a true number under a false sentence is still a wrong answer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.contracts import ResultTable
from app.insights.models import TileKind
from app.query.presentation import ValueKind, to_display

NOTHING = "There is nothing to show for this yet."

_MEASURE_KINDS = frozenset({"currency", "percent", "integer", "decimal"})
_MAX_LINES = 3
# Words that mean a column holds a statistic *about* rows rather than an amount *of* something.
# Adding six averages together gives a number that is not the total of anything, so no share of
# it may be claimed. Matched against the underscore-separated words of the output name, which
# dashboard.py and analyses.py write ("average_ctc", "median_ctc", "total_gross", "employees").
_NOT_ADDABLE_WORDS = frozenset({"average", "avg", "mean", "median", "quartile", "percentile",
                                "p25", "p50", "p75", "lowest", "highest", "min", "max", "rate"})
# Column names that carry a summary statistic, matched as substrings of the output name so
# "median_ctc" and "ctc_median" both count.
_MEDIAN_NAMES = ("median", "p50")
_LOWER_QUARTILE_NAMES = ("p25", "q1", "lower_quartile")
_UPPER_QUARTILE_NAMES = ("p75", "q3", "upper_quartile")
_WORDS = {"avg": "average", "pct": "percentage", "qty": "quantity",
          "amt": "amount", "num": "number"}
# The acronyms an Indian HR file is full of, so neither a sentence nor a heading writes "Ctc"
# or "Tds". One place to add "ESI" when a file turns up with it.
ACRONYMS = frozenset({"CTC", "LOP", "PF", "TDS", "HRA", "FY", "ID"})
# Title case: everything is capitalised except these, and the first word always is. Long
# prepositions ("against", "between") are capitalised, which is what every style guide does.
_MINOR_WORDS = frozenset({"a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
                          "of", "on", "or", "per", "the", "to", "vs", "with"})


@dataclass(frozen=True)
class _Shape:
    """Which output columns are worth talking about, found once and reused by every builder."""

    table: ResultTable
    kinds: list[ValueKind]
    measures: list[int]
    labels: list[int]
    dates: list[int]

    def display(self, row: int, column: int) -> str:
        """The cell as the analyst sees it. build_table always fills `display`; the fallback is
        for a ResultTable assembled by hand in a test or by another module."""
        shown = self.table.display
        if row < len(shown) and column < len(shown[row]):
            return shown[row][column]
        return to_display(self.table.rows[row][column], self.kinds[column])

    def value(self, row: int, column: int) -> float | None:
        return _number(self.table.rows[row][column])

    def name(self, column: int) -> str:
        return _humanise(self.table.columns[column])

    def ranked(self, column: int) -> list[int]:
        """Row indices whose measure is a real number: empty cells are skipped, never read
        as zero, which is the same rule SQL's own aggregates follow."""
        return [i for i in range(len(self.table.rows)) if self.value(i, column) is not None]


def describe(
    table: ResultTable, kinds: list[str], kind: TileKind, title: str
) -> tuple[str, list[str]]:
    """One sentence about this result, plus up to three short computed facts.

    `kind` picks the reading (a trend is read over time, a breakdown across groups); a result
    whose shape does not match its kind falls back to the reading its columns do support, so a
    mislabelled tile still says something true rather than raising.
    """
    if not table.rows:
        return NOTHING, []
    shape = _shape(table, list(kinds))
    statement, lines = _BUILDERS.get(kind, _fallback)(shape, title)
    return statement, _trim(lines)


def insight_lines(table: ResultTable, kinds: list[str]) -> list[str]:
    """The same computed facts, for a result nobody labelled — a model-written answer.

    Exported so an answer in the chat carries the same "Top 3 make up 72.0%" line the dashboard
    would have shown for the same rows.
    """
    if not table.rows:
        return []
    return _trim(_fallback(_shape(table, list(kinds)), "")[1])


# --------------------------------------------------------------------------- readings


def _kpi(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """One figure with its name. The headline measure is the last one, because a metric query
    ends with the figure that was asked for (the same rule choose_chart uses)."""
    if not shape.measures:
        return _fallback_text(shape, title), []
    headline = shape.measures[-1]
    label = title or shape.name(headline)
    if shape.value(0, headline) is None:
        return f"{_cap(label)} could not be calculated from this data.", []
    statement = f"{_cap(label)} is {shape.display(0, headline)}."
    lines = [f"{_cap(shape.name(i))}: {shape.display(0, i)}."
             for i in shape.measures[:-1] if shape.display(0, i) != "—"]
    return statement, lines


def _breakdown(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """Highest and lowest group, then how concentrated the total is."""
    group = _first(shape.labels, shape.dates)
    if group is None or not shape.measures:
        return _fallback_text(shape, title), []
    measure = shape.measures[0]
    ranked = shape.ranked(measure)
    if not ranked:
        return _fallback_text(shape, title), []

    tops = _winners(shape, measure, ranked, best=True)
    bottoms = _winners(shape, measure, ranked, best=False)
    count = to_display(len(ranked), "integer")
    top_value, bottom_value = shape.display(tops[0], measure), shape.display(bottoms[0], measure)

    if len(ranked) == 1:
        statement = f"{shape.display(ranked[0], group)} is the only group, at {top_value}."
    elif shape.value(tops[0], measure) == shape.value(bottoms[0], measure):
        statement = f"All {count} groups are level at {top_value}."
    else:
        verb = "are" if len(tops) > 1 else "is"
        statement = (f"{_names(shape, group, tops)} {verb} highest at {top_value} and"
                     f" {_names(shape, group, bottoms)} lowest at {bottom_value},"
                     f" across {count} groups.")
    return statement, _spread_lines(shape, measure, ranked, tops, bottoms)


def _spread_lines(shape: _Shape, measure: int, ranked: list[int],
                  tops: list[int], bottoms: list[int]) -> list[str]:
    """Concentration, spread and the middle of a grouped result.

    Every line here is skipped when the rows cannot support it: shares need the whole total
    (a truncated result has only part of it) and non-negative parts, a ratio needs a positive
    lowest, and adding up a column of percentages — or of averages — measures nothing at all.
    """
    values = [shape.value(i, measure) for i in ranked]
    kind = shape.kinds[measure]
    addable = kind != "percent" and not shape.table.truncated and all(v >= 0 for v in values)
    # The mean of a column of averages is still an honest "average across the groups"; a share
    # of their sum is not, because that sum is not the total of anything.
    summable = addable and _addable_name(shape, measure)
    lines = []
    if summable and len(ranked) > 3 and (total := sum(values)) > 0:
        top_three = sum(sorted(values, reverse=True)[:3])
        lines.append(f"Top 3 make up {to_display(100 * top_three / total, 'percent')} of the total.")
    low, high = shape.value(bottoms[0], measure), shape.value(tops[0], measure)
    if low > 0 and high != low:
        lines.append(f"The highest is {to_display(round(high / low, 1), 'decimal')}× the lowest.")
    if addable and len(ranked) > 1:
        lines.append(f"The average across the groups is"
                     f" {to_display(sum(values) / len(values), kind)}.")
    return lines


def _trend(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """Where a dated series starts, where it ends, and its peak."""
    if not shape.dates or not shape.measures:
        return _breakdown(shape, title)
    when, measure = shape.dates[0], shape.measures[0]
    # ISO dates sort chronologically as text (presentation._json_safe writes them that way), so
    # a series the SQL did not order still starts where it starts.
    ranked = sorted(shape.ranked(measure), key=lambda i: str(shape.table.rows[i][when]))
    if not ranked:
        return _fallback_text(shape, title), []
    first, last = ranked[0], ranked[-1]
    name = _cap(title or shape.name(measure))
    if len(ranked) == 1:
        return (f"{name} has one period so far: {shape.display(first, measure)}"
                f" ({shape.display(first, when)})."), []

    statement = (f"{name} went from {shape.display(first, measure)} ({shape.display(first, when)})"
                 f" to {shape.display(last, measure)} ({shape.display(last, when)}).")
    return statement, _change_lines(shape, measure, when, ranked)


def _change_lines(shape: _Shape, measure: int, when: int, ranked: list[int]) -> list[str]:
    """How far it moved, and the peak and trough along the way."""
    first, last = ranked[0], ranked[-1]
    start, end = shape.value(first, measure), shape.value(last, measure)
    from_to = f"from {shape.display(first, when)} to {shape.display(last, when)}"
    if start == end:
        lines = [f"Unchanged {from_to}."]
    elif start > 0:
        # A percentage change needs a positive starting point: "up 300% from -₹1 L" is noise.
        move = to_display(abs(100 * (end - start) / start), "percent")
        lines = [f"{'Up' if end > start else 'Down'} {move} {from_to}."]
    else:
        move = to_display(abs(end - start), shape.kinds[measure])
        lines = [f"{'Up' if end > start else 'Down'} {move} {from_to}."]

    peak = max(ranked, key=lambda i: shape.value(i, measure))
    trough = min(ranked, key=lambda i: shape.value(i, measure))
    if shape.value(peak, measure) != shape.value(trough, measure):
        lines.append(f"Peak was {shape.display(peak, measure)} ({shape.display(peak, when)}).")
        lines.append(f"Low was {shape.display(trough, measure)} ({shape.display(trough, when)}).")
    return lines


def _distribution(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """A one-row summary reads as median and middle half; anything else is a histogram, which
    reads as a breakdown over its buckets."""
    median = _named_column(shape, _MEDIAN_NAMES)
    if median is None or len(shape.table.rows) != 1:
        return _breakdown(shape, title)
    statement = f"{_cap(title or shape.name(median))} has a median of {shape.display(0, median)}."
    lower, upper = _named_column(shape, _LOWER_QUARTILE_NAMES), _named_column(shape, _UPPER_QUARTILE_NAMES)
    lines = []
    if lower is not None and upper is not None:
        lines.append(f"The middle half falls between {shape.display(0, lower)}"
                     f" and {shape.display(0, upper)}.")
    lines += [f"{_cap(shape.name(i))}: {shape.display(0, i)}."
              for i in shape.measures if i not in (median, lower, upper)][:2]
    return statement, lines


def _share(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """The largest slice, as a percentage. A percent column in the result is used as it is;
    otherwise the share is computed, but only from a whole, non-negative total."""
    group = _first(shape.labels, shape.dates)
    if group is None or not shape.measures:
        return _fallback_text(shape, title), []
    percents = [i for i in shape.measures if shape.kinds[i] == "percent"]
    measure = percents[0] if percents else shape.measures[0]
    ranked = shape.ranked(measure)
    if not ranked:
        return _fallback_text(shape, title), []

    tops = _winners(shape, measure, ranked, best=True)
    verb = "are" if len(tops) > 1 else "is"
    names = _names(shape, group, tops)
    if percents:
        statement = f"{names} {verb} the largest share at {shape.display(tops[0], measure)}."
        return statement, _spread_lines(shape, measure, ranked, tops,
                                        _winners(shape, measure, ranked, best=False))

    values = [shape.value(i, measure) for i in ranked]
    total = sum(values)
    if (shape.table.truncated or total <= 0 or any(v < 0 for v in values)
            or not _addable_name(shape, measure)):
        return _breakdown(shape, title)
    share = to_display(100 * shape.value(tops[0], measure) / total, "percent")
    statement = (f"{names} {verb} the largest share at {share} of the total"
                 f" ({shape.display(tops[0], measure)} of {to_display(total, shape.kinds[measure])}).")
    return statement, _spread_lines(shape, measure, ranked, tops,
                                    _winners(shape, measure, ranked, best=False))


def _two_way(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """Two groupings and a measure: name the largest cell and the smallest."""
    grouping = sorted(shape.labels + shape.dates)
    if len(grouping) < 2 or not shape.measures:
        return _breakdown(shape, title)
    rows, columns, measure = grouping[0], grouping[1], shape.measures[0]
    ranked = shape.ranked(measure)
    if not ranked:
        return _fallback_text(shape, title), []

    tops = _winners(shape, measure, ranked, best=True)
    bottoms = _winners(shape, measure, ranked, best=False)
    cell = f"{shape.display(tops[0], rows)} / {shape.display(tops[0], columns)}"
    count, top_value = to_display(len(ranked), "integer"), shape.display(tops[0], measure)
    if len(tops) == len(ranked):
        # Every cell holds the same number: naming one of them "the largest" would invent a
        # difference the rows do not have.
        return f"All {count} combinations are level at {top_value}.", []
    if len(tops) > 1:
        # The tie is between `tops`, not between every combination in the result: saying
        # "48 combinations are tied" when two are is the false sentence this module exists
        # to avoid.
        statement = (f"{to_display(len(tops), 'integer')} of {count} combinations are tied at"
                     f" the top on {top_value}, including {cell}.")
    else:
        statement = f"{cell} is the largest at {top_value}, across {count} combinations."
    lines = [(f"{shape.display(bottoms[0], rows)} / {shape.display(bottoms[0], columns)}"
              f" is the smallest at {shape.display(bottoms[0], measure)}.")]
    return statement, lines + _spread_lines(shape, measure, ranked, tops, bottoms)


def _fallback(shape: _Shape, title: str) -> tuple[str, list[str]]:
    """The reading the columns support, for a tile whose kind does not match its result and
    for `insight_lines`, which is handed rows with no kind at all."""
    if len(shape.table.rows) == 1 and shape.measures:
        return _kpi(shape, title)
    if shape.dates and shape.measures and not shape.labels:
        return _trend(shape, title)
    if len(shape.labels) >= 2 and shape.measures:
        return _two_way(shape, title)
    if (shape.labels or shape.dates) and shape.measures:
        return _breakdown(shape, title)
    return _fallback_text(shape, title), []


def _fallback_text(shape: _Shape, title: str) -> str:
    """Nothing numeric to read: say how much there is, which is still true and still useful."""
    count = to_display(shape.table.row_count, "integer")
    rows = "row" if shape.table.row_count == 1 else "rows"
    more = " (the first page of a longer result)" if shape.table.truncated else ""
    return f"{_cap(title) + ': ' if title else 'This shows '}{count} {rows}{more}."


_BUILDERS = {
    "kpi": _kpi, "metric": _kpi,
    "breakdown": _breakdown,
    "trend": _trend,
    "distribution": _distribution,
    "share": _share,
    "comparison": _two_way,
    "relationship": _fallback,
    "quality": _fallback,
}


# --------------------------------------------------------------------------- helpers


def _shape(table: ResultTable, kinds: list[str]) -> _Shape:
    kinds = list(kinds) + ["text"] * (len(table.columns) - len(kinds))  # never index past the end
    return _Shape(
        table=table, kinds=kinds,
        measures=[i for i, k in enumerate(kinds[:len(table.columns)]) if k in _MEASURE_KINDS],
        labels=[i for i, k in enumerate(kinds[:len(table.columns)]) if k == "text"],
        dates=[i for i, k in enumerate(kinds[:len(table.columns)]) if k == "date"],
    )


def _number(value: Any) -> float | None:
    """A cell that can be compared and added. `True` is an int in Python and a label here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _winners(shape: _Shape, measure: int, ranked: list[int], *, best: bool) -> list[int]:
    """Every row holding the top (or bottom) value, in row order. Naming one of several tied
    groups as "the highest" is the false-sentence failure this product was built to avoid."""
    pick = max if best else min
    target = pick(shape.value(i, measure) for i in ranked)
    return [i for i in ranked if shape.value(i, measure) == target]


def _names(shape: _Shape, column: int, rows: list[int]) -> str:
    """Up to two winners by name; beyond that, a count, because a sentence listing nine tied
    departments is not a sentence."""
    shown = [shape.display(i, column) for i in rows[:2]]
    if len(rows) == 1:
        return shown[0]
    if len(rows) == 2:
        return f"{shown[0]} and {shown[1]}"
    return f"{shown[0]}, {shown[1]} and {to_display(len(rows) - 2, 'integer')} more"


def _first(*groups: list[int]) -> int | None:
    return next((g[0] for g in groups if g), None)


def _addable_name(shape: _Shape, measure: int) -> bool:
    """Can this column be totalled at all?

    A column of averages, medians, minimums or rates is a statistic per group, and the sum of
    those is not the total of anything — so "Top 3 make up 72.0% of the total" over it would be
    arithmetic dressed as a finding. The aggregate is not in the result, but the name our own
    templates give the column is ("average_ctc", "total_gross", "employees"), and an unknown
    name is treated as addable because a plain amount column is the common case.
    """
    words = set(shape.table.columns[measure].lower().split("_"))
    return not (words & _NOT_ADDABLE_WORDS)


def _named_column(shape: _Shape, options: tuple[str, ...]) -> int | None:
    lowered = [c.lower() for c in shape.table.columns]
    return next((i for i, name in enumerate(lowered) if any(o in name for o in options)), None)


def _humanise(column: str) -> str:
    """A column name as the words an analyst says: avg_ctc -> "average CTC", total_lop -> "total LOP"."""
    return " ".join(_WORDS.get(word.lower(), word.upper() if word.upper() in ACRONYMS
                               else word.lower())
                    for word in column.split("_") if word)


def titled(text: str) -> str:
    """A heading, title-cased, from words that are already the file's own.

    Here rather than in whichever module writes the heading, because this is the same knowledge
    `_humanise` uses: it is how this app writes an analyst's own words back to them. `analyses`
    titles every guided analysis with it.

    Why not `str.title()`: it writes "Ctc", "Tds" and "Hra", which is the first thing that makes
    a generated page look generated. A word the file did not write in lower case is left exactly
    as it is, because the header is the analyst's spelling and not ours: "iOS", "eNPS" and "DOJ"
    all survive. Only header-derived text goes through this — a value out of the data keeps its
    own spelling, since retyping somebody's team name is not a formatting decision.
    """
    words = " ".join(text.split()).split(" ")
    return " ".join(_titled_word(word, first=index == 0) for index, word in enumerate(words))


def _titled_word(word: str, *, first: bool) -> str:
    if word.upper() in ACRONYMS:
        return word.upper()
    if word.lower() in _MINOR_WORDS and not first:
        return word.lower()
    return word[:1].upper() + word[1:] if word.islower() else word


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _trim(lines: list[str]) -> list[str]:
    """At most three, no repeats: a tile has room for three short facts, not a report."""
    return list(dict.fromkeys(line for line in lines if line))[:_MAX_LINES]
