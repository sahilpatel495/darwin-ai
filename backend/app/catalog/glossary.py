"""HR semantic layer: vetted metric definitions and deterministic ambiguity detection.

Why: "attrition" and "salary" have precise, contested meanings. Left alone, a model picks
one silently and the number cannot be defended in front of a CHRO. Here each metric has one
written definition and one SQL pattern, bound to whatever this customer called the columns,
and a word that could mean several columns becomes a one-click question instead of a guess.

Pattern syntax: {role} becomes table.column and {role@table} becomes the table. Dates the
question must supply are written DATE '<period_start>': if a model forgets to fill one in,
DuckDB refuses the query and the repair loop fixes it. A pattern with a real example date
would instead run happily and answer for the wrong period.

Conventions a reviewer should know:
- Headcount on a day D counts people who joined on or before D and whose exit date is
  empty or after D. Someone whose last day is D is not in the headcount of D.
- Attrition's opening headcount is the headcount on the day before the period starts, so
  one period's closing number is the next period's opening number.
- A metric whose columns are missing is returned with `missing_roles` and no hint. The
  pipeline then lets the model answer unaided, which is right for, say, a roster with no
  exit dates: every row in it is a current employee.
"""

from __future__ import annotations

import re

from app.contracts import (
    Catalog,
    Clarification,
    ClarifyOption,
    ColumnProfile,
    Metric,
    ResolvedMetric,
    TableProfile,
)
from app.profile.roles import ROLE_SYNONYMS

