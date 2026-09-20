"""What the analyst reads: Indian number formatting, column units, and the chart rules."""
# ruff: noqa: DTZ001 - DuckDB returns naive datetimes for TIMESTAMP columns, so the tests use them.

from datetime import date, datetime
from decimal import Decimal

import pytest
from app.contracts import ResultTable
from app.query.executor import ExecResult
from app.query.guard import GuardedQuery
from app.query.presentation import build_table, choose_chart, column_kinds, to_display

from tests.fixtures import make_session

# --------------------------------------------------------------------------- to_display


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (1234567, "integer", "12,34,567"),
        (1500, "integer", "1,500"),
        (1234567.5, "currency", "₹12.35 L"),
        (12000000, "currency", "₹1.20 Cr"),
        (45000, "currency", "₹45,000"),
        (99999.5, "currency", "₹99,999.50"),
        (-1234567.5, "currency", "-₹12.35 L"),
        (12.345, "percent", "12.3%"),
        (3.14159, "decimal", "3.14"),
        (0.5, "decimal", "0.5"),
        (date(2025, 4, 4), "date", "04 Apr 2025"),
        (True, "text", "Yes"),
        (None, "currency", "—"),
        (None, "text", "—"),
    ],
)
def test_to_display_cases_from_the_brief(value, kind, expected):
    assert to_display(value, kind) == expected


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (False, "text", "No"),
        (7.0, "decimal", "7"),
        (1234567.891, "decimal", "12,34,567.89"),
        (0.0045, "decimal", "0.0045"),  # a small rate must not be shown as a flat 0
        (0.1 + 0.2 - 0.3, "decimal", "0"),  # 5.6e-17 of floating-point dust is not a rate
        (-(0.1 + 0.2 - 0.3), "decimal", "0"),
        (float("inf"), "currency", "—"),
        (float("-inf"), "percent", "—"),
        (-0.0, "currency", "₹0"),  # never "-₹0"
        (-0.04, "percent", "0.0%"),  # never "-0.0%"
        (-99999.995, "currency", "-₹1.00 L"),
        (-1500, "integer", "-1,500"),
        (100, "integer", "100"),
        (0, "currency", "₹0"),
        (100000, "currency", "₹1.00 L"),
        (9999999, "currency", "₹1.00 Cr"),  # never "₹100.00 L"
        (99999.999, "currency", "₹1.00 L"),
        (123456789012, "currency", "₹12,345.68 Cr"),
        (Decimal("1234567.50"), "currency", "₹12.35 L"),
        (2.5, "percent", "2.5%"),
        (50, "percent", "50.0%"),
        (datetime(2025, 1, 1), "date", "01 Jan 2025"),
        (datetime(2025, 1, 1, 14, 30), "date", "01 Jan 2025 14:30"),
        ("2025-04-04", "date", "04 Apr 2025"),
        (date(2025, 4, 1), "date", "01 Apr 2025"),  # the day is dropped per column, not per value

        (float("nan"), "decimal", "—"),
        (2025, "text", "2025"),
        ("Bengaluru", "text", "Bengaluru"),
        ("not a number", "integer", "not a number"),  # never crash on a surprising value
        (1e30, "currency", "1e+30"),  # a hostile file's absurd number is shown as it is, not a crash
    ],
)
def test_to_display_edge_cases(value, kind, expected):
    assert to_display(value, kind) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2025, 1, 1), "Jan 2025"),
        (datetime(2025, 1, 1), "Jan 2025"),
        ("2025-01-01", "Jan 2025"),
        (None, "—"),
    ],
)
def test_to_display_writes_a_month_when_the_caller_says_the_column_is_monthly(value, expected):
    assert to_display(value, "date", month=True) == expected


def test_half_is_rounded_up_the_way_a_payslip_does_it():
    # Python's round() would give 0.12 (banker's rounding); an analyst checking by hand expects 0.13.
    assert to_display(0.125, "decimal") == "0.13"


# --------------------------------------------------------------------------- column_kinds

JOIN = "FROM employees e JOIN salary_register s ON e.emp_id = s.emp_code"


def kinds_for(sql: str, columns: list[str], duck_types: list[str], rows=(), tables=("employees", "salary_register")):
    result = ExecResult(columns=columns, duck_types=duck_types, rows=list(rows))
    return column_kinds(result, GuardedQuery(sql=sql, tables=list(tables)), make_session().catalog)


