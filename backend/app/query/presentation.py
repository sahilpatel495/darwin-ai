"""Turn a result into what the user sees: display strings and a chart spec. Rules only.

Why rules and not the model: the same result must always look the same, a unit must never be
guessed (a headcount shown in rupees is worse than a bare number), and the narrator can only
copy numbers, so every number has to be formatted here before any model sees it.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import pairwise
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import traverse_scope

from app.contracts import Catalog, ChartSpec, ResultTable
from app.query.executor import ExecResult
from app.query.guard import GuardedQuery

ValueKind = str  # "currency" | "percent" | "integer" | "decimal" | "date" | "text"

MAX_BARS = 12  # the frontend draws the first 12 rows of a bar chart
MAX_SERIES = 8  # more colours than this cannot be told apart in a grouped bar

_MEASURES = {"currency", "percent", "integer", "decimal"}
_VALUE_FORMATS = {"currency": "currency_inr", "percent": "percent"}
_INTEGER_TYPES = {"TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
                  "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT"}
_UNITLESS = (exp.Count, exp.CountIf, exp.ApproxDistinct, exp.Corr)  # a number of rows or a coefficient, never rupees
_LAKH, _CRORE = Decimal(100_000), Decimal(10_000_000)
_TITLE_FILLER = re.compile(
    r"^(?:please\s+)?(?:(?:can|could)\s+you\s+)?"
    r"(?:what(?:['’]s|\s+is|\s+are|\s+was|\s+were)|show(?:\s+me)?|give\s+me|tell\s+me|list)\s+(?:the\s+)?",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- column kinds


def column_kinds(result: ExecResult, query: GuardedQuery, catalog: Catalog) -> list[ValueKind]:
    """currency when a source column is currency and the aggregate is not COUNT; percent when
    the alias ends with _pct (prompt convention); else from the DuckDB type.

    Two additions the analyst would otherwise trip over: a source column ingested as a
    percentage stays a percentage, and a whole-number column the rows are grouped by (a year,
    a rating) is a label, so it is never shown as "2,025" or plotted as a measure."""
    source = [c for t in catalog.tables if t.name in query.tables for c in t.columns]
    tree = _parse(query.sql)
    rupees = _inherits_unit(result, tree, {c.name for c in source if c.type == "currency"})
    percent = _inherits_unit(result, tree, {c.name for c in source if c.type == "percent"})
    group_keys = _group_keys(result, tree)

    kinds: list[ValueKind] = []
    for i, (name, duck_type) in enumerate(zip(result.columns, result.duck_types, strict=True)):
        kind = _kind_from_duck_type(duck_type)
        if kind in ("integer", "decimal"):
            if name.lower().endswith("_pct") or percent[i]:
                kind = "percent"
            elif rupees[i]:
                kind = "currency"
            elif kind == "integer" and (group_keys[i] or _is_year_column(name, [row[i] for row in result.rows])):
                kind = "text"
        kinds.append(kind)
    return kinds


def _kind_from_duck_type(duck_type: str) -> ValueKind:
    name = duck_type.upper()
    if name.startswith(("DATE", "TIMESTAMP")):
        return "date"
    if name in _INTEGER_TYPES:
        return "integer"
    if name.startswith(("DECIMAL", "NUMERIC")) or name in {"DOUBLE", "FLOAT", "REAL"}:
        return "decimal"
    return "text"  # VARCHAR, BOOLEAN (shown as Yes/No) and anything exotic


def _parse(sql: str) -> exp.Query | None:
    """The guard already accepted this SQL; it is re-read here only to see which output column
    came from where. If it cannot be read, callers fall back to column names."""
    try:
        tree = sqlglot.parse_one(sql, read="duckdb")
    except SqlglotError:
        return None
    return tree if isinstance(tree, exp.Query) else None


def _projections(result: ExecResult, tree: exp.Query | None) -> list[exp.Expression] | None:
    """The final SELECT's expressions, one per result column; None for SELECT * or a mismatch."""
    if tree is None:
        return None
    projections = tree.selects
    if len(projections) != len(result.columns) or any(p.is_star for p in projections):
        return None
    return projections


def _inherits_unit(result: ExecResult, tree: exp.Query | None, source_names: set[str]) -> list[bool]:
    """Which result columns are amounts in the unit of the source columns called `source_names`?

    CTEs and subqueries are visited innermost first, so `sum(gross) AS paid` inside a CTE makes
    `paid` an amount before the outer query uses it."""
    # ponytail: units are tracked by column name, not table.column. Ceiling: two same-named
    # columns with different units in one query. Upgrade path: sqlglot.lineage per projection.
    names = {n.lower() for n in source_names}
    by_name = [c.lower() in names for c in result.columns]
    if not names or tree is None:
        return by_name
    try:
        for scope in traverse_scope(tree):
            for projection in scope.expression.selects:
                if _is_amount(projection, names):
                    names.add(projection.alias_or_name.lower())
    except SqlglotError:
        return by_name
    projections = _projections(result, tree)
    if projections is None:
        return [c.lower() in names for c in result.columns]
    return [_is_amount(p, names) for p in projections]


