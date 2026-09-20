"""Run one template-written query and return a finished tile.

Why this is a module and not three lines in the dashboard: model-written SQL and
template-written SQL must take exactly one path to the screen. Same guard, same executor with
the same timeout, same column kinds, same display strings, same chart rules, same caveats. If
the two paths diverged, a number on the dashboard and the same number in an answer could
disagree, and the whole promise of the product is that they cannot.

A tile that cannot be produced raises ValueError with one plain sentence. Callers building a
dashboard catch it and drop the tile: an overview missing one card is useful, an overview that
500s is not.
"""

from __future__ import annotations

from typing import get_args

from app.config import settings
from app.contracts import ChartSpec, ResultTable
from app.insights.facts import describe
from app.insights.models import InsightTile, TileKind
from app.query.executor import ExecResult, QueryError, QueryTimeout, execute
from app.query.guard import GuardedQuery, GuardError, validate_sql
from app.query.presentation import build_table, choose_chart, column_kinds
from app.query.verify import fan_out_risks, null_caveats
from app.sessions import SessionLike

# A tile is a card, not an export. 500 rows fills any chart the frontend draws and keeps a
# whole dashboard of tiles well inside the response size the browser has to parse.
ROW_CAP = 500
CHART_TYPES = frozenset(get_args(ChartSpec.model_fields["type"].annotation))


def run_tile(
    session: SessionLike, *, tile_id: str, title: str, kind: TileKind, sql: str,
    chart_type: str | None = None, ask: str | None = None, statement: str | None = None,
) -> InsightTile:
    """Validate, run, format and read one query.

    `chart_type` overrides the chart the rules would pick, keeping the x/y/series the rules
    found: a caller may know a share is best as a donut, but it must not get to decide which
    column is the measure — that is what makes every chart in the app consistent.
    `statement` overrides the computed sentence (a KPI tile usually has a better one of its
    own); the computed insight lines are kept either way.
    """
    if chart_type is not None and chart_type not in CHART_TYPES:
        raise ValueError(f"{chart_type} is not a chart this app can draw.")  # before any query runs
    query = _guarded(sql, session)
    result = _run(session, query.sql)
    kinds = column_kinds(result, query, session.catalog)
    table = build_table(result, kinds)

    computed, insights = describe(table, kinds, kind, title)
    return InsightTile(
        id=tile_id, title=title, kind=kind,
        statement=statement or computed, insights=insights,
        chart=_chart(table, kinds, title, chart_type), table=table,
        sql=query.sql, tables_used=query.tables,
        caveats=null_caveats(query, session.catalog) + fan_out_risks(query, session.catalog),
        ask=ask,
    )


def _guarded(sql: str, session: SessionLike) -> GuardedQuery:
    """The same allow-list guard a model's SQL goes through, and the re-rendered SQL it
    returns is what runs. Our SQL is assembled from catalog identifiers, so a rejection here
    is a bug in a template rather than a hostile question — but it is still refused rather
    than run, because "we wrote it" is not a security property."""
    try:
        return validate_sql(sql, session.catalog)
    except GuardError as exc:
        raise ValueError(exc.message + (f" {exc.suggestion}" if exc.suggestion else "")) from exc


def _chart(table: ResultTable, kinds: list[str], title: str, chart_type: str | None) -> ChartSpec:
    """The rules pick the roles; the caller may pick the picture.

    An override is ignored when the rules found nothing to plot (`y` is empty, so the spec is
    a table): forcing "bar" onto a spec with no x or y would render an empty chart.
    """
    spec = choose_chart(table, kinds, title)
    if chart_type is None or not spec.y:
        return spec
    return spec.model_copy(update={"type": chart_type})


def _run(session: SessionLike, sql: str) -> ExecResult:
    """Execute on a cursor of this session's locked-down connection, with the same timeout the
    chat uses. DuckDB's own error text can quote a cell value, so it is never passed on: a
    template query that fails is our bug, and the analyst can only be told to move on."""
    try:
        return execute(session.cursor(), sql, timeout_s=settings.query_timeout_s, row_cap=ROW_CAP)
    except QueryTimeout as exc:
        raise ValueError(str(exc)) from exc
    except QueryError as exc:
        raise ValueError("This analysis could not be calculated from your files."
                         " Try it on one file, or ask the question in the chat instead.") from exc
