"""The automatic overview: everything we can say about a session without a model.

Why this exists: the moment the files land, the analyst should already have numbers. Not a
spinner, not "ask me something" — a page of computed findings, in the words of *their* data.
Every tile here is assembled from the catalog (roles, types, links) by the templates below,
run through the same guard, executor, formatter and chart rules as a model-written answer, and
read out by `facts`. No tokens, no clock, no randomness: the same files always give the same
overview, and it still works when every free model is rate limited.

How tiles get chosen, in one paragraph. Each section proposes candidates in the order an
analyst reads them. Candidates are then taken in *waves* — a section's first `depth` tiles
before any section's next `depth` — so an overview of six files covers six files instead of
spending itself on the first one. Everything that runs is scored on what came back (does it
have numbers, a readable number of groups, and do the groups actually differ); a tile that
scores nothing is dropped, a tile whose rows repeat another tile's rows is dropped, and what
is left is capped at `MAX_TILES`. Query time is capped too: when the budget is spent, the
remaining waves are simply not run, which is why the order is the order of importance.

The two rules this module must never break, both inherited from the product thesis:
- a number reaches a sentence only as a display string from `presentation.to_display`, so
  "₹54.67 Cr" on a tile is byte-identical to "₹54.67 Cr" in an answer;
- a PII column is never measured, grouped by, or offered. `sqlbuild.resolve` refuses them and
  every column here goes through it. The data-quality section names personal-data *columns*
  (that is the point of it) and never a value from one.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

from app.contracts import Catalog, ColumnProfile, ResultTable, TableProfile
from app.insights.facts import NOTHING
from app.insights.models import ColumnKind, Dashboard, DashboardSection, InsightTile, TileKind
from app.insights.runner import run_tile
from app.insights.sqlbuild import Ref, aggregate, date_bucket, from_clause, ident, resolve
from app.query.presentation import MAX_BARS, to_display
from app.sessions import SessionLike

# A page of findings, not a report. Fourteen tiles is what fits on one screen of a laptop
# before scrolling stops being reading and starts being searching.
MAX_TILES = 14
# The overview is the first thing drawn after an upload, so it competes with the analyst's
# patience, not with a batch job. Past this the remaining waves are skipped.
QUERY_BUDGET_S = 1.5
MIN_SCORE = 0.05  # below this a tile is saying nothing worth the space

# Roles that make a table the one the People tiles are about, and the slot each role may fill.
_PEOPLE_ROLES = ("join_date", "exit_date", "department", "location", "gender", "grade")
_PAY_ROLES = ("pay_month", "gross", "net")
_ATTENDANCE_ROLES = ("days_absent", "working_days", "days_present", "date", "pay_month")
_ROLE_SLOT: dict[str, tuple[ColumnKind, ...]] = {
    "department": ("category",), "location": ("category",), "gender": ("category",),
    "grade": ("category",), "exit_reason": ("category",), "review_cycle": ("category",),
    "join_date": ("date",), "exit_date": ("date",), "pay_month": ("date",), "date": ("date",),
    "ctc": ("measure",), "gross": ("measure",), "net": ("measure",), "amount": ("measure",),
    "days_absent": ("measure",), "working_days": ("measure",), "days_present": ("measure",),
    # A rating is a 1-5 integer: a measure to average and a label to group by, both true.
    "rating": ("measure", "category"),
}

# How many tiles a section may show before every other section has had its turn. People is the
# widest section because an HR analyst's first four questions are all about people.
_DEPTH = {"People": 4, "Pay": 2, "Attendance": 1, "Performance": 1}
_GENERIC_DEPTH = 2

_DESCRIPTIONS = {
    "People": "Who is on the books, where they sit, and who joined or left.",
    "Pay": "What payroll costs, and how it is spread.",
    "Attendance": "Days lost, and when.",
    "Performance": "How ratings are spread.",
}
# Roles an analyst says out loud differently from how the file spells the column. Everything
# else is the column's own name with the underscores taken out.
_SPOKEN = {"gross": "gross pay", "net": "take-home pay", "ctc": "CTC", "basic": "basic pay"}

QUALITY_SECTION = "Data quality"
_QUALITY_DESCRIPTION = "What we changed while reading your files, and what to keep an eye on."

# ponytail: one process-level dict, because sessions are already single-process (see
# SessionStore). Ceiling: a second worker rebuilds the overview once. Upgrade path: the same
# key in whatever cache the sessions move to.
_CACHE: dict[tuple[str, int], Dashboard] = {}
_CACHE_CAP = 8


@dataclass(frozen=True)
class _Candidate:
    """One tile we could show, before we know whether it says anything."""

    tile_id: str
    title: str
    kind: TileKind
    sql: str
    ask: str | None = None
    chart_type: str | None = None


@dataclass
class _Section:
    """A section and its candidates, in the order an analyst reads them."""

    title: str
    description: str
    depth: int
    candidates: list[_Candidate] = field(default_factory=list)

    def add(self, *candidates: _Candidate | None) -> None:
        self.candidates += [c for c in candidates if c is not None]


# --------------------------------------------------------------------------- public


def build(session: SessionLike) -> Dashboard:
    """The overview for this session, computed once per catalog version.

    Cached because it is the same page for the same files: a link confirmed or a file added
    bumps `catalog.version` and the next call recomputes from scratch. An empty session gets an
    empty dashboard rather than an apology — the UI has a better empty state than we do.
    """
    key = (session.id, session.catalog.version)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    started = time.perf_counter()
    plan = _plan(session.catalog)
    quality = _quality_tiles(session.catalog)
    tiles = _run(session, plan, budget=MAX_TILES - len(quality))
    sections = [DashboardSection(title=s.title, description=s.description, tiles=tiles[i])
                for i, s in enumerate(plan) if tiles.get(i)]
    if quality:
        sections.append(DashboardSection(title=QUALITY_SECTION, description=_QUALITY_DESCRIPTION,
                                         tiles=quality))
    dashboard = Dashboard(
        session_id=session.id, catalog_version=session.catalog.version,
        generated_ms=round((time.perf_counter() - started) * 1000), sections=sections)
    _remember(key, dashboard)
    return dashboard


def _remember(key: tuple[str, int], dashboard: Dashboard) -> None:
    """Keep this version, forget the session's older ones, and keep the dict small.

    Dropping the same session's other versions is the actual invalidation: without it a session
    that keeps adding files would hold one full dashboard per upload for as long as it lives.
    """
    for stale in [k for k in _CACHE if k[0] == key[0]]:
        del _CACHE[stale]
    _CACHE[key] = dashboard
    while len(_CACHE) > _CACHE_CAP:
        del _CACHE[next(iter(_CACHE))]  # insertion order: the oldest session goes first


def clear_cache() -> None:
    """Forget every cached overview. For tests and for "new session", which deletes the data."""
    _CACHE.clear()


# --------------------------------------------------------------------------- running


def _run(session: SessionLike, plan: list[_Section], *, budget: int) -> dict[int, list[InsightTile]]:
    """Run candidates in wave order until the time budget is gone, then keep the best.

    A candidate that raises is dropped and the next one is tried: an overview missing one card
    is useful, an overview that fails is not. Time is measured around the query itself, which
    is the only part that can be slow — building the SQL is string concatenation.
    """
    spent = 0.0
    ran: list[tuple[_Slot, InsightTile, float]] = []
    for slot in _wave_order(plan):
        if spent >= QUERY_BUDGET_S:
            break  # the rest of this wave and every later wave: the least important tiles
        candidate = plan[slot.section].candidates[slot.rank]
        started = time.perf_counter()
        try:
            tile = run_tile(session, tile_id=candidate.tile_id, title=candidate.title,
                            kind=candidate.kind, sql=candidate.sql,
                            chart_type=candidate.chart_type, ask=candidate.ask)
        except ValueError:
            continue
        finally:
            spent += time.perf_counter() - started
        tile = _RESTATE.get(candidate.tile_id, _unchanged)(tile)
        score = _usefulness(tile)
        if score >= MIN_SCORE:
            ran.append((slot, tile, score))
    return _keep(ran, budget)


class _Slot(NamedTuple):
    """Where a candidate sits: which wave it belongs to, and its place in its section."""

    wave: int
    section: int
    rank: int


def _wave_order(plan: list[_Section]) -> list[_Slot]:
    """Every section's first `depth` candidates, then every section's next `depth`, and so on.

    Why waves rather than one long list: an HR upload with a sales file in it proposes far more
    than fourteen tiles, and taking them in section order would spend the whole overview on
    People and never mention sales. Inside a wave, sections keep their own order.
    """
    return sorted(_Slot(rank // section.depth, index, rank)
                  for index, section in enumerate(plan)
                  for rank in range(len(section.candidates)))


def _keep(ran: list[tuple[_Slot, InsightTile, float]], budget: int) -> dict[int, list[InsightTile]]:
    """Drop repeats, cap the total, and give each section its tiles back in reading order.

    Selection is by wave, then section, then usefulness: the wave and the section decide the
    *shape* of the overview (every section gets a turn), and the score decides which of a
    section's candidates earn the space. Display order is the section's own order, because the
    analyst reads "headcount, then where they sit, then who left", not "best tile first".
    """
    ranked = sorted(ran, key=lambda item: (item[0].wave, item[0].section, -item[2], item[0].rank))
    kept: list[tuple[_Slot, InsightTile]] = []
    seen: set[tuple[int, tuple[str, ...], tuple[str, ...]]] = set()
    for slot, tile, _ in ranked:
        if len(kept) >= budget:
            break
        signature = (slot.section, *_signature(tile))
        if signature in seen:
            continue  # the same rows under a different title says nothing new
        seen.add(signature)
        kept.append((slot, tile))

    tiles: dict[int, list[InsightTile]] = {}
    for slot, tile in sorted(kept, key=lambda item: item[0]):
        tiles.setdefault(slot.section, []).append(tile)
    return tiles


def _usefulness(tile: InsightTile) -> float:
    """How much a tile earns its place on the page; below MIN_SCORE it is dropped.

    Three things make a computed tile worth showing: it has numbers at all (coverage), it has a
    readable number of groups, and the groups actually differ. "All six departments are level
    at 1" is true, computed, and a waste of a card.
    """
    table = tile.table
    if table is None or not table.rows or tile.statement == NOTHING:
        return 0.0
    column = _measure_index(table)
    if column is None:
        return 0.0
    values = [_number(row[column]) for row in table.rows]
    present = [v for v in values if v is not None]
    if not present:
        return 0.0
    coverage = len(present) / len(values)
    if len(table.rows) == 1:
        # One row is a figure, not a comparison — fine for a KPI or a five-number summary,
        # meaningless for a tile whose whole point is the difference between groups. Scored
        # below a breakdown that really varies and above one whose groups are all level, so a
        # page short of space shows the finding rather than the flat bar chart.
        return 0.0 if tile.kind in ("breakdown", "trend", "share", "comparison") else 0.7 * coverage
    low, high = min(present), max(present)
    spread = (high - low) / high if high > 0 else float(high != low)
    groups = len(table.rows)
    fit = 1.0 if groups <= MAX_BARS else 0.8 if groups <= 2 * MAX_BARS else 0.5
    return fit * (0.4 + 0.6 * spread) * coverage


def _signature(tile: InsightTile) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What the tile actually says, as the analyst sees it: its labels and its numbers.

    Display strings, not raw values, so two tiles that round to the same picture count as the
    same tile. Compared only within a section, because "800" in a sales KPI and "800" in a
    headcount KPI are the same string and completely different findings.
    """
    table = tile.table
    if table is None or not table.display:
        return ((), ())
    measure = _measure_index(table)
    labels = next((i for i in range(len(table.columns)) if i != measure), None)
    return (tuple(row[labels] for row in table.display) if labels is not None else (),
            tuple(row[measure] for row in table.display) if measure is not None else ())