DEFAULT_GLOSSARY: list[Metric] = [
    Metric(
        key="headcount", name="Headcount",
        synonyms=["head count", "employee count", "active employees", "current employees",
                  "total employees", "employee strength", "staff strength", "workforce size"],
        definition="Headcount on a date is the number of employees who had joined on or before that date "
                   "and had not left by it. When no date is given, today is used.",
        required_roles=["join_date", "exit_date"],
        sql_pattern="SELECT count(*) AS headcount FROM {join_date@table} WHERE {join_date} <= DATE '<as_of_date>' "
                    "AND ({exit_date} IS NULL OR {exit_date} > DATE '<as_of_date>') "
                    "/* replace DATE '<as_of_date>' with the date asked about, or with current_date if none */",
    ),
    Metric(
        key="attrition_rate", name="Attrition rate",
        synonyms=["attrition", "attrition percentage", "employee turnover", "staff turnover", "turnover rate"],
        definition="Attrition rate for a period is 100 × the number of employees who left in the period ÷ the "
                   "average of the headcount at the start and at the end of the period. A rate for one month "
                   "can be annualised by multiplying it by 12; the answer must say so when that is done.",
        required_roles=["join_date", "exit_date"],
        sql_pattern="WITH period AS (SELECT DATE '<period_start>' AS first_day, DATE '<period_end>' AS last_day) "
                    "SELECT round(100.0 * count(*) FILTER (WHERE {exit_date} BETWEEN first_day AND last_day) / nullif(("
                    "count(*) FILTER (WHERE {join_date} < first_day AND ({exit_date} IS NULL OR {exit_date} >= first_day)) + "
                    "count(*) FILTER (WHERE {join_date} <= last_day AND ({exit_date} IS NULL OR {exit_date} > last_day))"
                    ") / 2.0, 0), 1) AS attrition_rate_pct FROM {join_date@table}, period",
    ),
    Metric(
        key="early_attrition", name="Early attrition",
        synonyms=["early attrition rate", "infant attrition", "new hire attrition", "new joiner attrition",
                  "first year attrition"],
        definition="Early attrition is the share of the employees who joined in a period that left within "
                   "12 months of their own joining date: 100 × those early leavers ÷ all joiners in the period.",
        required_roles=["join_date", "exit_date"],
        sql_pattern="SELECT round(100.0 * count(*) FILTER (WHERE {exit_date} < {join_date} + INTERVAL 12 MONTH) "
                    "/ nullif(count(*), 0), 1) AS early_attrition_pct FROM {join_date@table} "
                    "WHERE {join_date} BETWEEN DATE '<cohort_start>' AND DATE '<cohort_end>'",
    ),
    Metric(
        key="avg_tenure", name="Average tenure",
        synonyms=["tenure", "avg tenure", "average length of service", "length of service", "average service"],
        definition="Average tenure is the average time, in years, from an employee's joining date to their exit "
                   "date, or to today for employees who are still with the company.",
        required_roles=["join_date", "exit_date"],
        sql_pattern="SELECT round(avg(date_diff('day', {join_date}, coalesce({exit_date}, current_date))) / 365.25, 1) "
                    "AS avg_tenure_years FROM {join_date@table}",
    ),
    Metric(
        key="gender_ratio", name="Gender ratio",
        synonyms=["gender diversity", "gender split", "gender mix", "gender distribution", "diversity ratio",
                  "male to female ratio"],
        definition="Gender ratio is each gender's share of current employees, as a percentage of the current "
                   "employees whose gender is recorded.",
        required_roles=["gender", "exit_date"],
        sql_pattern="SELECT {gender} AS gender, count(*) AS employees, "
                    "round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct FROM {gender@table} "
                    "WHERE {gender} IS NOT NULL AND ({exit_date} IS NULL OR {exit_date} > current_date) "
                    "GROUP BY 1 ORDER BY employees DESC, gender",
    ),
    Metric(
        key="absenteeism_rate", name="Absenteeism rate",
        synonyms=["absenteeism", "absenteeism percentage", "absence rate", "absent rate"],
        definition="Absenteeism rate is 100 × days absent ÷ working days, over the same employees and period.",
        required_roles=["days_absent", "working_days"],
        sql_pattern="SELECT round(100.0 * sum({days_absent}) / nullif(sum({working_days}), 0), 1) "
                    "AS absenteeism_rate_pct FROM {days_absent@table}",
    ),
    Metric(
        key="lop_pct", name="LOP %",
        synonyms=["lop percentage", "lop percent", "lop pct", "lop rate", "loss of pay %",
                  "loss of pay percentage", "loss of pay rate"],
        definition="LOP % is 100 × loss-of-pay days ÷ paid days, over the same employees and period.",
        required_roles=["lop_days", "paid_days"],
        sql_pattern="SELECT round(100.0 * sum({lop_days}) / nullif(sum({paid_days}), 0), 1) AS lop_pct "
                    "FROM {lop_days@table}",
    ),
    Metric(
        key="avg_ctc", name="Average CTC",
        synonyms=["avg ctc", "mean ctc", "average cost to company", "average annual ctc"],
        definition="Average CTC is the average annual cost to company over everyone in the data who has a CTC "
                   "on record. People with no CTC recorded are left out, not counted as zero.",
        required_roles=["ctc"],
        sql_pattern="SELECT round(avg({ctc}), 0) AS avg_ctc FROM {ctc@table}",
    ),
    Metric(
        key="rating_distribution", name="Rating distribution",
        synonyms=["ratings distribution", "distribution of ratings", "performance distribution",
                  "performance rating distribution", "bell curve"],
        definition="Rating distribution is the number of reviews at each rating and each rating's share of "
                   "all reviews that have a rating.",
        required_roles=["rating"],
        sql_pattern="SELECT {rating} AS rating, count(*) AS reviews, "
                    "round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct FROM {rating@table} "
                    "WHERE {rating} IS NOT NULL GROUP BY 1 ORDER BY 1",
    ),
    Metric(
        key="span_of_control", name="Span of control",
        synonyms=["average span of control", "average team size", "direct reports per manager",
                  "reportees per manager", "team size per manager"],
        definition="Span of control is the average number of direct reports per manager, counting only "
                   "people who have at least one direct report as managers.",
        required_roles=["manager_id", "employee_id"],
        sql_pattern="SELECT round(avg(direct_reports), 1) AS avg_span_of_control FROM ("
                    "SELECT {manager_id} AS manager, count(DISTINCT {employee_id}) AS direct_reports "
                    "FROM {manager_id@table} WHERE {manager_id} IS NOT NULL GROUP BY 1) AS managers",
    ),
]

