"""Guided analyses: ten questions an analyst can ask by picking columns, with no model.

Why this half of the product exists: the chat path needs a model, and every free model is
rate limited sooner or later. Picking "Average CTC" and "by Department" from two lists asks a
real analytical question with no tokens, no waiting and the same answer every time. It is also
the fastest way to ask: the analyst does not have to guess what wording the app understands.

How a request becomes SQL: `catalog()` publishes the kinds and the columns that may fill each
slot; a request names a kind, a column per input ("employees.ctc") and options picked from
fixed lists. `sqlbuild.resolve` turns each name into the catalog's own spelling and
`sqlbuild.aggregate`/`date_bucket` match the options against allow-lists, so **no string from a
request is ever interpolated into SQL**. The one exception is `compare`, whose two group values
are matched against the column's own distinct values and quoted from the catalog's copy, never
from the request's text. The assembled statement still goes through `app.query.guard` and
`app.query.executor` inside `runner.run_tile`, exactly like a model-written query: one path to
the screen means a number here and the same number in an answer cannot disagree.

Every refusal is one plain sentence naming the input the analyst has to change, because it is
shown next to the picker that caused it.
"""

from __future__ import annotations

from collections.abc import Callable
from math import floor, isfinite, log10
from typing import Any

from app.contracts import Catalog, TableProfile
from app.insights.models import (
    AnalysisCatalog,
    AnalysisInput,
    AnalysisKind,
    AnalysisOption,
    AnalysisRequest,
    ColumnChoice,
    InsightTile,
)
from app.insights.runner import ROW_CAP, run_tile
from app.insights.sqlbuild import (
    Ref,
    _shown,  # the same capped quoting sqlbuild uses when it quotes request text back
    aggregate,
    column_kind,
    date_bucket,
    from_clause,
    ident,
    resolve,
)
from app.query.presentation import ValueKind, to_display
from app.sessions import SessionLike

# A donut stops being readable past a handful of slices, so a share keeps the biggest few and
# adds the rest together. 6 + "Other" is what fits a card without a legend nobody reads.
MAX_SLICES = 6
# Bucket widths a person would choose. A histogram whose bands start at ₹4,17,332 is arithmetic;
# one whose bands start at ₹5 L is a finding.
_NICE_STEPS = (1, 2, 2.5, 5, 10)
# |r| at or above this reads as "strongly"; above _WEAK_CORRELATION as "weakly"; below it the
# honest reading is that the two numbers do not move together at all.
_STRONG_CORRELATION, _WEAK_CORRELATION = 0.7, 0.3
_MEASURE_WORDS = {"sum": "total", "average": "average", "median": "median",
                  "min": "lowest", "max": "highest"}
# presentation picks the same formats from a result's column kinds; a patched chart (see
# _bar_of) has to say it itself.
_VALUE_FORMATS = {"currency": "currency_inr", "percent": "percent"}

_MEASURE = ["measure"]
_CATEGORY = ["category"]
_DATE = ["date"]
_AGGREGATE = AnalysisOption(key="aggregate", label="How to combine",
                            choices=["sum", "average", "count", "median", "min", "max"])