def _measure_index(table: ResultTable) -> int | None:
    """The column a tile is read on: the last one holding numbers.

    Last, because a template query ends with the figure it was asked for — the same rule
    choose_chart and facts follow, so the three of them always talk about the same column.
    """
    for index in reversed(range(len(table.columns))):
        if any(_number(row[index]) is not None for row in table.rows):
            return index
    return None


def _number(value: object) -> float | None:
    """A cell that can be compared. `True` is an int in Python and a label here."""
    return None if isinstance(value, bool) or not isinstance(value, (int, float)) else float(value)


def _unchanged(tile: InsightTile) -> InsightTile:
    return tile


# --------------------------------------------------------------------------- planning


def _plan(catalog: Catalog) -> list[_Section]:
    """Which sections this session can have, and what each could show."""
    tables = _usable_tables(catalog)
    people = _home(tables, _PEOPLE_ROLES, (("join_date", "department", "location"),))
    pay = _home(tables, _PAY_ROLES, (("pay_month",), ("gross", "net")))
    attendance = _home(tables, _ATTENDANCE_ROLES,
                       (("days_absent",), ("working_days", "days_present")))
    performance = _home(tables, ("rating", "grade", "review_cycle"), (("rating",),))

    homes = (people, pay, attendance, performance)
    sections = [
        _people_section(catalog, people),
        _pay_section(catalog, pay, people),
        _attendance_section(catalog, attendance),
        _performance_section(catalog, performance, people),
    ]
    # A table counts as spoken for only when its section was really built. A table that looked
    # like a payslip but produced no tile has to fall through to the generic treatment rather
    # than disappear from the overview altogether.
    used = {home.name for home, section in zip(homes, sections, strict=True)
            if home is not None and section is not None}
    # The biggest leftover file first: it is the one the analyst is most likely to have
    # uploaded on purpose, and with fourteen tiles the later ones may not get a turn.
    rest = sorted((t for t in tables if t.name not in used), key=lambda t: (-t.row_count, t.name))
    sections += [_generic_section(catalog, table) for table in rest]
    return [s for s in sections if s is not None and s.candidates]