def _is_amount(node: exp.Expression, names: set[str]) -> bool:
    """Does this expression evaluate to an amount of what the columns in `names` measure?

    A count of payslips is not money, nor is a correlation with pay, a comparison
    (`gross > 100000`) is not money, a window's ORDER BY is not its value, and money divided by
    money is a ratio. Everything else that touches a money column (sum, avg, round, coalesce,
    CASE ... THEN gross) still is."""
    if isinstance(node, exp.Column):
        return node.name.lower() in names
    if isinstance(node, (*_UNITLESS, exp.Predicate)):
        return False
    if isinstance(node, exp.Div):
        return _is_amount(node.left, names) and not _is_amount(node.right, names)
    if isinstance(node, exp.Window):
        return _is_amount(node.this, names)
    if isinstance(node, exp.Query):
        return any(_is_amount(p, names) for p in node.selects)
    return any(_is_amount(child, names) for child in node.iter_expressions())


def _group_keys(result: ExecResult, tree: exp.Query | None) -> list[bool]:
    """In a GROUP BY query, a column with no aggregate in it is what the rows are grouped by."""
    projections = _projections(result, tree)
    if projections is None or not isinstance(tree, exp.Select) or not tree.args.get("group"):
        return [False] * len(result.columns)
    return [p.find(exp.AggFunc) is None for p in projections]


def _is_year_column(name: str, values: list[Any]) -> bool:
    """Backstop for a year that reaches the final SELECT through a CTE, where it no longer
    looks like a group key: named like a year and every value is a plausible year."""
    if name.lower().split("_")[-1] not in {"year", "yr", "fy"}:
        return False
    return all(v is None or (isinstance(v, int) and 1900 <= v <= 2100) for v in values)


# --------------------------------------------------------------------------- display strings


