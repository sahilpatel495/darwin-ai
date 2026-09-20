"""The tile runner: one path to the screen, and a plain sentence when there is no tile."""

import pytest
from app.insights import sqlbuild as sb
from app.insights.runner import ROW_CAP, run_tile
from app.query.presentation import to_display
from tests.fixtures import CANARY_EMAIL, CANARY_NAME, make_session


@pytest.fixture
def session():
    return make_session()


def breakdown_sql(session) -> str:
    """Exactly how a guided analysis assembles a cross-file breakdown: every identifier from
    the catalog, every option from an allow-list."""
    group = sb.resolve("employees.department", session.catalog, ("category",))
    measure = sb.resolve("salary_register.gross", session.catalog, ("measure",))
    total = sb.aggregate("sum", f"{sb.ident(measure.table)}.{sb.ident(measure.column)}")
    return (f"SELECT {sb.ident(group.table)}.{sb.ident(group.column)} AS department,"
            f" {total} AS total_gross"
            f" {sb.from_clause([group, measure], session.catalog)} GROUP BY 1 ORDER BY 2 DESC")


# ---- the happy path ------------------------------------------------------------------------


def test_a_breakdown_tile_is_complete(session):
    tile = run_tile(session, tile_id="pay-by-dept", title="Gross pay by department",
                    kind="breakdown", sql=breakdown_sql(session),
                    ask="How has gross pay moved by department?")
    assert tile.id == "pay-by-dept" and tile.kind == "breakdown"
    assert tile.statement == ("Engineering is highest at ₹12.00 L and HR lowest at ₹2.70 L,"
                              " across 3 groups.")
    assert tile.insights and all(line.endswith(".") for line in tile.insights)
    assert tile.chart.type == "bar" and tile.chart.value_format == "currency_inr"
    assert tile.table.row_count == 3
    assert sorted(tile.tables_used) == ["employees", "salary_register"]
    assert tile.ask == "How has gross pay moved by department?"


def test_the_sql_on_the_tile_is_the_guard_rewritten_sql_that_actually_ran(session):
    tile = run_tile(session, tile_id="t", title="t", kind="breakdown", sql=breakdown_sql(session))
    assert tile.sql.startswith("SELECT") and '"employees"' in tile.sql
    session.cursor().execute(tile.sql)  # the analyst can paste it and get the same rows


def test_the_same_tile_twice_is_identical(session):
    """No model, no clock, no randomness: an overview must not change between two loads."""
    one = run_tile(session, tile_id="t", title="t", kind="breakdown", sql=breakdown_sql(session))
    two = run_tile(session, tile_id="t", title="t", kind="breakdown", sql=breakdown_sql(session))
    assert one.model_dump() == two.model_dump()


def test_numbers_are_formatted_the_way_answers_format_them(session):
    tile = run_tile(session, tile_id="t", title="Total gross", kind="kpi",
                    sql='SELECT sum("gross") AS total_gross FROM "salary_register"')
    total = tile.table.rows[0][0]
    assert tile.table.display[0][0] == to_display(total, "currency")
    assert tile.statement == f"Total gross is {to_display(total, 'currency')}."


def test_a_caller_supplied_statement_wins_but_the_computed_lines_stay(session):
    tile = run_tile(session, tile_id="t", title="t", kind="breakdown",
                    sql=breakdown_sql(session), statement="Pay is concentrated in Engineering.")
    assert tile.statement == "Pay is concentrated in Engineering."
    assert tile.insights


def test_an_empty_result_is_a_tile_not_an_error(session):
    tile = run_tile(session, tile_id="t", title="Exits", kind="breakdown",
                    sql="SELECT \"department\", count(*) AS n FROM \"employees\""
                        " WHERE \"exit_date\" IS NOT NULL AND \"department\" = 'Legal' GROUP BY 1")
    assert tile.statement == "There is nothing to show for this yet."
    assert tile.table.row_count == 0 and tile.insights == []


# ---- charts --------------------------------------------------------------------------------


def test_a_requested_chart_type_keeps_the_roles_the_rules_found(session):
    rules = run_tile(session, tile_id="t", title="t", kind="breakdown", sql=breakdown_sql(session))
    donut = run_tile(session, tile_id="t", title="t", kind="share",
                     sql=breakdown_sql(session), chart_type="donut")
    assert rules.chart.type == "bar" and donut.chart.type == "donut"
    assert (donut.chart.x, donut.chart.y) == (rules.chart.x, rules.chart.y)