def test_kinds_follow_the_source_column_the_alias_and_the_database_type():
    sql = (
        "SELECT e.department, sum(s.gross) AS total_gross, count(*) AS employees, "
        f"round(100.0 * sum(s.net) / sum(s.gross), 1) AS net_pct {JOIN} GROUP BY e.department"
    )
    kinds = kinds_for(sql, ["department", "total_gross", "employees", "net_pct"],
                      ["VARCHAR", "DOUBLE", "BIGINT", "DOUBLE"])
    assert kinds == ["text", "currency", "integer", "percent"]


def test_money_is_recognised_whatever_the_alias_says():
    sql = "SELECT e.department, avg(e.ctc) AS avg_salary FROM employees e GROUP BY e.department"
    assert kinds_for(sql, ["department", "avg_salary"], ["VARCHAR", "DOUBLE"]) == ["text", "currency"]


def test_a_plain_money_column_and_select_star_are_currency_by_name():
    assert kinds_for("SELECT e.ctc FROM employees e", ["ctc"], ["DOUBLE"]) == ["currency"]
    star = kinds_for("SELECT * FROM salary_register", ["emp_code", "pay_month", "gross", "net"],
                     ["VARCHAR", "DATE", "DOUBLE", "DOUBLE"])
    assert star == ["text", "date", "currency", "currency"]


def test_counting_people_is_never_shown_in_rupees():
    sql = (
        "SELECT count(s.gross) AS payslips, count(DISTINCT s.gross) AS distinct_amounts, "
        "sum(CASE WHEN s.gross > 100000 THEN 1 ELSE 0 END) AS high_earners, "
        "count(*) FILTER (WHERE s.gross > 100000) AS also_high, "
        "rank() OVER (ORDER BY sum(s.gross) DESC) AS pay_rank FROM salary_register s"
    )
    kinds = kinds_for(sql, ["payslips", "distinct_amounts", "high_earners", "also_high", "pay_rank"],
                      ["BIGINT", "BIGINT", "HUGEINT", "BIGINT", "BIGINT"])
    assert "currency" not in kinds


def test_average_pay_per_head_is_money_but_a_ratio_of_two_amounts_is_not():
    sql = f"SELECT sum(s.gross) / count(DISTINCT s.emp_code) AS per_head, sum(s.net) / sum(s.gross) AS take_home_ratio {JOIN}"
    assert kinds_for(sql, ["per_head", "take_home_ratio"], ["DOUBLE", "DOUBLE"]) == ["currency", "decimal"]


def test_a_correlation_with_pay_is_a_coefficient_not_rupees():
    sql = "SELECT corr(e.ctc, s.gross) AS pay_link, stddev(e.ctc) AS spread " + JOIN
    assert kinds_for(sql, ["pay_link", "spread"], ["DOUBLE", "DOUBLE"]) == ["decimal", "currency"]


def test_money_survives_a_pre_aggregating_cte():
    sql = (
        "WITH pay AS (SELECT s.emp_code, sum(s.gross) AS paid FROM salary_register s GROUP BY s.emp_code) "
        "SELECT e.department, sum(pay.paid) AS total FROM pay JOIN employees e ON e.emp_id = pay.emp_code GROUP BY 1"
    )
    assert kinds_for(sql, ["department", "total"], ["VARCHAR", "DOUBLE"]) == ["text", "currency"]


def test_whole_number_group_keys_are_labels_so_a_year_is_not_shown_as_2_025():
    sql = "SELECT year(e.date_of_joining) AS joined_in, count(*) AS joiners FROM employees e GROUP BY 1"
    assert kinds_for(sql, ["joined_in", "joiners"], ["BIGINT", "BIGINT"]) == ["text", "integer"]
    # The same label arriving through a CTE is caught by its calendar name instead.
    through_cte = "WITH y AS (SELECT 1) SELECT y.join_year, y.joiners FROM y"
    rows = [(2024, 5), (2025, 3)]
    assert kinds_for(through_cte, ["join_year", "joiners"], ["BIGINT", "BIGINT"], rows) == ["text", "integer"]
    # ...but a measure that merely ends in "year" keeps its number formatting.
    assert kinds_for(through_cte, ["exits_this_year", "joiners"], ["BIGINT", "BIGINT"], [(12, 5)]) == ["integer", "integer"]


def test_database_types_map_to_kinds_and_unreadable_sql_never_raises():
    kinds = kinds_for("this is not sql (", ["a", "b", "c", "d", "e", "f", "gross"],
                      ["DATE", "TIMESTAMP", "BOOLEAN", "DECIMAL(18,2)", "HUGEINT", "VARCHAR", "DOUBLE"])
    assert kinds == ["date", "date", "text", "decimal", "integer", "text", "currency"]