def _usable_tables(catalog: Catalog) -> list[TableProfile]:
    """Every table a tile may read, with union members replaced by their view.

    A question about attendance is about the whole year, not about Q1: stacking is exactly what
    the view is for, and showing "absence in attendance_q1" next to "absence in attendance_q2"
    would be two half-answers where there is one answer.
    """
    stacked = {name for u in catalog.unions if u.status == "active" for name in u.tables}
    return [t for t in catalog.tables if t.name not in stacked]


def _home(tables: Sequence[TableProfile], roles: Sequence[str],
          required: Sequence[Sequence[str]]) -> TableProfile | None:
    """The table a section is about: it must carry at least one role from each required group,
    and among those it is the one carrying the most of the section's roles.

    All of a section's roles are taken from one table on purpose. Two tables would mean a join,
    and a join on an overview is a number nobody asked us to risk: see `from_clause`.
    """
    fit = [t for t in tables if all(any(_column(t, r) for r in group) for group in required)]
    ranked = sorted(fit, key=lambda t: (-sum(_column(t, r) is not None for r in roles),
                                        not t.is_view, -t.row_count, t.name))
    return ranked[0] if ranked else None


def _column(table: TableProfile, role: str) -> ColumnProfile | None:
    return next((c for c in table.columns if c.role == role), None)


def _refs(table: TableProfile | None, catalog: Catalog, roles: Iterable[str]) -> dict[str, Ref]:
    """role -> a checked reference, for the roles this table really has.

    Everything goes through `resolve`, so a role sitting on a personal-data column, an
    identifier, or a column of the wrong shape (a free-text "department" with 400 values) is
    quietly absent and the tiles that need it are never proposed.
    """
    found: dict[str, Ref] = {}
    if table is None:
        return found
    for role in roles:
        column = _column(table, role)
        if column is None:
            continue
        try:
            found[role] = resolve(f"{table.name}.{column.name}", catalog, _ROLE_SLOT.get(role, ()))
        except ValueError:
            continue
    return found


def _q(ref: Ref) -> str:
    """"table"."column": always qualified, so the same builder works joined or not."""
    return f"{ident(ref.table)}.{ident(ref.column)}"


def _spoken(ref: Ref) -> str:
    """The column as an analyst says it: "gross pay" for a gross column, "order date" for
    order_date. Keyed on the role first, so a column called `gross` in a file that is not a
    payslip keeps its own name."""
    return _SPOKEN.get(ref.profile.role or "") or ref.column.replace("_", " ")


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _where(*conditions: str | None) -> str:
    live = [c for c in conditions if c]
    return f" WHERE {' AND '.join(live)}" if live else ""