def test_a_requested_chart_type_is_ignored_when_there_is_nothing_to_plot(session):
    """Forcing "bar" on a result with no measure would draw an empty chart."""
    tile = run_tile(session, tile_id="t", title="t", kind="quality", chart_type="bar",
                    sql='SELECT DISTINCT "department" FROM "employees"')
    assert tile.chart.type == "table"


def test_an_unknown_chart_type_is_refused(session):
    with pytest.raises(ValueError, match="not a chart this app can draw"):
        run_tile(session, tile_id="t", title="t", kind="breakdown",
                 sql=breakdown_sql(session), chart_type="sankey")


# ---- caveats -------------------------------------------------------------------------------


def test_null_caveats_are_attached(session):
    """One of the eight fixture employees has no CTC, so an average over it is an average of
    seven and the tile has to say so."""
    tile = run_tile(session, tile_id="t", title="Average CTC", kind="kpi",
                    sql='SELECT avg("ctc") AS avg_ctc FROM "employees"')
    assert any("no ctc" in caveat.lower() for caveat in tile.caveats)


def test_a_fan_out_join_is_flagged_rather_than_shown_as_a_clean_number(session):
    """Summing the one-side of a 1:N link counts each employee once per payslip. The number is
    still shown — an analyst may want it — but never without the warning."""
    tile = run_tile(session, tile_id="t", title="CTC by pay month", kind="trend",
                    sql='SELECT "salary_register"."pay_month", sum("employees"."ctc") AS ctc'
                        ' FROM "employees" JOIN "salary_register"'
                        ' ON "employees"."emp_id" = "salary_register"."emp_code" GROUP BY 1')
    assert any("more than once" in c or "repeat" in c.lower() for c in tile.caveats)


# ---- refusals are sentences, never stack traces --------------------------------------------


def test_a_guard_rejection_becomes_a_plain_sentence(session):
    with pytest.raises(ValueError) as caught:
        run_tile(session, tile_id="t", title="t", kind="kpi",
                 sql="DROP TABLE employees")
    message = str(caught.value)
    assert message == "Only queries that read data are allowed. This one would change or export data."


def test_an_unknown_column_refusal_carries_the_suggestion(session):
    with pytest.raises(ValueError, match="Did you mean"):
        run_tile(session, tile_id="t", title="t", kind="kpi",
                 sql='SELECT "departmnt" FROM "employees"')


def test_a_broken_query_never_leaks_duckdb_error_text(session):
    """DuckDB quotes cell values in its errors. A tile is our bug, not the analyst's, so they
    get a next step instead of a conversion error carrying someone's name."""
    with pytest.raises(ValueError) as caught:
        run_tile(session, tile_id="t", title="t", kind="kpi",
                 sql='SELECT "name"::INTEGER AS n FROM "employees"')
    message = str(caught.value)
    assert message == ("This analysis could not be calculated from your files."
                       " Try it on one file, or ask the question in the chat instead.")
    assert CANARY_NAME not in message and CANARY_EMAIL not in message


def test_a_timeout_is_a_sentence_with_a_next_step(session, monkeypatch):
    from dataclasses import replace

    from app.insights import runner
    monkeypatch.setattr(runner, "settings", replace(runner.settings, query_timeout_s=0.5))
    with pytest.raises(ValueError, match="so it was stopped"):
        run_tile(session, tile_id="t", title="t", kind="kpi",
                 sql="SELECT count(*) AS n FROM range(100000000) a, range(100000) b")


# ---- limits --------------------------------------------------------------------------------


def test_rows_are_capped_and_the_cap_is_reported(session, monkeypatch):
    from app.insights import runner
    monkeypatch.setattr(runner, "ROW_CAP", 3)
    tile = run_tile(session, tile_id="t", title="Payslips", kind="quality",
                    sql='SELECT "emp_code", "gross" FROM "salary_register" ORDER BY 1, 2')
    assert tile.table.row_count == 3 and tile.table.truncated


def test_the_default_cap_is_a_card_not_an_export():
    assert ROW_CAP == 500