# The ten analyses, in the order the picker shows them. The first nine are mirrored in
# frontend/src/fixtures/analyses.json; `compare` is the tenth. An option with no `choices` is
# filled by the UI from the chosen column's own values (see _group_value).
KINDS: list[AnalysisKind] = [
    AnalysisKind(
        key="breakdown", name="Break down", description="Split one number by a group.",
        example="Average CTC by department",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="by", label="Split by", accepts=_CATEGORY)],
        options=[_AGGREGATE],
    ),
    AnalysisKind(
        key="trend", name="Trend over time",
        description="See how a number moves month by month.", example="Gross pay by month",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="date", label="Over which date", accepts=_DATE),
                AnalysisInput(key="by", label="Separate lines for", accepts=_CATEGORY,
                              optional=True)],
        options=[_AGGREGATE,
                 AnalysisOption(key="grain", label="Every",
                                choices=["month", "quarter", "year", "week"])],
    ),
    AnalysisKind(
        key="top_n", name="Top and bottom", description="Find the highest and lowest groups.",
        example="Top 5 locations by headcount",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="by", label="Rank what", accepts=_CATEGORY)],
        options=[_AGGREGATE,
                 AnalysisOption(key="top_n", label="How many", choices=["5", "10", "20"])],
    ),
    AnalysisKind(
        key="distribution", name="Distribution",
        description="See how values are spread, with the median and the tails.",
        example="How CTC is spread",
        inputs=[AnalysisInput(key="measure", label="Which number", accepts=_MEASURE)],
    ),
    AnalysisKind(
        key="share", name="Share of total",
        description="What part of the whole each group makes up.",
        example="Share of gross pay by department",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="by", label="Split by", accepts=_CATEGORY)],
        options=[_AGGREGATE],
    ),
    AnalysisKind(
        key="pivot", name="Two-way table", description="Cross one group with another.",
        example="Headcount by department and location",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="by", label="Rows", accepts=_CATEGORY),
                AnalysisInput(key="across", label="Columns", accepts=_CATEGORY)],
        options=[_AGGREGATE],
    ),
    AnalysisKind(
        key="correlation", name="Do two numbers move together?",
        description="Compare two measures row by row.", example="CTC against rating",
        inputs=[AnalysisInput(key="measure", label="First number", accepts=_MEASURE),
                AnalysisInput(key="measure_b", label="Second number", accepts=_MEASURE)],
    ),
    AnalysisKind(
        key="change", name="Change between periods",
        description="Compare one period with the one before.",
        example="Gross pay, this month vs last",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="date", label="Over which date", accepts=_DATE),
                AnalysisInput(key="by", label="Split by", accepts=_CATEGORY, optional=True)],
        options=[_AGGREGATE,
                 AnalysisOption(key="grain", label="Compare by",
                                choices=["month", "quarter", "year"])],
    ),
    AnalysisKind(
        key="outliers", name="Unusual values",
        description="List the rows far outside the usual range.",
        example="Unusually high deductions",
        inputs=[AnalysisInput(key="measure", label="Which number", accepts=_MEASURE)],
    ),
    AnalysisKind(
        key="compare", name="Compare two groups",
        description="Put two values of the same column side by side.",
        example="Engineering against Sales on average CTC",
        inputs=[AnalysisInput(key="measure", label="What to measure", accepts=_MEASURE),
                AnalysisInput(key="by", label="Which column", accepts=_CATEGORY)],
        options=[_AGGREGATE,
                 AnalysisOption(key="group_a", label="First group", choices=[]),
                 AnalysisOption(key="group_b", label="Second group", choices=[])],
    ),
]


# --------------------------------------------------------------------------- the two entries


def catalog(session: SessionLike) -> AnalysisCatalog:
    """What can be asked, and which columns can fill each slot.

    Union views are left out: a view holds the same headers as the files it unions, so offering
    both would list "days present" three times and let an analyst combine a file with itself.

    # ponytail: no cross-file attendance in the guided path. Ceiling: "days present across both
    # quarters" has to be asked in the chat. Upgrade path: offer the view instead and drop the
    # base tables' duplicated columns, which is this one condition and nothing else.
    """
    tables = [table for table in session.catalog.tables if not table.is_view]
    columns = []
    for table in tables:
        for profile in table.columns:
            # column_kind forces PII and identifier columns to "text", and no slot accepts free
            # text, so this one check keeps names, emails and employee ids out of every list.
            kind = column_kind(profile)
            if kind == "text":
                continue
            columns.append(ColumnChoice(ref=f"{table.name}.{profile.name}", label=profile.label,
                                        table_label=_table_label(table, tables), kind=kind))
    return AnalysisCatalog(kinds=KINDS, columns=columns)


def run(session: SessionLike, request: AnalysisRequest) -> InsightTile:
    """Assemble, check, run and read one guided analysis, or raise ValueError with a sentence
    naming the input that has to change."""
    kind = next((k for k in KINDS if k.key == request.kind), None)
    if kind is None:
        raise ValueError(f"{_shown(request.kind)} is not an analysis this app can run."
                         f" Choose one of: {', '.join(k.key for k in KINDS)}.")
    refs = _inputs(kind, request, session.catalog)
    return _BUILDERS[kind.key](session, refs, _options(kind, request))


# --------------------------------------------------------------------------- request checking


def _inputs(kind: AnalysisKind, request: AnalysisRequest, known: Catalog) -> dict[str, Ref]:
    """Every declared input resolved against the catalog; an optional one left blank is absent.

    An input the kind does not declare is refused rather than ignored: a request carrying
    `{"by": ...}` for a distribution is a bug or a probe, and silently dropping it would answer
    a different question from the one that was asked.
    """
    declared = {slot.key: slot for slot in kind.inputs}
    for key in request.inputs:
        if key not in declared:
            raise ValueError(f"{_shown(key)} is not something {kind.name} asks for."
                             f" It takes: {', '.join(declared)}.")
    refs = {}
    for key, slot in declared.items():
        ref = request.inputs.get(key, "").strip()
        if not ref:
            if slot.optional:
                continue
            raise ValueError(f"{kind.name} needs a column for “{slot.label}”."
                             " Pick one from the list.")
        refs[key] = resolve(ref, known, tuple(slot.accepts))
    return refs