def _still_here(exit_date: Ref | None) -> str | None:
    """The "currently employed" test, used by every People tile so the headcount KPI and the
    headcount-by-department bars can never disagree. Someone whose last day is today has left,
    which is the glossary's rule."""
    return None if exit_date is None else f"({_q(exit_date)} IS NULL OR {_q(exit_date)} > current_date)"


# --------------------------------------------------------------------------- HR sections


def _people_section(catalog: Catalog, table: TableProfile | None) -> _Section | None:
    """Headcount, where they sit, the gender mix, attrition, joiners and leavers, tenure."""
    refs = _refs(table, catalog, _PEOPLE_ROLES)
    if table is None or not refs:
        return None
    section = _Section("People", _DESCRIPTIONS["People"], _DEPTH["People"])
    source, active = ident(table.name), _still_here(refs.get("exit_date"))
    joined = refs.get("join_date")
    left = refs.get("exit_date")

    if active:
        section.add(_Candidate(
            "people-headcount", "Active headcount", "kpi",
            f"SELECT count(*) AS active_headcount FROM {source}"
            + _where(active, f"{_q(joined)} <= current_date" if joined else None),
            ask="How has headcount changed over the last year?"))
    else:
        section.add(_Candidate(
            "people-headcount", "People on file", "kpi",
            f"SELECT count(*) AS people FROM {source}",
            ask="How many people are in each department?"))

    section.add(_group_count(refs.get("department"), "people-by-department",
                             "Headcount by department", source, active,
                             "Which department grew the most this year?"))
    section.add(_share_tile(refs.get("gender"), "people-gender", "Gender mix", source, active,
                            "What is the gender mix in each department?"))
    section.add(_attrition(table, joined, left))
    section.add(_flow(table, joined, left))
    section.add(_group_count(refs.get("location"), "people-by-location", "Headcount by location",
                             source, active, "Which location has the highest average CTC?"))
    section.add(_tenure(table, joined, active))
    return section


def _group_count(group: Ref | None, tile_id: str, title: str, source: str,
                 active: str | None, ask: str) -> _Candidate | None:
    """How many people in each group, biggest first, ties broken by name.

    The tie-break is not cosmetic: DuckDB returns tied groups in whatever order its hash
    aggregate happened to build them, so two loads of a company with three departments of 156
    each would show the bars in a different order and "X is highest" would name a different
    department. The whole point of this half of the product is that it does not do that.
    """
    if group is None:
        return None
    sql = (f"SELECT {_q(group)} AS {ident(group.column)}, count(*) AS employees FROM {source}"
           + _where(active, f"{_q(group)} IS NOT NULL") + " GROUP BY 1 ORDER BY 2 DESC, 1")
    return _Candidate(tile_id, title, "breakdown", sql, ask=ask)


def _share_tile(group: Ref | None, tile_id: str, title: str, source: str,
                active: str | None, ask: str) -> _Candidate | None:
    """The same counts read as shares of the whole, drawn as a donut.

    Only the counts are selected: a second column holding the percentage would push the result
    past the chart rules into a plain table, and `facts` computes the share from a whole,
    non-truncated total anyway.
    """
    if group is None:
        return None
    sql = (f"SELECT {_q(group)} AS {ident(group.column)}, count(*) AS employees FROM {source}"
           + _where(active, f"{_q(group)} IS NOT NULL") + " GROUP BY 1 ORDER BY 2 DESC, 1")
    return _Candidate(tile_id, title, "share", sql, ask=ask, chart_type="donut")


def _attrition(table: TableProfile, joined: Ref | None, left: Ref | None) -> _Candidate | None:
    """Attrition for the latest full year, exactly as the glossary defines it: exits in the
    year over the average of the opening and closing headcount.

    The year is chosen by the data, not by the clock, so the number does not change tomorrow:
    it is the last calendar year the files run to the end of (a file ending in June describes
    a year that is not over, so the year before it is the last full one).
    """
    if joined is None or left is None:
        return None
    exits = f"count(*) FILTER (WHERE {_q(left)} BETWEEN first_day AND final_day)"
    opening = (f"count(*) FILTER (WHERE {_q(joined)} < first_day"
               f" AND ({_q(left)} IS NULL OR {_q(left)} >= first_day))")
    closing = (f"count(*) FILTER (WHERE {_q(joined)} <= final_day"
               f" AND ({_q(left)} IS NULL OR {_q(left)} > final_day))")
    average = f"({opening} + {closing}) / 2.0"
    sql = (
        f"WITH span AS (SELECT max(greatest({_q(joined)},"
        f" coalesce({_q(left)}, {_q(joined)}))) AS last_day FROM {ident(table.name)}),"
        " reporting_year AS (SELECT CASE WHEN month(last_day) = 12 THEN year(last_day)"
        " ELSE year(last_day) - 1 END AS yr FROM span),"
        " period AS (SELECT yr, make_date(yr, 1, 1) AS first_day,"
        " make_date(yr, 12, 31) AS final_day FROM reporting_year)"
        f" SELECT yr AS year, {exits} AS exits, round({average}, 1) AS average_headcount,"
        f" round(100.0 * {exits} / nullif({average}, 0), 1) AS attrition_rate_pct"
        f" FROM {ident(table.name)}, period GROUP BY 1"
    )
    return _Candidate("people-attrition", "Attrition rate", "metric", sql,
                      ask="Which departments had the highest attrition?")