# term -> roles it could mean. "salary" is the canonical example.
AMBIGUOUS_TERMS: dict[str, list[str]] = {
    "salary": ["ctc", "gross", "net", "basic"],
    "pay": ["ctc", "gross", "net"],
    "compensation": ["ctc", "gross"],
    "earnings": ["gross", "net"],
}

# Roles that name one pay component outright. "How much did we pay out in bonuses?" is about
# bonuses: "pay" there is a verb, not a column to choose, so no chips are offered.
_NAMED_COMPONENTS = ("bonus", "deductions")

_ROLE_LABELS = {"ctc": "CTC, annual", "gross": "Gross pay", "net": "Net pay, take-home", "basic": "Basic pay"}
_PLACEHOLDER = re.compile(r"\{(\w+)(@table)?\}")


def _mentions(text: str, phrase: str) -> list[tuple[int, int]]:
    """Where `phrase` appears in `text` as whole words, the way people type it: plural
    ("salaries", "attrition rates"), hyphenated ("head-count") or run together ("LOP%").
    Whole words only, so "payment" never counts as "pay"."""
    words = phrase.lower().split()
    if not words or len(phrase.strip()) < 2:
        return []  # a blank synonym in a user-edited glossary must not match everything
    *head, last = words
    ending = re.escape(last) + "(?:s|es)?"
    if last.endswith("y"):
        ending = f"(?:{ending}|{re.escape(last[:-1])}ies)"
    pattern = r"(?<!\w)" + r"[\s\-]*".join([*map(re.escape, head), ending]) + r"(?!\w)"
    return [m.span() for m in re.finditer(pattern, text.lower())]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def _binds(column: ColumnProfile, role: str) -> bool:
    """A column can stand for a role only if it has values in it.

    A header with nothing under it is kept as an empty column (ingest says so in the
    receipt), and "LWD" on the sheet of people who have not left is exactly that. Bound to
    exit_date it satisfies the attrition metric on paper, and a session holding only that
    sheet then answers "attrition is 0%" — a refusal turned into a number. Ignored, the
    metric comes back with exit_date missing and the app refuses and names it.
    """
    return column.role == role and column.distinct_count > 0


def _column_with_role(table: TableProfile, role: str) -> ColumnProfile | None:
    return next((c for c in table.columns if _binds(c, role)), None)


def _resolve(metric: Metric, catalog: Catalog) -> ResolvedMetric:
    """Bind each role the metric needs to one real column of ONE table: the table covering
    the most required roles, a union view winning a tie because it holds the whole dataset
    rather than one quarter of it.

    One table, not the best column wherever it lives, because every pattern has a single
    {role@table} and therefore a single FROM. Reaching into a second table for the roles the
    first one lacks wrote `count(DISTINCT staff_master_all.emp_no) ... FROM stores`, which
    DuckDB refuses to bind — and the model was handed it as the vetted definition. A role
    the chosen table does not have is reported missing, which is the truth: these files
    cannot compute that metric, and the app should say so rather than half-write it.
    """
    in_pattern = [role for role, _ in _PLACEHOLDER.findall(metric.sql_pattern)]
    needed = list(dict.fromkeys([*metric.required_roles, *in_pattern]))
    ranked = sorted(catalog.tables, key=lambda t: (
        -sum(_column_with_role(t, r) is not None for r in metric.required_roles),
        -sum(_column_with_role(t, r) is not None for r in needed),
        not t.is_view))

    bindings: dict[str, str] = {}
    for table in ranked[:1]:  # empty catalog: nothing binds and every role is missing
        for role in needed:
            if column := _column_with_role(table, role):
                bindings[role] = f"{table.name}.{column.name}"
    missing = [role for role in needed if role not in bindings]

    def fill(match: re.Match[str]) -> str:
        bound = bindings[match.group(1)]
        return bound.split(".")[0] if match.group(2) else bound

    return ResolvedMetric(metric=metric, bindings=bindings, missing_roles=missing,
                          sql_hint="" if missing else _PLACEHOLDER.sub(fill, metric.sql_pattern))


