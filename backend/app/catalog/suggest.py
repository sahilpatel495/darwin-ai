"""Starter questions built from the schema by template, so every one is answerable.

Why templates and not a model: a first-time user judges the product by the first question
they click. It has to work, it has to be free, and it must not be able to carry hostile
text. Column wording therefore comes from the normalised column name (which the model sees
anyway), never from raw header text, and PII columns are never mentioned.
"""

from __future__ import annotations

import re
from itertools import chain, zip_longest

from app.catalog.glossary import match_metrics
from app.contracts import Catalog, ColumnProfile, TableProfile

_AVERAGED_ROLES = ("ctc", "rating")  # adding up CTCs or ratings across people means little
_MEASURE_ROLES = ("gross", "net", "ctc", "amount", "bonus", "basic", "deductions", "quantity",
                  "days_absent", "days_present", "lop_days", "paid_days", "working_days", "rating")
_TREND_DATE_ROLES = ("pay_month", "date")  # transaction dates; a joining date is not a time axis
_FALLBACK_NAME = re.compile(r"^column_\d+$")  # ingest's name for a header it could not use
_ACRONYMS = {"ctc", "lop", "hra", "pf", "esi", "tds"}  # read as "CTC" whatever the export's casing


def _phrase(col: ColumnProfile) -> str:
    """The column in the user's words. The label's casing is kept ("CTC", "LOP days") only
    when the label is the column name spelled differently, so no new text can ride along."""
    words = re.findall(r"[A-Za-z0-9]+", col.label)
    if "_".join(w.lower() for w in words) != col.name:
        words = col.name.split("_")
    return " ".join(w.upper() if w.lower() in _ACRONYMS or (w.isupper() and len(w) <= 4) else w.lower() for w in words)


def _usable(col: ColumnProfile) -> bool:
    return not col.pii and not col.is_identifier and not _FALLBACK_NAME.match(col.name)


def _rank(measure: ColumnProfile) -> int:
    """Pay before attendance before anything unrecognised: the question people came to ask."""
    return _MEASURE_ROLES.index(measure.role) if measure.role in _MEASURE_ROLES else len(_MEASURE_ROLES)


def _measures(table: TableProfile) -> list[ColumnProfile]:
    """Columns worth adding up or averaging, best first. A bare integer with no role is left
    out: it is as likely a year or a pin code as a quantity."""
    found = [c for c in table.columns if _usable(c)
             and (c.role in _MEASURE_ROLES or (c.role is None and c.type in ("currency", "decimal", "percent")))]
    return sorted(found, key=_rank)


def _best_first(ranked: list[tuple[int, str]]) -> list[str]:
    return [question for _, question in sorted(ranked, key=lambda pair: pair[0])]


def _categories(table: TableProfile) -> list[ColumnProfile]:
    """Text columns with a handful of known values, those with a recognised role first."""
    found = [c for c in table.columns if _usable(c) and c.type == "text" and c.values and 2 <= len(c.values) <= 30]
    return sorted(found, key=lambda c: c.role is None)


def _total_or_average(measure: ColumnProfile) -> str:
    kind = "average" if measure.role in _AVERAGED_ROLES or measure.type == "percent" else "total"
    return f"{kind} {_phrase(measure)}"


def _metric_questions(catalog: Catalog) -> list[str]:
    tables = [t for t in catalog.tables if not t.is_view]
    exits = next((c for t in tables for c in t.columns if c.role == "exit_date" and c.max), None)
    department = next((c for t in tables for c in t.columns if c.role == "department" and _usable(c)), None)
    candidates = [
        f"What was the attrition rate in {exits.max[:4]}?" if exits else "",
        f"What is the headcount by {_phrase(department)}?" if department else "What is the current headcount?",
        "What is the gender ratio?", "What is the absenteeism rate?", "What is the rating distribution?",
        "What is the average span of control?", "What is the average tenure?", "What is the LOP percentage?",
    ]
    # Only offer a metric this data can actually compute (all of its columns are present).
    return [q for q in candidates if q and any(not m.missing_roles for m in match_metrics(q, catalog))]


def _cross_file_questions(catalog: Catalog) -> list[str]:
    """A measure from the "many" side broken down by a category from the "one" side. N:M links
    are skipped: they are the fan-out trap, not something to invite the user into."""
    tables = {t.name: t for t in catalog.tables}
    questions = []
    for link in catalog.relationships:
        if link.status != "active" or link.cardinality == "N:M":
            continue
        one, many = (link.left_table, link.right_table) if link.cardinality != "N:1" else (link.right_table, link.left_table)
        measures, categories = _measures(tables[many]), _categories(tables[one])
        if measures and categories:
            questions.append((_rank(measures[0]), f"What is the {_total_or_average(measures[0])} by {_phrase(categories[0])}?"))
    return _best_first(questions)


def _trend_questions(tables: list[TableProfile]) -> list[str]:
    return _best_first([(_rank(_measures(t)[0]), f"How has the {_total_or_average(_measures(t)[0])} changed month by month?")
                        for t in tables if _measures(t) and any(c.role in _TREND_DATE_ROLES for c in t.columns)])


def _breakdown_questions(tables: list[TableProfile]) -> list[str]:
    questions = []
    for table in tables:
        measures, categories = _measures(table), _categories(table)
        if measures and categories:
            questions.append((_rank(measures[0]), f"What is the {_total_or_average(measures[0])} by {_phrase(categories[0])}?"))
        if measures and len(categories) > 1:
            questions.append((_rank(measures[0]), f"Which {_phrase(categories[1])} has the highest {_total_or_average(measures[0])}?"))
    return _best_first(questions)


def _union_questions(catalog: Catalog) -> list[str]:
    views = {t.name: t for t in catalog.tables if t.is_view}
    questions = []
    for union in catalog.unions:
        measures = _measures(views[union.view_name]) if union.view_name in views else []
        if measures:
            files = re.sub(r"(_all)?(_\d+)?$", "", union.view_name).replace("_", " ")  # attendance_all -> attendance
            questions.append(f"What is the {_total_or_average(measures[0])} in each of the {len(union.tables)} {files} files?")
    return questions


def _count_questions(tables: list[TableProfile]) -> list[str]:
    """Counting needs no amounts and no dates, so even a bare roster (an id and a department)
    gives a first-time user something to click rather than an empty page."""
    questions = []
    for table in tables:
        is_roster = any(c.role == "employee_id" and c.is_unique for c in table.columns)
        if categories := _categories(table):
            questions.append(f"How many {'employees' if is_roster else 'rows'} are there in each {_phrase(categories[0])}?")
    return questions


def suggest_questions(catalog: Catalog, limit: int = 6) -> list[str]:
    """Deterministic templates over roles/types (measure by category, trend over a date,
    a cross-file question when an active relationship exists, a glossary metric when its
    roles are present). No LLM call.

    The first question of each kind comes before the second of any kind, so six chips show
    the product's range rather than six breakdowns.
    """
    base = [t for t in catalog.tables if not t.is_view]
    kinds = [_metric_questions(catalog), _cross_file_questions(catalog), _trend_questions(base),
             _breakdown_questions(base), _union_questions(catalog), _count_questions(base)]
    in_turn = [q for q in chain.from_iterable(zip_longest(*kinds)) if q]
    return list(dict.fromkeys(in_turn))[:limit]