def _attrition_sentence(tile: InsightTile) -> InsightTile:
    """Put the year in the tile, from the result's own display strings.

    `facts` cannot: the year is a label column, and the title was written before the query ran,
    so only the result knows which year turned out to be the last full one. The replacement
    insight line is the glossary definition, because an attrition number that does not say how
    it was counted is the number people argue about.
    """
    row = tile.table.display[0] if tile.table and tile.table.display else None
    if row is None or len(row) < 4 or row[3] == "—":
        return tile
    year, exits, average, rate = row[0], row[1], row[2], row[3]
    return tile.model_copy(update={
        "title": f"Attrition in {year}",
        "statement": f"{rate} of the workforce left in {year}: {exits} exits against an"
                     f" average headcount of {average}.",
        "insights": [("Counted as exits in the year divided by the average of the opening"
                      " and closing headcount."),
                     f"{year} is the last full year your files cover."],
    })


_RESTATE: dict[str, Callable[[InsightTile], InsightTile]] = {"people-attrition": _attrition_sentence}


def _flow(table: TableProfile, joined: Ref | None, left: Ref | None) -> _Candidate | None:
    """Joiners and leavers side by side, by year.

    One long result (year, movement, people) rather than two columns of counts, because that is
    the shape the chart rules draw as a grouped bar; two measure columns would fall back to a
    table, and the whole point of this tile is seeing the two bars next to each other.
    """
    if joined is None or left is None:
        return None
    source = ident(table.name)
    sql = (f"WITH movements AS (SELECT year({_q(joined)}) AS yr, 'Joined' AS movement FROM {source}"
           f" UNION ALL SELECT year({_q(left)}) AS yr, 'Left' AS movement FROM {source}"
           f" WHERE {_q(left)} IS NOT NULL)"
           " SELECT yr AS year, movement AS movement, count(*) AS people FROM movements"
           " GROUP BY 1, 2 ORDER BY 1, 2")
    return _Candidate("people-flow", "Joiners and leavers by year", "comparison", sql,
                      ask="Why did more people leave in the latest year?")


def _tenure(table: TableProfile, joined: Ref | None, active: str | None) -> _Candidate | None:
    """How long the people who are still here have been here, in bands.

    Bands rather than a histogram of years: "under 1 year" and "10 years or more" are the two
    groups anybody acts on, and fixed bands need no thresholds invented from the data.
    """
    if joined is None:
        return None
    years = f"date_diff('day', {_q(joined)}, current_date) / 365.25"
    sql = ("SELECT CASE WHEN tenure_years < 1 THEN 'Under 1 year'"
           " WHEN tenure_years < 3 THEN '1 to 3 years'"
           " WHEN tenure_years < 5 THEN '3 to 5 years'"
           " WHEN tenure_years < 10 THEN '5 to 10 years'"
           " ELSE '10 years or more' END AS tenure, count(*) AS employees"
           f" FROM (SELECT {years} AS tenure_years FROM {ident(table.name)}"
           + _where(active) + ") AS t GROUP BY 1 ORDER BY min(tenure_years)")
    return _Candidate("people-tenure", "Tenure of current employees", "distribution", sql,
                      ask="Who has been here longest in each department?")


def _pay_section(catalog: Catalog, pay: TableProfile | None,
                 people: TableProfile | None) -> _Section | None:
    """The payroll total and its monthly shape, then what CTC looks like across the company."""
    refs = _refs(pay, catalog, _PAY_ROLES)
    people_refs = _refs(people, catalog, ("ctc", "grade", "department", "exit_date"))
    money = refs.get("gross") or refs.get("net")
    month = refs.get("pay_month")
    ctc = people_refs.get("ctc")
    if money is None and ctc is None:
        return None
    section = _Section("Pay", _DESCRIPTIONS["Pay"], _DEPTH["Pay"])

    if money is not None:
        source = ident(money.table)
        total = aggregate("sum", _q(money))
        label = _spoken(money)
        section.add(_Candidate(
            "pay-total", f"Total {label}", "kpi",
            f"SELECT {total} AS total_{money.column} FROM {source}",
            ask=f"How does total {label} split by department?"))
        if month is not None:
            section.add(_Candidate(
                "pay-trend", f"{_cap(label)} by month", "trend",
                f"SELECT {_q(month)} AS {ident(month.column)}, {total} AS total_{money.column}"
                f" FROM {source} GROUP BY 1 ORDER BY 1",
                ask=f"Which month had the highest {label}, and why?"))

    if ctc is not None:
        group = people_refs.get("grade") or people_refs.get("department")
        active = _still_here(people_refs.get("exit_date"))
        if group is not None:
            section.add(_Candidate(
                "pay-ctc-by-group", f"Average CTC by {_spoken(group)}", "breakdown",
                f"SELECT {_q(group)} AS {ident(group.column)},"
                f" round({aggregate('average', _q(ctc))}, 0) AS average_ctc"
                f" FROM {ident(ctc.table)}"
                + _where(active, f"{_q(group)} IS NOT NULL") + " GROUP BY 1 ORDER BY 2 DESC, 1",
                ask=f"Is CTC fair across every {_spoken(group)}?"))
        section.add(_spread(ctc, "pay-ctc-spread", "CTC spread", active,
                            "Who is paid above the top quarter of the range?"))
    return section