# --------------------------------------------------------------------------- build_table


def test_build_table_is_json_safe_with_parallel_display_strings():
    result = ExecResult(
        columns=["month", "department", "total_gross", "share_pct", "active"],
        duck_types=["DATE", "VARCHAR", "DECIMAL(18,2)", "DOUBLE", "BOOLEAN"],
        rows=[(date(2025, 1, 1), "Engineering", Decimal("1200000.00"), 57.14, True),
              (datetime(2025, 2, 1), None, None, float("nan"), False)],
        truncated=True,
    )
    table = build_table(result, ["date", "text", "currency", "percent", "text"])
    assert table.columns == result.columns
    assert table.rows == [["2025-01-01", "Engineering", 1200000.0, 57.14, True],
                          ["2025-02-01", None, None, None, False]]
    # Both dates in that column are the first of a month, so the column is written as months.
    assert table.display == [["Jan 2025", "Engineering", "₹12.00 L", "57.1%", "Yes"],
                             ["Feb 2025", "—", "—", "—", "No"]]
    assert table.row_count == 2 and table.truncated is True
    table.model_dump_json()  # the API serialises this; NaN or Decimal would break it


def test_a_month_column_drops_the_day_and_a_dated_one_next_to_it_keeps_it():
    """`date_trunc('month', ...)` and a Pay Month column hold nothing but first-of-month dates,
    where "01 Jan 2025" invites the reader to think something happened on the 1st. The decision
    is per column: a real joining date in the next column still names its day."""
    result = ExecResult(
        columns=["month", "joined_on", "total_gross"],
        duck_types=["DATE", "DATE", "DOUBLE"],
        rows=[(date(2025, 1, 1), date(2025, 1, 1), 1200000.0),
              (date(2025, 2, 1), date(2025, 2, 14), 900000.0)],
    )
    table = build_table(result, ["date", "date", "currency"])
    assert table.display == [["Jan 2025", "01 Jan 2025", "₹12.00 L"],
                             ["Feb 2025", "14 Feb 2025", "₹9.00 L"]]


def test_a_column_of_timestamps_and_one_with_no_dates_at_all_keep_their_formatting():
    """A punch time is not a month even when it falls on the 1st, and an all-empty column has
    nothing to read a pattern from: both must come out exactly as they did before."""
    result = ExecResult(
        columns=["punched_at", "left_on"], duck_types=["TIMESTAMP", "DATE"],
        rows=[(datetime(2025, 1, 1, 9, 14), None), (datetime(2025, 2, 1, 9, 2), None)],
    )
    table = build_table(result, ["date", "date"])
    assert table.display == [["01 Jan 2025 09:14", "—"], ["01 Feb 2025 09:02", "—"]]


# --------------------------------------------------------------------------- choose_chart


def table_of(columns: list[str], rows: list[list], truncated: bool = False) -> ResultTable:
    return ResultTable(columns=columns, rows=rows, display=[[str(v) for v in r] for r in rows],
                       row_count=len(rows), truncated=truncated)


def test_a_single_value_is_a_kpi_tile_with_a_clean_title():
    chart = choose_chart(table_of(["attrition_pct"], [[28.6]]), ["percent"], "  What is the attrition rate for 2025?  ")
    assert (chart.type, chart.y, chart.value_format) == ("kpi", ["attrition_pct"], "percent")
    assert chart.title == "Attrition rate for 2025"


def test_a_single_row_headlines_its_final_measure():
    table = table_of(["exits", "avg_headcount", "attrition_pct"], [[2, 7.0, 28.6]])
    chart = choose_chart(table, ["integer", "decimal", "percent"], "attrition rate?")
    assert (chart.type, chart.y, chart.value_format) == ("kpi", ["attrition_pct"], "percent")


def test_dates_with_measures_make_a_line():
    table = table_of(["month", "days_present", "days_absent"], [["2025-01-01", 168, 8], ["2025-02-01", 170, 6]])
    chart = choose_chart(table, ["date", "integer", "integer"], "Show days present and absent per month")
    assert (chart.type, chart.x, chart.y) == ("line", "month", ["days_present", "days_absent"])
    assert chart.title == "Days present and absent per month" and chart.value_format == "number"