def to_display(value: Any, kind: ValueKind) -> str:
    """Indian formatting: 1234567 -> "12,34,567"; currency -> "₹12.35 L" / "₹1.20 Cr" from
    1 lakh up, else "₹45,000"; percent -> "12.5%"; dates -> "04 Apr 2025"; None -> "—".

    Never raises: a value that does not fit its kind is shown as plain text."""
    if value is None or (isinstance(value, (float, Decimal)) and not math.isfinite(value)):
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):  # before `date`: a datetime is also a date
        return value.strftime("%d %b %Y" if value.time() == time.min else "%d %b %Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    if kind == "date":
        return _iso_text_as_date(str(value))
    if kind not in _MEASURES or not isinstance(value, (int, float, Decimal)):
        return str(value)

    try:
        return _number(Decimal(str(value)), kind)
    except InvalidOperation:  # more digits than Decimal's default precision, e.g. 1e30
        return str(value)


def _number(number: Decimal, kind: ValueKind) -> str:
    if kind == "currency":
        return _rupees(number)
    if kind == "percent":
        return _plain(number, 1) + "%"
    if kind == "integer" and number == number.to_integral_value():
        return _plain(number, 0)
    # Two decimals, except for a small rate such as 0.0045, which must not be shown as 0. Anything
    # below one in a billion is floating-point dust (0.1 + 0.2 - 0.3 is 5.6e-17) and does read as 0.
    is_small_rate = Decimal("1e-9") <= abs(number) < Decimal("0.01")
    return _plain(number, 1 - number.adjusted() if is_small_rate else 2, trim=True)


def _iso_text_as_date(text: str) -> str:
    try:
        return date.fromisoformat(text[:10]).strftime("%d %b %Y")
    except ValueError:
        return text


def _plain(number: Decimal, places: int, *, trim: bool = False) -> str:
    """Round half up (what a person checking with a calculator expects; Python's round() is
    banker's rounding), then group digits the Indian way."""
    rounded = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    whole, _, fraction = f"{abs(rounded):f}".partition(".")
    if trim:
        fraction = fraction.rstrip("0")
    sign = "-" if rounded < 0 else ""
    return sign + _group_indian(whole) + (f".{fraction}" if fraction else "")


def _group_indian(digits: str) -> str:
    """'1234567' -> '12,34,567': the last three digits, then pairs."""
    head, tail = digits[:-3], digits[-3:]
    pairs = re.findall(r"\d{1,2}(?=(?:\d{2})*$)", head)
    return ",".join([*pairs, tail])


def _rupees(number: Decimal) -> str:
    """Below 1 lakh the exact amount; from 1 lakh up two decimals of lakh or crore, which is how
    Indian payroll figures are read aloud. The exact value stays in the table's raw rows."""
    rupees = abs(number).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if number < 0 and rupees else ""
    if rupees < _LAKH:
        return f"{sign}₹{_plain(rupees, 2, trim=rupees == rupees.to_integral_value())}"
    lakhs = (rupees / _LAKH).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if lakhs < 100:  # 99,99,999 rounds to 100.00 L, which must read as 1.00 Cr
        return f"{sign}₹{lakhs} L"
    return f"{sign}₹{_plain(rupees / _CRORE, 2)} Cr"


def _json_safe(value: Any) -> Any:
    """What goes in `rows`: only scalars every JSON encoder and the frontend agree on."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (float, Decimal)):
        return float(value) if math.isfinite(value) else None  # NaN is not valid JSON
    if isinstance(value, datetime) and value.time() == time.min:
        return value.date().isoformat()  # date_trunc returns midnight timestamps; charts want dates
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)  # intervals, lists, structs, UUIDs: readable text, never a crash


def build_table(result: ExecResult, kinds: list[ValueKind]) -> ResultTable:
    """Raw JSON-safe values for charts and export, and a parallel grid of display strings, which
    are the only form of a number the narrator is ever given."""
    return ResultTable(
        columns=list(result.columns),
        rows=[[_json_safe(v) for v in row] for row in result.rows],
        display=[[to_display(v, k) for v, k in zip(row, kinds, strict=True)] for row in result.rows],
        row_count=len(result.rows),
        truncated=result.truncated,
    )


# --------------------------------------------------------------------------- chart


def choose_chart(table: ResultTable, kinds: list[ValueKind], question: str) -> ChartSpec:
    """1x1 -> kpi; date + measure(s) -> line; category + measure: <= 12 groups -> sorted bar,
    more -> top 12 bar with a note; 2 categories + measure -> grouped_bar; 2 measures ->
    scatter; otherwise table.

    A single row with several columns is also a kpi, headlining its last measure, because
    metric queries end with the figure that was asked for (exits, avg_headcount, attrition_pct).
    `value_format` describes the values in `y`."""
    kind_of = dict(zip(table.columns, kinds, strict=True))
    measures = [c for c in table.columns if kind_of[c] in _MEASURES]
    dates = [c for c in table.columns if kind_of[c] == "date"]
    labels = [c for c in table.columns if kind_of[c] == "text"]

    def spec(chart_type: str, y: list[str], **fields: Any) -> ChartSpec:
        value_format = _VALUE_FORMATS.get(kind_of[y[0]], "number") if y else "number"
        return ChartSpec(type=chart_type, y=y, title=_title(question), value_format=value_format, **fields)

    # A chart names its columns, so two columns with one name (SELECT count(*), count(*)) cannot be drawn.
    if not table.rows or not measures or len(set(table.columns)) < len(table.columns):
        return spec("table", [])
    if len(table.rows) == 1:
        return spec("kpi", measures[-1:])
    if len(dates) == 1 and not labels:
        return spec("line", measures, x=dates[0])
    if len(labels) == 1 and not dates and len(measures) == 1:
        return spec("bar", measures, x=labels[0], note=_bar_note(table, table.columns.index(measures[0])))
    if labels and len(labels) + len(dates) == 2 and len(measures) == 1:
        x, series = [c for c in table.columns if c in labels or c in dates]
        if _distinct(table, x) <= MAX_BARS and _distinct(table, series) <= MAX_SERIES:
            return spec("grouped_bar", measures, x=x, series=series)
        return spec("table", [], note="There are too many groups to chart clearly, so this is shown as a table.")
    if len(measures) == 2 and not labels and not dates:
        return spec("scatter", measures[1:], x=measures[0])
    return spec("table", [])


def _distinct(table: ResultTable, column: str) -> int:
    index = table.columns.index(column)
    return len({row[index] for row in table.rows})


def _bar_note(table: ResultTable, measure_index: int) -> str | None:
    """Say what the chart leaves out, and only claim "top" when the rows really are sorted."""
    if len(table.rows) <= MAX_BARS:
        return None
    values = [row[measure_index] for row in table.rows if row[measure_index] is not None]
    which = "top" if all(a >= b for a, b in pairwise(values)) else "first"
    count = to_display(table.row_count, "integer")
    if table.truncated:
        return f"Showing the {which} {MAX_BARS} of more than {count} groups. The table has the first {count}."
    return f"Showing the {which} {MAX_BARS} of {count} groups. The table has all of them."


def _title(question: str) -> str:
    """The question as a one-line chart title: no filler opening, no question mark, max 80 chars."""
    text = " ".join(question.split()).rstrip("?.! ")
    text = _TITLE_FILLER.sub("", text, count=1) or text
    text = text[:1].upper() + text[1:]
    return text if len(text) <= 80 else text[:79].rstrip() + "…"