def _spread(measure: Ref, tile_id: str, title: str, condition: str | None,
            ask: str) -> _Candidate:
    """The five-number summary of one measure: the reading `facts` gives a distribution.

    Median and quartiles rather than an average, because one ₹87 L salary moves an average and
    does not move a median, and the question a spread tile answers is "what is normal here".
    """
    column, source = _q(measure), ident(measure.table)
    sql = (f"SELECT round(median({column}), 0) AS median_{measure.column},"
           f" round(quantile_cont({column}, 0.25), 0) AS p25_{measure.column},"
           f" round(quantile_cont({column}, 0.75), 0) AS p75_{measure.column},"
           f" min({column}) AS lowest_{measure.column},"
           f" max({column}) AS highest_{measure.column}"
           f" FROM {source}" + _where(condition, f"{column} IS NOT NULL"))
    return _Candidate(tile_id, title, "distribution", sql, ask=ask)


def _attendance_section(catalog: Catalog, table: TableProfile | None) -> _Section | None:
    """Absence as a rate, by month, over the stacked view when there is one."""
    refs = _refs(table, catalog, _ATTENDANCE_ROLES)
    absent = refs.get("days_absent")
    month = refs.get("date") or refs.get("pay_month")
    if table is None or absent is None or month is None:
        return None
    # Against working days when the file has them; otherwise against the days it does account
    # for. Both are honest denominators — days nobody recorded are not days anybody was absent.
    if (working := refs.get("working_days")) is not None:
        denominator = aggregate("sum", _q(working))
    elif (present := refs.get("days_present")) is not None:
        denominator = f"({aggregate('sum', _q(present))} + {aggregate('sum', _q(absent))})"
    else:
        return None

    section = _Section("Attendance", _DESCRIPTIONS["Attendance"], _DEPTH["Attendance"])
    section.add(_Candidate(
        "attendance-rate", "Absence rate by month", "trend",
        f"SELECT {date_bucket(_q(month), 'month')} AS month,"
        f" round(100.0 * {aggregate('sum', _q(absent))} / nullif({denominator}, 0), 1)"
        f" AS absence_rate_pct FROM {ident(table.name)} GROUP BY 1 ORDER BY 1",
        ask="Which department loses the most days to absence?"))
    return section


def _performance_section(catalog: Catalog, table: TableProfile | None,
                         people: TableProfile | None) -> _Section | None:
    """How ratings are spread, and whether they are spread the same way at every grade."""
    refs = _refs(table, catalog, ("rating", "grade"))
    rating = refs.get("rating")
    if table is None or rating is None:
        return None
    section = _Section("Performance", _DESCRIPTIONS["Performance"], _DEPTH["Performance"])
    # A rating stored as 1-5 is grouped by, not averaged, so it is labelled before it is
    # counted: "Rating 3 is highest at 354" reads as a finding, "3 is highest at 354" reads as
    # a typo. A rating already written in words ("Exceeds expectations") is left alone.
    label = (f"concat('Rating ', {_q(rating)})" if rating.profile.type != "text"
             else _q(rating))
    section.add(_Candidate(
        "perf-ratings", "Rating distribution", "distribution",
        f"SELECT {label} AS {ident(rating.column)}, count(*) AS reviews"
        f" FROM {ident(table.name)}" + _where(f"{_q(rating)} IS NOT NULL")
        + f" GROUP BY 1 ORDER BY min({_q(rating)})",
        ask="How do ratings compare between departments?"))

    grade = refs.get("grade") or _refs(people, catalog, ("grade",)).get("grade")
    if grade is not None:
        # count(*) counts reviews on the many side of the link, so nothing from the one side is
        # summed and nothing is counted twice; from_clause refuses the shapes where it would be.
        try:
            source = from_clause([grade, rating], catalog)
        except ValueError:
            return section
        section.add(_Candidate(
            "perf-by-grade", "Ratings by grade", "comparison",
            f"SELECT {_q(grade)} AS grade, {_q(rating)} AS rating, count(*) AS reviews {source}"
            + _where(f"{_q(grade)} IS NOT NULL", f"{_q(rating)} IS NOT NULL")
            + " GROUP BY 1, 2 ORDER BY 1, 2",
            ask="Are the top ratings concentrated in one grade?"))
    return section


# --------------------------------------------------------------------------- any other file


def _generic_section(catalog: Catalog, table: TableProfile) -> _Section:
    """An overview of a file we have no HR story for: how much of it there is, what it adds up
    to, what it splits into, how it moves, and what a typical row looks like.

    Named after the file rather than the table so the analyst recognises it: `sales.csv`, not
    `sales`; `Salary_Register_2025.xlsx - Bonuses` for a second sheet.
    """
    label = _file_label(table)
    section = _Section(label, "Computed straight from this file.", _GENERIC_DEPTH)
    measures = _pick(table, catalog, ("measure",), _measure_rank)
    additive = [m for m in measures if m.profile.type != "percent"]
    categories = _pick(table, catalog, ("category",), _category_rank)
    dates = _pick(table, catalog, ("date",), lambda c: (c.null_fraction, -c.distinct_count, c.name))
    measure = additive[0] if additive else None

    # The figure and the split first, the row count after them: with a shared tile budget a
    # section may only get its first two, and "800 rows" alone is not an overview of anything.
    section.add(
        _totals(table, additive) if additive else None,
        _breakdown(table, categories[0], measure) if categories else None,
        _Candidate(f"{table.name}-rows", "Row count", "kpi",
                   f"SELECT count(*) AS row_count FROM {ident(table.name)}",
                   ask=f"What is in {label}?"),
        _trend(table, dates[0], measure) if dates else None,
        _breakdown(table, categories[1], measure) if len(categories) > 1 else None,
        _spread(measure, f"{table.name}-spread", f"{_cap(_spoken(measure))} spread", None,
                f"What is a typical {_spoken(measure)}?") if measure is not None else None,
    )
    return section