def match_metrics(question: str, catalog: Catalog) -> list[ResolvedMetric]:
    """Metrics whose name or a synonym appears in the question (case-insensitive, word
    boundaries), each bound to this session's columns via ColumnProfile.role. A metric whose
    required roles are absent is still returned, with `missing_roles` set and sql_hint "".

    When one metric's phrase sits inside another's ("attrition" inside "early attrition"),
    only the more specific metric is returned, so the model gets one definition, not two.
    """
    spans = {m.key: [s for phrase in (m.name, *m.synonyms) for s in _mentions(question, phrase)]
             for m in catalog.glossary}

    def inside_another(span: tuple[int, int], key: str) -> bool:
        return any(o[0] <= span[0] and span[1] <= o[1] and o != span
                   for other, found in spans.items() if other != key for o in found)

    return [_resolve(m, catalog) for m in catalog.glossary
            if any(not inside_another(span, m.key) for span in spans[m.key])]


# --------------------------------------------------------------------------
# Ambiguity
# --------------------------------------------------------------------------


def _phrases(column: ColumnProfile) -> set[str]:
    """How a user might type a column: 'pay month' for pay_month or for the label 'Pay Month'."""
    return {" ".join(re.findall(r"[a-z0-9]+", text.lower())) for text in (column.name, column.label)} - {""}


def _asks_about(question: str, term: str, catalog: Catalog) -> bool:
    """True when `term` is used on its own: not as part of a table or column name the user
    typed ("pay month", "salary register"), not inside the usual name of something this data
    has ("basic pay" when there is a basic-pay column), and not as the exact name of a column."""
    columns = {p for t in catalog.tables for c in t.columns for p in _phrases(c)}
    if term in columns:
        return False  # the data has a column called exactly "salary": that is what they mean
    roles = {c.role for t in catalog.tables for c in t.columns if c.role}
    names = (columns | {t.name.replace("_", " ") for t in catalog.tables}
             | {header.replace("_", " ") for role in roles for header in ROLE_SYNONYMS.get(role, ())})
    text = question.lower()
    for name in sorted((n for n in names if n != term and _mentions(n, term)), key=len, reverse=True):
        for start, end in reversed(_mentions(text, name)):
            text = text[:start] + " " + text[end:]
    return bool(_mentions(text, term))


def find_ambiguity(
    question: str, catalog: Catalog, clarification: dict[str, str] | None
) -> Clarification | None:
    """Return clarify options when an AMBIGUOUS_TERMS term appears in the question, two or
    more of its candidate roles exist in the data, the question names none of those columns
    or roles explicitly (nor another pay component such as bonuses or deductions), and
    `clarification` does not already resolve the term.

    A clarification only counts when its value is a real "table.column": the pipeline writes
    that value into a prompt, so free text must never pass as a column.
    """
    real_columns = {f"{t.name}.{c.name}" for t in catalog.tables for c in t.columns}
    # A union view stands in for its members, so "gross" is offered once, not once per file.
    stacked = {name for u in catalog.unions if u.status == "active" for name in u.tables}

    for term, roles in AMBIGUOUS_TERMS.items():
        if (clarification or {}).get(term) in real_columns or not _asks_about(question, term, catalog):
            continue
        candidates = [(role, table, column) for role in roles for table in catalog.tables
                      if table.name not in stacked for column in table.columns if _binds(column, role)]
        if len({role for role, _, _ in candidates}) < 2:
            continue
        explicit = {phrase for role, _, column in candidates
                    for phrase in (*_phrases(column), *(s.replace("_", " ") for s in ROLE_SYNONYMS[role]))}
        explicit |= {s.replace("_", " ") for role in _NAMED_COMPONENTS for s in ROLE_SYNONYMS[role]}
        if any(_mentions(question, phrase) for phrase in explicit):
            continue
        return Clarification(
            term=term,
            question=f'"{term.capitalize()}" could mean more than one column in your data. Which one should I use?',
            options=[ClarifyOption(label=f"{_ROLE_LABELS[role]} ({table.name}.{column.name})",
                                   value=f"{table.name}.{column.name}") for role, table, column in candidates])
    return None