def _options(kind: AnalysisKind, request: AnalysisRequest) -> dict[str, str]:
    """Every option, defaulted to the first choice and checked against the allow-list.

    An option with no fixed choices (compare's two groups) is passed through as written and
    matched against the column's own values later; it never reaches SQL as written.
    """
    declared = {option.key: option for option in kind.options}
    for key in request.options:
        if key not in declared:
            raise ValueError(f"{_shown(key)} is not something you can choose for {kind.name}."
                             f" It offers: {', '.join(declared) or 'no options'}.")
    picked = {}
    for key, option in declared.items():
        value = request.options.get(key, "").strip()
        if not value:
            if not option.choices:
                raise ValueError(f"Choose a value for “{option.label}”.")
            value = option.choices[0]
        elif option.choices and value not in option.choices:
            raise ValueError(f"{_shown(value)} is not a choice for “{option.label}”."
                             f" Choose one of: {', '.join(option.choices)}.")
        picked[key] = value
    return picked


# --------------------------------------------------------------------------- the ten builders


def _breakdown(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """One number for every value of a category: the question an HR analyst asks first."""
    measure, group = refs["measure"], refs["by"]
    func = options["aggregate"]
    group_name, measure_name = _aliases(group.column, _measure_alias(func, measure))
    sql = (f"SELECT {_col(group)} AS {ident(group_name)},"
           f" {aggregate(func, _col(measure))} AS {ident(measure_name)}"
           f" {from_clause([measure, group], session.catalog)}"
           " GROUP BY 1 ORDER BY 2 DESC, 1")
    phrase, by = _phrase(func, measure), _words(group.profile.label)
    return run_tile(session, tile_id="analysis-breakdown", title=f"{_cap(phrase)} by {by}",
                    kind="breakdown", sql=sql, chart_type="bar",
                    ask=f"How has {phrase} by {by} changed over time?")


def _trend(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """The same number period by period, and one line per group when a group is picked."""
    measure, when, group = refs["measure"], refs["date"], refs.get("by")
    func, grain = options["aggregate"], options["grain"]
    names = _aliases(when.column, *([group.column] if group else []),
                     _measure_alias(func, measure))
    grouped = f", {_col(group)} AS {ident(names[1])}" if group else ""
    sql = (f"SELECT {date_bucket(_col(when), grain)} AS {ident(names[0])}{grouped},"
           f" {aggregate(func, _col(measure))} AS {ident(names[-1])}"
           f" {from_clause([measure, when] + ([group] if group else []), session.catalog)}"
           f" GROUP BY {'1, 2' if group else '1'} ORDER BY {'1, 2' if group else '1'}")
    phrase = _phrase(func, measure)
    split = f", split by {_words(group.profile.label)}" if group else ""
    return run_tile(session, tile_id="analysis-trend", title=f"{_cap(phrase)} by {grain}{split}",
                    # A grouped trend is read across its two groupings; an ungrouped one over time.
                    kind="comparison" if group else "trend", sql=sql, chart_type="line",
                    ask=f"What is behind the change in {phrase}?")


def _top_n(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """The leaders. The statement names the highest and the lowest of the rows shown, which is
    what "top and bottom" means once the list is cut at N."""
    measure, group = refs["measure"], refs["by"]
    func, top = options["aggregate"], int(options["top_n"])  # from a fixed list of numerals
    group_name, measure_name = _aliases(group.column, _measure_alias(func, measure))
    sql = (f"SELECT {_col(group)} AS {ident(group_name)},"
           f" {aggregate(func, _col(measure))} AS {ident(measure_name)}"
           f" {from_clause([measure, group], session.catalog)}"
           f" GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {top}")
    phrase, by = _phrase(func, measure), _words(group.profile.label)
    return run_tile(session, tile_id="analysis-top-n", title=f"Top {top} {_plural(by)} by {phrase}",
                    kind="breakdown", sql=sql, chart_type="bar",
                    ask=f"What is different about the top {by}?")


def _distribution(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """How the values are spread: a histogram over round buckets, read as median and quartiles.

    Two queries. The summary (median, quartiles, ends) decides the bucket width and writes the
    sentence; the histogram draws the shape. They cannot be one query: a median sitting next to
    the bucket counts would make the result a four-measure table, which charts as nothing.
    """
    measure = refs["measure"]
    column, table = _col(measure), ident(measure.table)
    summary = (f"SELECT median({column}) AS {ident('median_' + measure.column)},"
               f" quantile_cont({column}, 0.25) AS {ident('p25_' + measure.column)},"
               f" quantile_cont({column}, 0.75) AS {ident('p75_' + measure.column)},"
               f" min({column}) AS {ident('lowest_' + measure.column)},"
               f" max({column}) AS {ident('highest_' + measure.column)}"
               f" FROM {table}")
    shown, values = _one_row(session, summary)
    median, low, high = values[0], values[3], values[4]
    step = _nice_step(low, high, measure.profile.type == "integer")

    band, count_name = _aliases(f"{measure.column}_band", _measure_alias("count", measure))
    sql = (f"SELECT floor({column} / {step!r}) * {step!r} AS {ident(band)},"
           f" {aggregate('count', column)} AS {ident(count_name)}"
           f" FROM {table} WHERE {column} IS NOT NULL GROUP BY 1 ORDER BY 1")
    label = _words(measure.profile.label)
    tile = run_tile(session, tile_id="analysis-distribution", title=f"How {label} is spread",
                    kind="distribution", sql=sql, chart_type="histogram",
                    ask=f"Who sits in the top 10% of {label}?")
    if None in (median, values[1], values[2]):
        # Nothing but empty cells, or values quantile_cont cannot rank (NaN). run_tile's own
        # sentence is the honest one; "falls between 2 and —" is a sentence with a hole in it.
        return tile
    ends = ([] if None in (values[3], values[4]) else
            [f"The lowest is {shown[3]} and the highest is {shown[4]}."])
    return tile.model_copy(update={
        "statement": (f"Half of {label} falls between {shown[1]} and {shown[2]},"
                      f" and the median is {shown[0]}."),
        "insights": [*ends, *_biggest_band(tile, label)],
    })


def _share(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """What part of the whole each group makes up.

    Past six groups the rest are added together as "Other", so the slices still add up to the
    whole. That is only done for a sum or a count: adding six averages together would produce a
    number that means nothing.

    And when the aggregate is not a sum or a count this stops being a share at all. A donut of
    averages draws six numbers as parts of a whole that does not exist, so the tile becomes what
    it really is — a breakdown, on bars, titled as one. `facts` refuses to compute a share over
    such a column too, so the picture and the sentence agree.
    """
    measure, group = refs["measure"], refs["by"]
    func = options["aggregate"]
    whole = func in ("sum", "count")
    group_name, measure_name = _aliases(group.column, _measure_alias(func, measure))
    totals = (f"SELECT {_col(group)} AS grouped, {aggregate(func, _col(measure))} AS measured"
              f" {from_clause([measure, group], session.catalog)} GROUP BY 1")
    if whole:
        # A group genuinely called "Other" merges with the remainder. The total stays right.
        sql = (f"WITH totals AS ({totals}), ranked AS (SELECT grouped, measured,"
               " row_number() OVER (ORDER BY measured DESC, grouped) AS place FROM totals)"
               f" SELECT CASE WHEN place <= {MAX_SLICES} THEN grouped ELSE 'Other' END"
               f" AS {ident(group_name)}, sum(measured) AS {ident(measure_name)}"
               " FROM ranked GROUP BY 1 ORDER BY 2 DESC, 1")
    else:
        sql = (f"WITH totals AS ({totals}) SELECT grouped AS {ident(group_name)},"
               f" measured AS {ident(measure_name)} FROM totals ORDER BY 2 DESC, 1")
    phrase, by = _phrase(func, measure), _words(group.profile.label)
    # A donut has to show a whole: only a total or a count is one, and only up to six slices.
    donut = whole and group.profile.distinct_count <= MAX_SLICES
    return run_tile(session, tile_id="analysis-share",
                    title=f"Share of {phrase} by {by}" if whole else f"{_cap(phrase)} by {by}",
                    kind="share" if whole else "breakdown", sql=sql,
                    chart_type="donut" if donut else "bar",
                    ask=f"How has the share of {phrase} by {by} moved over time?")


def _pivot(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """One number crossed by two groupings: a heatmap while both sides stay readable."""
    measure, rows, across = refs["measure"], refs["by"], refs["across"]
    if (rows.table, rows.column) == (across.table, across.column):
        raise ValueError("Rows and Columns have to be two different columns."
                         " Pick another column for one of them.")
    func = options["aggregate"]
    row_name, column_name, measure_name = _aliases(rows.column, across.column,
                                                   _measure_alias(func, measure))
    sql = (f"SELECT {_col(rows)} AS {ident(row_name)}, {_col(across)} AS {ident(column_name)},"
           f" {aggregate(func, _col(measure))} AS {ident(measure_name)}"
           f" {from_clause([measure, rows, across], session.catalog)}"
           " GROUP BY 1, 2 ORDER BY 1, 2")
    phrase = _phrase(func, measure)
    down, right = _words(rows.profile.label), _words(across.profile.label)
    # run_tile keeps the rules' chart when there is too much to plot, which is exactly the
    # "else a table" case: too many values on either side and the heatmap becomes unreadable.
    return run_tile(session, tile_id="analysis-pivot", title=f"{_cap(phrase)} by {down} and {right}",
                    kind="comparison", sql=sql, chart_type="heatmap",
                    ask=f"Where is {phrase} highest across {down} and {right}?")


def _correlation(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """Do two numbers move together? corr() over every row; the scatter shows up to 500.

    The coefficient is computed over the whole file, so the sentence is about all of it. Only
    the picture is capped, and the caveat says so.
    """
    first, second = refs["measure"], refs["measure_b"]
    if (first.table, first.column) == (second.table, second.column):
        raise ValueError("Pick two different numbers. A column always moves with itself.")
    source = from_clause([first, second], session.catalog)
    both_present = f"WHERE {_col(first)} IS NOT NULL AND {_col(second)} IS NOT NULL"
    shown, values = _one_row(
        session, f'SELECT corr({_col(first)}, {_col(second)}) AS "correlation",'
                 f' count(*) AS "rows_compared" {source} {both_present}')

    x, y = _aliases(first.column, second.column)
    sql = (f"SELECT {_col(first)} AS {ident(x)}, {_col(second)} AS {ident(y)}"
           f" {source} {both_present} ORDER BY 1, 2 LIMIT {ROW_CAP}")
    one, two = _words(first.profile.label), _words(second.profile.label)
    tile = run_tile(session, tile_id="analysis-correlation", title=f"{one} against {two}",
                    kind="relationship", sql=sql, chart_type="scatter",
                    ask=f"Does {one} still move with {two} within each group?")
    coefficient, compared = values[0], values[1]
    if coefficient is None:
        return tile.model_copy(update={"statement": (
            f"There is not enough variation in {one} or {two} to say whether they move together."
        )})
    insights = ["Moving together is not proof that one causes the other."]
    if compared > ROW_CAP:
        insights.insert(0, f"The chart shows {to_display(ROW_CAP, 'integer')} of"
                           f" {shown[1]} rows; the figure above uses all of them.")
    return tile.model_copy(update={
        "statement": f"{_cap(one)} and {two} {_correlation_words(coefficient)}"
                     f" (correlation {shown[0]} over {shown[1]} rows).",
        "insights": insights,
    })


def _change(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """The last period against the one before it.

    The two periods are found in the data, not from today's date: a file that ends in March is
    asked about March, not about an empty current month. When only one period exists, the
    previous figure is empty rather than zero, and the sentence says so.
    """
    measure, when, group = refs["measure"], refs["date"], refs.get("by")
    func, grain = options["aggregate"], options["grain"]
    periods = (f"SELECT {date_bucket(_col(when), grain)} AS period"
               f"{f', {_col(group)} AS grouped' if group else ''},"
               f" {aggregate(func, _col(measure))} AS measured"
               f" {from_clause([measure, when] + ([group] if group else []), session.catalog)}"
               f" WHERE {_col(when)} IS NOT NULL GROUP BY {'1, 2' if group else '1'}")
    two = (f"SELECT {'grouped, ' if group else ''}"
           " sum(measured) FILTER (WHERE period = (SELECT boundary FROM earlier_period)) AS earlier_value,"
           " sum(measured) FILTER (WHERE period = (SELECT boundary FROM latest_period)) AS later_value"
           f" FROM periods{' GROUP BY 1' if group else ''}")
    head = (f"WITH periods AS ({periods}),"
            " latest_period AS (SELECT max(period) AS boundary FROM periods),"
            " earlier_period AS (SELECT max(period) AS boundary FROM periods"
            " WHERE period < (SELECT boundary FROM latest_period)),"
            f" two AS ({two})")

    measure_name = _measure_alias(func, measure)
    change_name = f"change_in_{measure.column}"
    phrase = _phrase(func, measure)
    if group:
        group_name, change_name, earlier, later = _aliases(
            group.column, change_name, f"previous_{measure_name}", f"current_{measure_name}")
        sql = (f"{head} SELECT grouped AS {ident(group_name)},"
               f" later_value - earlier_value AS {ident(change_name)},"
               f" earlier_value AS {ident(earlier)}, later_value AS {ident(later)}"
               " FROM two ORDER BY 2 DESC, 1")
        tile = run_tile(session, tile_id="analysis-change",
                        title=f"Change in {phrase} by {grain}, split by {_words(group.profile.label)}",
                        # facts reads the first measure, which is why the change column is first.
                        kind="breakdown", sql=sql,
                        ask=f"What changed in {phrase} between the last two {grain}s?")
        return _bar_of(tile, x=group_name, y=change_name, kind=_value_kind(func, measure))

    was, earlier, now, later, change_name = _aliases(
        f"previous_{when.column}", f"previous_{measure_name}",
        f"current_{when.column}", f"current_{measure_name}", change_name)
    sql = (f"{head} SELECT (SELECT boundary FROM earlier_period) AS {ident(was)},"
           f" earlier_value AS {ident(earlier)},"
           f" (SELECT boundary FROM latest_period) AS {ident(now)},"
           f" later_value AS {ident(later)},"
           f" later_value - earlier_value AS {ident(change_name)} FROM two")
    tile = run_tile(session, tile_id="analysis-change", title=f"Change in {phrase} by {grain}",
                    kind="kpi", sql=sql,
                    ask=f"What changed in {phrase} between the last two {grain}s?")
    return tile.model_copy(update=_change_words(tile, phrase, grain, _value_kind(func, measure)))


def _outliers(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """The rows more than 1.5 interquartile ranges outside the middle half — the rule a
    statistician would use and an auditor recognises.

    Personal-data columns are left out of the listing: an unusual salary is a finding, and a
    list of names next to it is a leak.
    """
    measure = refs["measure"]
    column, table = _col(measure), ident(measure.table)
    quartiles = (f"WITH bounds AS (SELECT quantile_cont({column}, 0.25) AS q1,"
                 f" quantile_cont({column}, 0.75) AS q3 FROM {table})")
    low, high = "q1 - 1.5 * (q3 - q1)", "q3 + 1.5 * (q3 - q1)"
    shown, values = _one_row(
        session, f'{quartiles} SELECT {low} AS "lower_bound", {high} AS "upper_bound" FROM bounds')

    profile = next(t for t in session.catalog.tables if t.name == measure.table)
    visible = [f"{table}.{ident(c.name)}" for c in profile.columns if not c.pii]
    # Biggest first, then every other column shown: two rows with the same value must not swap
    # places between two loads of the same file.
    sql = (f"{quartiles} SELECT {', '.join(visible)}"
           f" FROM {table}, bounds WHERE {column} < {low} OR {column} > {high}"
           f" ORDER BY {column} DESC, {', '.join(visible)}")
    label = _words(measure.profile.label)
    tile = run_tile(session, tile_id="analysis-outliers", title=f"Unusual {label} values",
                    kind="distribution", sql=sql, chart_type="table",
                    ask=f"What do the unusual {label} rows have in common?")
    if values[0] is None:
        # Empty, or holding values quantile_cont cannot rank (NaN). Either way there is no
        # range, and "has no values" would be false for the second case.
        return tile.model_copy(update={
            "statement": f"{_cap(label)} could not be checked for unusual values."})
    count = to_display(tile.table.row_count, "integer")
    if not tile.table.rows:
        statement = (f"No {label} value is unusual: they all sit between"
                     f" {shown[0]} and {shown[1]}.")
    else:
        rows = "row" if tile.table.row_count == 1 else "rows"
        statement = (f"{count} {rows} sit outside the usual range for {label}"
                     f" (below {shown[0]} or above {shown[1]}).")
    # `facts` reads a result as groups of something; this one is a list of rows, so its computed
    # lines would call 35 individual salaries "the groups" and offer a share of their sum.
    return tile.model_copy(update={
        "statement": statement,
        "insights": ["Unusual is not the same as wrong: these are the rows worth checking."],
    })


def _compare(session: SessionLike, refs: dict[str, Ref], options: dict[str, str]) -> InsightTile:
    """Two values of one column, side by side, with the gap between them stated."""
    measure, group = refs["measure"], refs["by"]
    func = options["aggregate"]
    first = _group_value(options["group_a"], group)
    second = _group_value(options["group_b"], group)
    if first == second:
        raise ValueError("Pick two different groups to compare.")
    group_name, measure_name = _aliases(group.column, _measure_alias(func, measure))
    sql = (f"SELECT {_col(group)} AS {ident(group_name)},"
           f" {aggregate(func, _col(measure))} AS {ident(measure_name)}"
           f" {from_clause([measure, group], session.catalog)}"
           f" WHERE {_col(group)} IN ({_literal(first)}, {_literal(second)})"
           " GROUP BY 1 ORDER BY 2 DESC, 1")
    phrase = _phrase(func, measure)
    tile = run_tile(session, tile_id="analysis-compare", title=f"{_cap(phrase)}: {first} vs {second}",
                    kind="comparison", sql=sql, chart_type="bar",
                    ask=f"Why is {phrase} different between {first} and {second}?")
    return tile.model_copy(update=_compare_words(tile, first, second,
                                                 _value_kind(func, measure)))


_BUILDERS: dict[str, Callable[[SessionLike, dict[str, Ref], dict[str, str]], InsightTile]] = {
    "breakdown": _breakdown, "trend": _trend, "top_n": _top_n, "distribution": _distribution,
    "share": _share, "pivot": _pivot, "correlation": _correlation, "change": _change,
    "outliers": _outliers, "compare": _compare,
}


# --------------------------------------------------------------------------- sentences


def _correlation_words(coefficient: float) -> str:
    """The coefficient in words. A number between -1 and 1 means nothing to most readers, and
    "0.31" invites a stronger claim than the data supports."""
    strength = abs(coefficient)
    if strength < _WEAK_CORRELATION:
        return "do not move together"
    how = "strongly" if strength >= _STRONG_CORRELATION else "weakly"
    return f"move {'together' if coefficient > 0 else 'in opposite directions'} {how}"


def _change_words(tile: InsightTile, phrase: str, grain: str, kind: ValueKind) -> dict[str, Any]:
    """The one-row change tile in a sentence, from its own display strings."""
    if not tile.table.rows:
        return {}
    shown, values = tile.table.display[0], tile.table.rows[0]
    earlier, change = values[1], values[4]
    if values[2] is None:
        # No latest period means no dated rows at all. The one-period sentence below would name
        # that period, and "There is only one month ... (—)" is a claim about nothing.
        return {"statement": f"No row here has a date, so there are no {grain}s to compare."}
    if earlier is None or change is None:
        return {"statement": f"There is only one {grain} of {phrase} in this data"
                             f" ({shown[2]}), so there is nothing to compare it with."}
    if change == 0:
        return {"statement": f"{_cap(phrase)} is unchanged at {shown[3]}"
                             f" between {shown[0]} and {shown[2]}."}
    moved = to_display(abs(change), kind)
    statement = (f"{_cap(phrase)} went from {shown[1]} in {shown[0]} to {shown[3]} in"
                 f" {shown[2]}, {'up' if change > 0 else 'down'} {moved}.")
    if earlier <= 0:  # "up 300% from minus one lakh" is noise, so the share is left out
        return {"statement": statement}
    share = to_display(abs(100 * change / earlier), "percent")
    moved_by = f"That is {share} {'more' if change > 0 else 'less'} than the {grain} before."
    return {"statement": statement, "insights": [moved_by]}


def _compare_words(tile: InsightTile, first: str, second: str, kind: ValueKind) -> dict[str, Any]:
    """Which group is ahead, and by how much, from the two rows the query returned."""
    rows, shown = tile.table.rows, tile.table.display
    if len(rows) < 2 or rows[0][1] is None or rows[1][1] is None:
        present = shown[0][0] if rows else "neither group"
        return {"statement": f"Only {present} has rows here, so there is nothing to compare."}
    ahead, behind = rows[0], rows[1]
    if ahead[1] == behind[1]:
        return {"statement": f"{first} and {second} are level at {shown[0][1]}."}
    gap = to_display(ahead[1] - behind[1], kind)
    statement = (f"{shown[0][0]} is ahead at {shown[0][1]}, {gap} more than"
                 f" {shown[1][0]} at {shown[1][1]}.")
    if behind[1] <= 0:
        return {"statement": statement}
    share = to_display(100 * (ahead[1] - behind[1]) / behind[1], "percent")
    return {"statement": statement, "insights": [f"That is {share} higher."]}


def _biggest_band(tile: InsightTile, label: str) -> list[str]:
    """Where most of the values sit, read off the histogram's own rows."""
    if not tile.table.rows:
        return []
    top = max(range(len(tile.table.rows)), key=lambda i: tile.table.rows[i][1])
    band, count = tile.table.display[top][0], tile.table.display[top][1]
    return [f"Most {label} values start at {band} ({count} of them)."]


# --------------------------------------------------------------------------- helpers


def _one_row(session: SessionLike, sql: str) -> tuple[list[str], list[Any]]:
    """Run a one-row helper query the same way a tile is run, and return both forms of its
    values: the display strings (the only form a sentence may use, so "₹20.40 Cr" here is
    "₹20.40 Cr" everywhere) and the raw numbers, which decide which sentence gets built.

    A second query rather than extra columns on the tile: the chart is chosen from the result's
    columns, so a median or a correlation sitting beside the rows being drawn would turn every
    histogram and scatter into a table.
    """
    tile = run_tile(session, tile_id="analysis-summary", title="", kind="kpi", sql=sql)
    if not tile.table.rows:  # an aggregate always returns a row; this is a broken template
        raise ValueError("This analysis could not be calculated from your files."
                         " Try it on one file, or ask the question in the chat instead.")
    return tile.table.display[0], tile.table.rows[0]


def _bar_of(tile: InsightTile, *, x: str, y: str, kind: ValueKind) -> InsightTile:
    """Draw one chosen column of a many-column result as a bar.

    The chart rules draw a result that has one measure; a change tile has three (the change and
    the two periods behind it) and would fall back to a table. The change is the column worth
    drawing, and this code knows that because it wrote the SELECT — it is not a guess about
    someone else's columns. Everything else on the tile still comes from run_tile.
    """
    if not tile.table.rows:
        return tile
    chart = tile.chart.model_copy(update={
        "type": "bar", "x": x, "y": [y],
        "value_format": _VALUE_FORMATS.get(kind, "number"),
    })
    return tile.model_copy(update={"chart": chart})


def _col(ref: Ref) -> str:
    """"table"."column", both spellings from the catalog."""
    return f"{ident(ref.table)}.{ident(ref.column)}"


def _literal(value: str) -> str:
    """A single-quoted SQL string. The only values that reach this are the catalog's own copies
    of a column's distinct values (see _group_value), never a request's text."""
    return "'" + value.replace("'", "''") + "'"


def _group_value(text: str, ref: Ref) -> str:
    """One of the column's own values, matched case-insensitively, returned in the catalog's
    spelling. An unmatched value is refused rather than passed through, which is what keeps a
    request's text out of the WHERE clause."""
    values = ref.profile.values
    if values is None:  # the profiler lists values only below its own cap
        raise ValueError(f"{ref.profile.label} has too many different values to compare two of"
                         " them. Pick a column with a short list of values, such as department.")
    if not values:  # listed, and empty: the column is blank in every row
        raise ValueError(f"{ref.profile.label} is empty in every row, so there is nothing to"
                         " compare. Pick a column that has values in it.")
    match = next((value for value in values if value.lower() == text.strip().lower()), None)
    if match is None:
        raise ValueError(f"{_shown(text)} is not a value in {ref.profile.label}."
                         f" Choose one of: {', '.join(values[:6])}.")
    return match


def _aliases(*names: str) -> list[str]:
    """Output names that differ. Two files can use the same header, and a chart cannot name two
    columns the same: choose_chart falls back to a table the moment it sees a repeat."""
    unique: list[str] = []
    for name in names:
        while name in unique:
            name += "_2"
        unique.append(name)
    return unique


def _measure_alias(func: str, ref: Ref) -> str:
    """The output name for an aggregate: total_gross, average_ctc, or the table's name for a
    count, because what a count counts is rows of that table."""
    return ref.table if func == "count" else f"{_MEASURE_WORDS[func]}_{ref.column}"


def _phrase(func: str, ref: Ref) -> str:
    """What the number is, in the analyst's words: "total Gross Pay", "number of employees"."""
    if func == "count":
        return f"number of {_words(ref.table)}"
    return f"{_MEASURE_WORDS[func]} {_words(ref.profile.label)}"


def _value_kind(func: str, ref: Ref) -> ValueKind:
    """How presentation will format this aggregate, for the two sentences that compute a
    difference themselves. A count is a number of rows, never rupees; everything else keeps the
    column's own unit."""
    return "integer" if func == "count" else ref.profile.type


def _nice_step(low: float | None, high: float | None, whole_numbers: bool) -> float:
    """A bucket width a person would choose: 1, 2, 2.5 or 5 times a power of ten, so the bands
    start at round numbers. Ten buckets at most, and never a fraction of a whole-number column.

    A width of 1 is the answer whenever the ends cannot be read. An all-empty column gives no
    ends at all, and a column holding NaN or ±1e308 (a spreadsheet can write both) gives ends
    that are not numbers: log10 of those raises ValueError or OverflowError, neither of which
    is a ValueError carrying a sentence, so they would reach the browser as a 500.
    """
    if low is None or high is None:
        return 1.0
    span = high - low  # -1e308 to 1e308 overflows to inf, so the span is checked, not the ends
    if not isfinite(span) or span <= 0:
        return 1.0
    rough = span / 10
    power = 10.0 ** floor(log10(rough))
    step = next(multiple * power for multiple in _NICE_STEPS if rough <= multiple * power)
    return max(1.0, float(round(step))) if whole_numbers else step


def _table_label(table: TableProfile, tables: list[TableProfile]) -> str:
    """The file the analyst recognises, with the sheet name when one workbook gave several
    tables and the file name alone would be ambiguous."""
    if table.sheet and sum(t.source_file == table.source_file for t in tables) > 1:
        return f"{table.source_file} ({table.sheet})"
    return table.source_file


def _words(text: str) -> str:
    """A header as the analyst wrote it, with underscores opened up."""
    return " ".join(text.replace("_", " ").split()) or text


def _plural(text: str) -> str:
    return text if text.endswith("s") else f"{text}s"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]