def _totals(table: TableProfile, measures: list[Ref]) -> _Candidate:
    """The file's headline figure, with one supporting count.

    The headline goes *last* in the SELECT because `facts` and `choose_chart` both read the
    final measure as the one that was asked for. Only two columns: a tile that adds up every
    numeric column ends up totalling unit prices, which measures nothing.
    """
    headline = measures[0]
    support = next((m for m in measures[1:] if m.profile.role == "quantity"), None)
    selected = [m for m in (support, headline) if m is not None]
    columns = ", ".join(f"{aggregate('sum', _q(m))} AS total_{m.column}" for m in selected)
    label = _spoken(headline)
    return _Candidate(f"{table.name}-totals", f"Total {label}", "kpi",
                      f"SELECT {columns} FROM {ident(table.name)}",
                      ask=f"How has {label} moved over the year?")


def _breakdown(table: TableProfile, category: Ref, measure: Ref | None) -> _Candidate:
    """The file split by one of its labels: the measure per group, or the row count when the
    file has nothing to add up. A percentage column is averaged, never summed."""
    if measure is None:
        value, title = "count(*) AS rows_in_group", f"Rows by {_spoken(category)}"
    else:
        func = "average" if measure.profile.type == "percent" else "sum"
        value = f"{aggregate(func, _q(measure))} AS {func}_{measure.column}"
        title = f"{_cap(_spoken(measure))} by {_spoken(category)}"
    sql = (f"SELECT {_q(category)} AS {ident(category.column)}, {value} FROM {ident(table.name)}"
           + _where(f"{_q(category)} IS NOT NULL") + " GROUP BY 1 ORDER BY 2 DESC, 1")
    return _Candidate(f"{table.name}-by-{category.column}", title, "breakdown", sql,
                      ask=f"Which {_spoken(category)} is growing fastest?")


def _trend(table: TableProfile, when: Ref, measure: Ref | None) -> _Candidate:
    """The file by month. Months, not days: a year of daily rows is 365 unreadable points."""
    if measure is None:
        value, title = "count(*) AS rows_in_month", "Rows by month"
    else:
        func = "average" if measure.profile.type == "percent" else "sum"
        value = f"{aggregate(func, _q(measure))} AS {func}_{measure.column}"
        title = f"{_cap(_spoken(measure))} by month"
    sql = (f"SELECT {date_bucket(_q(when), 'month')} AS month, {value}"
           f" FROM {ident(table.name)}" + _where(f"{_q(when)} IS NOT NULL")
           + " GROUP BY 1 ORDER BY 1")
    return _Candidate(f"{table.name}-by-month", title, "trend", sql,
                      ask="What changed in the strongest month?")


def _pick(table: TableProfile, catalog: Catalog, accepts: tuple[ColumnKind, ...],
          rank: Callable[[ColumnProfile], tuple]) -> list[Ref]:
    """This table's columns that can fill a slot, best first. `resolve` does the refusing, so
    personal data and identifiers never reach a picker, a chart or a title."""
    refs = []
    for column in sorted(table.columns, key=rank):
        try:
            refs.append(resolve(f"{table.name}.{column.name}", catalog, accepts))
        except ValueError:
            continue
    return refs


def _measure_rank(column: ColumnProfile) -> tuple:
    """What a file is really about: the column named as an amount, then money, then counts."""
    role = 0 if column.role == "amount" else 1 if column.type == "currency" else \
        2 if column.role == "quantity" else 3
    return (role, column.null_fraction, column.name)


def _category_rank(column: ColumnProfile) -> tuple:
    """Three to twelve groups is a chart; two is a toggle and forty is a list."""
    return (0 if 3 <= column.distinct_count <= MAX_BARS else 1, column.null_fraction,
            column.distinct_count, column.name)


def _file_label(table: TableProfile) -> str:
    """The file (and sheet) as the analyst named it, flattened to one short line.

    File names come from an upload, so they are somebody else's text: whitespace is collapsed
    and the result is capped before it becomes a heading. It is rendered as plain text, never
    as markup, and it never reaches a prompt (DECISIONS #16b).
    """
    name = " ".join((table.source_file or table.name).split())
    sheet = " ".join((table.sheet or "").split())
    label = f"{name} - {sheet}" if sheet else name
    return label[:57] + "..." if len(label) > 60 else label


# --------------------------------------------------------------------------- data quality


def _quality_tiles(catalog: Catalog) -> list[InsightTile]:
    """What we changed, what to look at, what the model cannot see, and how the files link.

    These tiles run no SQL: everything here was already computed during ingestion and link
    detection. They are built first and always kept, because "your ₹ column was read as money
    and one Grand Total row was dropped" is the finding an analyst needs before they trust a
    single other tile on the page.
    """
    files = [t for t in catalog.tables if not t.is_view]
    if not files:
        return []
    tiles = [_cleaned_tile(files), _attention_tile(files), _privacy_tile(files),
             _links_tile(catalog)]
    return [tile for tile in tiles if tile is not None]


def _rows(count: int) -> str:
    """"1 row" / "6 rows", the number formatted the way every other number in the app is."""
    return f"{to_display(count, 'integer')} row{'' if count == 1 else 's'}"