def test_one_category_and_one_measure_make_a_bar():
    table = table_of(["department", "total_gross"], [["Engineering", 1200000.0], ["Sales", 633334.0]])
    chart = choose_chart(table, ["text", "currency"], "What is the total gross pay by department?")
    assert (chart.type, chart.x, chart.y, chart.note) == ("bar", "department", ["total_gross"], None)
    assert chart.value_format == "currency_inr" and chart.title == "Total gross pay by department"


def test_more_than_twelve_groups_keep_the_bar_and_say_what_is_hidden():
    rows = [[f"Team {i}", 100 - i] for i in range(43)]
    chart = choose_chart(table_of(["team", "people"], rows), ["text", "integer"], "headcount by team")
    assert chart.type == "bar"
    assert chart.note == "Showing the top 12 of 43 groups. The table has all of them."


def test_the_note_does_not_claim_top_when_rows_are_unsorted_or_cut_off():
    unsorted = [[f"Team {i}", i] for i in range(20)]
    chart = choose_chart(table_of(["team", "people"], unsorted), ["text", "integer"], "headcount by team")
    assert chart.note == "Showing the first 12 of 20 groups. The table has all of them."
    cut = choose_chart(table_of(["team", "people"], unsorted, truncated=True), ["text", "integer"], "q")
    assert "more than 20 groups" in cut.note


def test_two_categories_and_a_measure_make_a_grouped_bar():
    rows = [["Engineering", "F", 1], ["Engineering", "M", 2], ["Sales", "F", 2], ["Sales", "M", 1]]
    chart = choose_chart(table_of(["department", "gender", "people"], rows), ["text", "text", "integer"], "q")
    assert (chart.type, chart.x, chart.series, chart.y) == ("grouped_bar", "department", "gender", ["people"])


def test_a_grouped_bar_too_dense_to_read_falls_back_to_the_table():
    rows = [[f"Dept {d}", f"City {c}", 1] for d in range(20) for c in range(10)]
    chart = choose_chart(table_of(["department", "city", "people"], rows), ["text", "text", "integer"], "q")
    assert chart.type == "table" and "table" in chart.note.lower()


def test_two_measures_make_a_scatter():
    table = table_of(["tenure_years", "ctc"], [[1.5, 900000.0], [6.0, 2400000.0]])
    chart = choose_chart(table, ["decimal", "currency"], "q")
    assert (chart.type, chart.x, chart.y, chart.value_format) == ("scatter", "tenure_years", ["ctc"], "currency_inr")


def test_everything_else_is_a_table():
    listing = table_of(["emp_id", "department", "location", "ctc"], [["E001", "HR", "Pune", 1.0], ["E002", "HR", "Pune", 2.0]])
    assert choose_chart(listing, ["text", "text", "text", "currency"], "q").type == "table"
    mixed = table_of(["department", "people", "avg_ctc"], [["HR", 2, 9.0], ["Sales", 3, 12.0]])
    assert choose_chart(mixed, ["text", "integer", "currency"], "q").type == "table"
    assert choose_chart(table_of(["department"], []), ["text"], "q").type == "table"
    assert choose_chart(table_of(["name"], [["Asha"]]), ["text"], "q").type == "table"


def test_two_columns_with_one_name_are_shown_as_a_table():
    # DuckDB returns both as "count_star()"; a chart spec could not say which one it means.
    twins = table_of(["department", "count_star()", "count_star()"], [["HR", 2, 2], ["Sales", 3, 3]])
    assert choose_chart(twins, ["text", "integer", "integer"], "q").type == "table"


def test_a_big_or_broken_result_never_breaks_presentation():
    rows = [(f"Team {i}", float("nan") if i % 2 else float(i)) for i in range(5000)]
    result = ExecResult(columns=["team", "avg_ctc"], duck_types=["VARCHAR", "DOUBLE"], rows=rows, truncated=True)
    table = build_table(result, ["text", "currency"])
    assert table.row_count == 5000 and table.rows[1] == ["Team 1", None] and table.display[1] == ["Team 1", "—"]
    chart = choose_chart(table, ["text", "currency"], "average ctc by team")
    assert chart.type == "bar" and "more than 5,000 groups" in chart.note
    table.model_dump_json()


def test_titles_are_short_single_line_plain_text():
    chart = choose_chart(table_of(["n"], [[1]]), ["integer"], "show me\n the   headcount " + "x" * 200)
    assert "\n" not in chart.title and len(chart.title) <= 80 and chart.title.startswith("Headcount x")
    assert choose_chart(table_of(["n"], [[1]]), ["integer"], "How many people joined in 2024?").title == "How many people joined in 2024"