def _cleaned_tile(files: list[TableProfile]) -> InsightTile:
    """What ingestion changed before any number was calculated."""
    typed = sum(len(t.health.coercions) for t in files)
    titles = sum(t.health.skipped_title_rows for t in files)
    totals = sum(t.health.dropped_total_rows for t in files)
    removed = sum(t.health.duplicate_rows for t in files if t.health.duplicates_removed)
    rows = sum(t.health.rows for t in files)

    lines = []
    if typed:
        lines.append(f"{to_display(typed, 'integer')} columns were read as dates, whole numbers"
                     " or rupee amounts instead of text.")
    if titles or totals:
        parts = []
        if titles:
            parts.append(f"{_rows(titles)} of title above the header")
        if totals:
            parts.append(f"{_rows(totals)} of totals at the foot")
        lines.append(f"Dropped {' and '.join(parts)}, which would have been counted twice.")
    if removed:
        lines.append(f"{_rows(removed)} were exact duplicates, including their id,"
                     " and were removed.")
    if not lines:
        lines.append("Nothing had to be corrected: every column parsed cleanly.")
    tables = f"{to_display(len(files), 'integer')} table{'' if len(files) == 1 else 's'}"
    statement = (f"{_rows(rows)} across {tables} were read and cleaned before anything was"
                 " calculated.")
    return InsightTile(id="quality-cleaned", title="What was cleaned", kind="quality",
                       statement=statement, insights=lines[:3],
                       ask="How many rows are in each file?")


def _attention_tile(files: list[TableProfile]) -> InsightTile | None:
    """Gaps and values that would not parse: the things that make a total look wrong later."""
    lines = []
    gaps = sorted(((share, column, t.name) for t in files
                   for column, share in t.health.null_hotspots.items()),
                  key=lambda item: (-item[0], item[1], item[2]))
    for share, column, table in gaps[:2]:
        lines.append(f"{column} in {table} is empty in {to_display(100 * share, 'percent')}"
                     " of rows, so totals and averages leave those rows out.")
    unreadable = sorted(((c.unparseable, c.column, t.name, c.to_type) for t in files
                         for c in t.health.coercions if c.unparseable),
                        key=lambda item: (-item[0], item[1], item[2]))
    for count, column, table, to_type in unreadable[:2]:
        lines.append(f"{to_display(count, 'integer')} values in {column} ({table}) could not be"
                     f" read as {to_type} and are empty.")
    if any(t.health.date_format_ambiguous for t in files):
        lines.append("Some dates could be day-first or month-first; they were read as day-first.")
    lines += [w for t in files for w in t.health.warnings]
    if not lines:
        return None
    lines = lines[:3]
    statement = (f"{to_display(len(lines), 'integer')} things are worth a look before you quote"
                 " these numbers." if len(lines) > 1 else lines[0])
    return InsightTile(id="quality-attention", title="What needs a look", kind="quality",
                       statement=statement, insights=lines,
                       ask="Which columns have the most empty values?")


def _privacy_tile(files: list[TableProfile]) -> InsightTile:
    """Which columns are held back from the model. Columns, never a value from one."""
    hidden = [(t.name, c.label) for t in files for c in t.columns if c.pii]
    # The follow-up is deliberately about the catalog, not about the columns themselves: a
    # chip inviting an analyst to ask what is *in* a personal-data column would undo the tile.
    ask = "What does the AI see about my files?"
    if not hidden:
        return InsightTile(
            id="quality-privacy", title="Personal data", kind="quality", ask=ask,
            statement="No column in these files looks like personal data.",
            insights=[("The AI never sees a row either way: it is given column names, types"
                       " and statistics, and writes SQL that this app runs.")])
    columns = ", ".join(sorted({label for _, label in hidden}))
    statement = (f"{to_display(len(hidden), 'integer')} columns hold personal data and are"
                 " hidden from the AI.")
    return InsightTile(
        id="quality-privacy", title="Personal data", kind="quality", statement=statement, ask=ask,
        insights=[f"Hidden: {columns[:200]}.",
                  "They are never measured, never grouped by, and never offered as a filter.",
                  "The AI is given column names, types and statistics — never a row."])


def _links_tile(catalog: Catalog) -> InsightTile | None:
    """How well the files join, in words rather than a match percentage nobody reads.

    Directional on purpose (DECISIONS #17): "7% of employees have no payroll rows" and "7% of
    payroll rows have no employee" are different problems and only one of them is yours.
    """
    active = [r for r in catalog.relationships if r.status == "active"]
    stacked = [u for u in catalog.unions if u.status == "active"]
    if not active and not stacked:
        return None
    lines = []
    for link in sorted(active, key=lambda r: (r.match_left, r.id))[:2]:
        where = f"in {link.right_table}, on {link.left_column}"
        lines.append(f"Every row in {link.left_table} finds a match {where}."
                     if link.match_left >= 1 else
                     f"{to_display(100 * link.match_left, 'percent')} of rows in"
                     f" {link.left_table} find a match {where}.")
    for union in stacked[:1]:
        lines.append(f"{' and '.join(union.tables)} have the same columns and are stacked"
                     f" into {union.view_name}, so a question covers all of them at once.")
    weakest = min(active, key=lambda r: (r.match_left, r.id), default=None)
    statement = (f"{to_display(len(active), 'integer')} links between your files are switched on,"
                 " so a question can cross them." if active else
                 f"{to_display(len(stacked), 'integer')} files with the same columns are stacked"
                 " into one view.")
    ask = (f"How many rows in {weakest.left_table} have no match in {weakest.right_table}?"
           if weakest is not None else None)
    return InsightTile(id="quality-links", title="How your files link up", kind="quality",
                       statement=statement, insights=lines[:3], ask=ask)
