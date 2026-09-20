"""The guided analyses: ten questions asked by picking columns, with no model.

Every number below is hand-checked against tests/fixtures.py: 8 employees, 2 pay months of
salary (gross = ctc / 12, rounded), 3 attendance months per quarter. The point of these tests
is that the same picks always produce the same sentence and the same rupees, and that a
request cannot reach SQL with anything the catalog did not put there.
"""

import json
import time
from pathlib import Path

import pytest
from app.config import settings
from app.contracts import ColumnProfile, DataHealth, TableProfile
from app.insights import analyses
from app.insights.models import AnalysisRequest
from app.insights.runner import ROW_CAP
from app.sessions import SessionStore
from tests.fixtures import CANARY_EMAIL, CANARY_NAME, make_session

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_JSON = ROOT / "frontend/src/fixtures/analyses.json"

# One valid request per kind, reused by the tests that must hold for all ten.
REQUESTS = {
    "breakdown": AnalysisRequest(
        kind="breakdown", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "average"}),
    "trend": AnalysisRequest(
        kind="trend", inputs={"measure": "attendance_q1.days_present",
                              "date": "attendance_q1.month"},
        options={"aggregate": "sum"}),
    "top_n": AnalysisRequest(
        kind="top_n", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "sum", "top_n": "5"}),
    "distribution": AnalysisRequest(kind="distribution", inputs={"measure": "employees.ctc"}),
    "share": AnalysisRequest(
        kind="share", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "sum"}),
    "pivot": AnalysisRequest(
        kind="pivot", inputs={"measure": "employees.ctc", "by": "employees.department",
                              "across": "employees.location"},
        options={"aggregate": "count"}),
    "correlation": AnalysisRequest(
        kind="correlation", inputs={"measure": "attendance_q1.days_present",
                                    "measure_b": "attendance_q1.days_absent"}),
    "change": AnalysisRequest(
        kind="change", inputs={"measure": "salary_register.gross",
                               "date": "salary_register.pay_month"},
        options={"aggregate": "sum"}),
    "outliers": AnalysisRequest(kind="outliers", inputs={"measure": "employees.ctc"}),
    "compare": AnalysisRequest(
        kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "average", "group_a": "Engineering", "group_b": "Sales"}),
}


@pytest.fixture
def session():
    return make_session()


# ---- the picker ----------------------------------------------------------------------------


def test_the_catalog_offers_every_kind_and_only_columns_that_fill_a_slot(session):
    picker = analyses.catalog(session)
    assert [kind.key for kind in picker.kinds] == [
        "breakdown", "trend", "top_n", "distribution", "share", "pivot", "correlation",
        "change", "outliers", "compare"]
    refs = {choice.ref: choice.kind for choice in picker.columns}
    assert refs["employees.ctc"] == "measure"
    assert refs["employees.department"] == "category"
    assert refs["employees.date_of_joining"] == "date"


def test_personal_data_and_identifiers_are_never_offered(session):
    """The list is what the UI shows; a name in it is one click away from being grouped by."""
    refs = [choice.ref for choice in analyses.catalog(session).columns]
    assert "employees.name" not in refs and "employees.email" not in refs  # PII
    assert "employees.emp_id" not in refs and "salary_register.emp_code" not in refs  # ids


def test_a_union_view_does_not_repeat_the_columns_of_the_files_it_unions(session):
    refs = [choice.ref for choice in analyses.catalog(session).columns]
    assert "attendance_q1.days_present" in refs and "attendance_q2.days_present" in refs
    assert not any(ref.startswith("attendance_all.") for ref in refs)


def test_a_column_is_labelled_the_way_the_file_labels_it(session):
    choice = next(c for c in analyses.catalog(session).columns if c.ref == "employees.ctc")
    assert choice.label == "ctc" and choice.table_label == "employees.csv"


def test_a_category_publishes_its_own_values_and_nothing_else_does(session):
    """The compare pickers are filled from here. A number and a date have no group to pick, and
    listing a date's distinct values would put row data on the screen for nothing."""
    columns = {choice.ref: choice for choice in analyses.catalog(session).columns}
    assert columns["employees.department"].values == ["Engineering", "HR", "Sales"]
    assert columns["employees.ctc"].values == []
    assert columns["employees.date_of_joining"].values == []


def test_a_category_the_profiler_did_not_list_offers_an_empty_list_rather_than_guessing(session):
    """Above the profiler's own cap `values` is None, which is not a short list of groups —
    and `_group_value` refuses those columns too, so the picker and the runner agree."""
    department = next(c for t in session.catalog.tables if t.name == "employees"
                      for c in t.columns if c.name == "department")
    department.values = None
    choice = next(c for c in analyses.catalog(session).columns
                  if c.ref == "employees.department")
    assert choice.values == []


def test_compare_publishes_two_open_groups_that_say_where_the_choices_come_from(session):
    """The tenth analysis could not be run from the picker: its two group lists were empty and
    nothing on the option said they are filled from the column the analyst picks."""
    compare = next(kind for kind in analyses.KINDS if kind.key == "compare")
    groups = [option for option in compare.options if option.key in ("group_a", "group_b")]
    assert len(groups) == 2
    assert all(option.choices == [] for option in groups)
    assert all("values" in option.label.lower() for option in groups)


def test_a_workbook_that_gave_several_tables_names_the_sheet(session):
    """One file, two tables: "Salary_Register_2025.xlsx" alone would be ambiguous."""
    pay = next(t for t in session.catalog.tables if t.name == "salary_register")
    second_sheet = next(t for t in session.catalog.tables if t.name == "attendance_q1")
    pay.sheet, second_sheet.sheet = "Register", "Bonuses"
    second_sheet.source_file = pay.source_file
    labels = {c.ref: c.table_label for c in analyses.catalog(session).columns}
    assert labels["salary_register.gross"] == "Salary_Register_2025.xlsx (Register)"
    assert labels["attendance_q1.days_present"] == "Salary_Register_2025.xlsx (Bonuses)"
    assert labels["employees.ctc"] == "employees.csv"  # one table from that file: no sheet


def test_the_kinds_match_the_shape_the_frontend_was_built_against():
    """frontend/src/fixtures/analyses.json is the mock the UI is coded against. Every kind in
    it must be exactly the kind this module publishes, or the picker breaks in mock mode."""
    if not FIXTURE_JSON.exists():
        pytest.skip("frontend fixtures not present")
    published = {kind["key"]: kind for kind in json.loads(FIXTURE_JSON.read_text())["kinds"]}
    ours = {kind.key: kind.model_dump() for kind in analyses.KINDS}
    assert published  # the file would otherwise pass by being empty
    for key, kind in published.items():
        assert ours[key] == kind


# ---- one test per kind, with hand-checked numbers -------------------------------------------


def test_breakdown(session):
    """Engineering (24, 18, 30 L) averages 24 L; Sales (15, 12, 11 L) 12.67 L; HR is 9 L
    because the employee with no CTC is not counted as a zero."""
    tile = analyses.run(session, REQUESTS["breakdown"])
    assert tile.title == "Average CTC by Department"
    assert tile.table.columns == ["department", "average_ctc"]
    assert tile.table.display == [["Engineering", "₹24.00 L"], ["Sales", "₹12.67 L"],
                                 ["HR", "₹9.00 L"]]
    assert tile.chart.type == "bar" and tile.chart.value_format == "currency_inr"
    assert tile.statement == ("Engineering is highest at ₹24.00 L and HR lowest at ₹9.00 L,"
                              " across 3 groups.")
    assert tile.ask == "How has average ctc by department changed over time?"


def test_trend(session):
    """21 days present for all 8 people in January, 22 in February, 20 in March."""
    tile = analyses.run(session, REQUESTS["trend"])
    assert tile.table.columns == ["month", "total_days_present"]
    assert [row[1] for row in tile.table.rows] == [168, 176, 160]
    assert tile.chart.type == "line" and tile.chart.x == "month"
    assert tile.statement == ("Total Days Present by Month went from 168 (Jan 2025)"
                              " to 160 (Mar 2025).")


def test_a_trend_split_by_a_group_draws_one_line_per_group(session):
    tile = analyses.run(session, AnalysisRequest(
        kind="trend", inputs={"measure": "salary_register.gross",
                              "date": "salary_register.pay_month",
                              "by": "employees.department"}, options={"aggregate": "sum"}))
    assert tile.chart.type == "line" and tile.chart.series == "department"
    assert tile.table.columns == ["pay_month", "department", "total_gross"]
    assert tile.table.display[0] == ["Jan 2025", "Engineering", "₹6.00 L"]


def test_top_n(session):
    """Only three departments exist, so a top 5 is all of them, highest first."""
    tile = analyses.run(session, REQUESTS["top_n"])
    assert tile.title == "Top 5 Departments by Total CTC"
    assert tile.table.display == [["Engineering", "₹72.00 L"], ["Sales", "₹38.00 L"],
                                 ["HR", "₹9.00 L"]]
    assert tile.chart.type == "bar"
    assert "LIMIT 5" in tile.sql


def test_distribution(session):
    """Seven CTC values from 9 L to 30 L: median 15 L, quartiles 11.5 L and 21 L. The 2.1 M
    span buckets into round 2.5 L bands, not into 2.1 L tenths."""
    tile = analyses.run(session, REQUESTS["distribution"])
    assert tile.title == "How CTC Is Spread"
    assert tile.chart.type == "histogram" and tile.chart.x == "ctc_band"
    assert tile.table.display[:2] == [["₹7.50 L", "1"], ["₹10.00 L", "2"]]
    assert tile.statement == ("Half of ctc falls between ₹11.50 L and ₹21.00 L,"
                              " and the median is ₹15.00 L.")
    assert tile.insights[0] == "The lowest is ₹9.00 L and the highest is ₹30.00 L."


def test_a_distribution_of_whole_numbers_never_buckets_by_halves(session):
    """Days present run 20, 21, 22. A band width of 0.2 would be arithmetically correct and
    unreadable."""
    tile = analyses.run(session, AnalysisRequest(
        kind="distribution", inputs={"measure": "attendance_q1.days_present"}))
    assert [row[0] for row in tile.table.rows] == [20, 21, 22]
    assert tile.statement == "Half of days present falls between 20 and 22, and the median is 21."


def test_share(session):
    """72 L of 119 L is 60.5%. The share is computed from the whole total, not from the top row."""
    tile = analyses.run(session, REQUESTS["share"])
    assert tile.chart.type == "donut"
    assert tile.statement == ("Engineering is the largest share at 60.5% of the total"
                              " (₹72.00 L of ₹1.19 Cr).")


def test_a_share_of_many_groups_keeps_the_biggest_six_and_adds_up_the_rest(session):
    """The fixture has three departments, so nothing is lumped here; what is tested is that the
    remainder bucket is in the statement that runs, and that the chart stops being a donut."""
    department = next(c for t in session.catalog.tables if t.name == "employees"
                      for c in t.columns if c.name == "department")
    department.distinct_count = 20
    tile = analyses.run(session, REQUESTS["share"])
    assert "'Other'" in tile.sql and "place <= 6" in tile.sql
    assert tile.chart.type == "bar"  # a donut cannot show twenty slices


def test_a_share_of_averages_never_adds_averages_together(session):
    """Six averages added up is not a total, so those groups are never lumped into "Other" —
    and the tile stops calling itself a share at all. A donut of averages draws numbers as
    parts of a whole that does not exist, and the sentence under it would read a percentage off
    a denominator that means nothing. It is a breakdown, so it is drawn and read as one."""
    tile = analyses.run(session, AnalysisRequest(
        kind="share", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "average"}))
    assert "'Other'" not in tile.sql
    assert tile.chart.type == "bar" and tile.kind == "breakdown"
    assert tile.title == "Average CTC by Department"
    assert "share" not in tile.statement
    assert tile.statement == ("Engineering is highest at ₹24.00 L and HR lowest at ₹9.00 L,"
                              " across 3 groups.")


def test_a_share_of_a_count_is_still_a_donut_of_the_whole(session):
    """The control for the test above: a count does add up, so nothing changes for it."""
    tile = analyses.run(session, AnalysisRequest(
        kind="share", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "count"}))
    assert tile.chart.type == "donut" and tile.kind == "share"
    assert tile.title.startswith("Share of")
    assert "largest share" in tile.statement


def test_pivot(session):
    """Sales has both Mumbai employees; every other department/location pair has one."""
    tile = analyses.run(session, REQUESTS["pivot"])
    assert tile.title == "Number of Employees by Department and Location"
    assert tile.chart.type == "heatmap"
    assert tile.table.row_count == 7
    assert tile.statement == "Sales / Mumbai is the largest at 2, across 7 combinations."


def test_correlation(session):
    """days_absent is 2 - (days_present - 20) in the fixture, so the two move exactly opposite."""
    tile = analyses.run(session, REQUESTS["correlation"])
    assert tile.chart.type == "scatter"
    assert tile.statement == ("Days present and days absent move in opposite directions strongly"
                              " (correlation -1 over 24 rows).")
    assert tile.insights == ["Moving together is not proof that one causes the other."]
    assert "LIMIT 500" in tile.sql  # the coefficient uses every row; the picture is capped


def test_a_correlation_needs_two_columns_that_can_differ(session):
    with pytest.raises(ValueError, match="always moves with itself"):
        analyses.run(session, AnalysisRequest(
            kind="correlation", inputs={"measure": "employees.ctc",
                                        "measure_b": "employees.ctc"}))


def test_change(session):
    """Both pay months hold the same payroll, so the change is zero and says so rather than
    inventing a movement."""
    tile = analyses.run(session, REQUESTS["change"])
    assert tile.table.columns == ["previous_pay_month", "previous_total_gross",
                                  "current_pay_month", "current_total_gross", "change_in_gross"]
    assert tile.table.display[0] == ["Jan 2025", "₹10.52 L", "Feb 2025", "₹10.52 L", "₹0"]
    assert tile.statement == ("Total gross is unchanged at ₹10.52 L between Jan 2025"
                              " and Feb 2025.")


def test_a_change_with_only_one_period_says_there_is_nothing_to_compare(session):
    """Asked by year, the two pay months are one period. An empty previous figure must not be
    read as zero, which would report a 100% rise."""
    tile = analyses.run(session, AnalysisRequest(
        kind="change", inputs={"measure": "salary_register.gross",
                               "date": "salary_register.pay_month"},
        options={"aggregate": "sum", "grain": "year"}))
    assert tile.table.rows[0][1] is None
    assert tile.statement == ("There is only one year of total gross in this data"
                              " (Jan 2025), so there is nothing to compare it with.")


def test_a_change_split_by_a_group_is_drawn_as_a_bar_of_the_change(session):
    tile = analyses.run(session, AnalysisRequest(
        kind="change", inputs={"measure": "salary_register.gross",
                               "date": "salary_register.pay_month",
                               "by": "employees.department"}, options={"aggregate": "sum"}))
    assert tile.table.columns == ["department", "change_in_gross", "previous_total_gross",
                                  "current_total_gross"]
    assert tile.chart.type == "bar" and tile.chart.x == "department"
    assert tile.chart.y == ["change_in_gross"] and tile.chart.value_format == "currency_inr"
    # Every department moved by the same amount (nothing), so the rows are tied. A tie must
    # still come back in one fixed order, or the same file charts differently twice.
    assert tile.table.display == [["Engineering", "₹0", "₹6.00 L", "₹6.00 L"],
                                  ["HR", "₹0", "₹1.35 L", "₹1.35 L"],
                                  ["Sales", "₹0", "₹3.17 L", "₹3.17 L"]]


def test_outliers(session):
    """Quartiles 11.5 L and 21 L give a 9.5 L gap, so the fence runs from -2.75 L to 35.25 L.
    The 30 L salary is inside it: nothing here is unusual, and the tile says that rather than
    showing an empty table."""
    tile = analyses.run(session, REQUESTS["outliers"])
    assert tile.table.rows == []
    assert tile.statement == ("No ctc value is unusual: they all sit between -₹2.75 L"
                              " and ₹35.25 L.")
    assert tile.chart.type == "table"


def test_outliers_never_list_personal_data(session):
    """An unusual salary is a finding; the name next to it is a leak."""
    tile = analyses.run(session, REQUESTS["outliers"])
    assert tile.table.columns == ["emp_id", "department", "location", "gender",
                                   "date_of_joining", "exit_date", "ctc"]
    assert "name" not in tile.sql and "email" not in tile.sql


def test_outliers_say_nothing_about_groups_because_there_are_none(session):
    """A listing of rows is not a grouped result. Read as one it called individual salaries
    "the groups" and offered a percentage of their sum, neither of which is a fact about the
    outliers. Only the one line that is true of every listing stays."""
    session.conn.executemany(
        "INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?)",
        [("E009", "Test One", "one@example.com", "Sales", "Pune", "F", "2024-01-01", None, 90_000_000),
         ("E010", "Test Two", "two@example.com", "HR", "Mumbai", "M", "2024-01-01", None, 80_000_000)])
    tile = analyses.run(session, REQUESTS["outliers"])
    assert tile.table.row_count == 2
    assert tile.insights == [
        "Unusual is not the same as wrong: these are the rows worth checking."]


def test_compare(session):
    """24 L against 12.67 L: a gap of 11.33 L, which is 89.5% of the lower figure."""
    tile = analyses.run(session, REQUESTS["compare"])
    assert tile.title == "Average CTC: Engineering vs Sales"
    assert tile.chart.type == "bar"
    assert tile.statement == ("Engineering is ahead at ₹24.00 L, ₹11.33 L more than"
                              " Sales at ₹12.67 L.")
    assert tile.insights == ["That is 89.5% higher."]


def test_every_value_the_picker_publishes_runs_end_to_end(session):
    """What the picker offers has to be exactly what `run` accepts: a value in the list that
    raises is the dead button this analysis was published with."""
    department = next(c for c in analyses.catalog(session).columns
                      if c.ref == "employees.department")
    assert len(department.values) > 1
    for first, second in zip(department.values, department.values[1:], strict=False):
        tile = analyses.run(session, AnalysisRequest(
            kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
            options={"aggregate": "average", "group_a": first, "group_b": second}))
        assert tile.title.endswith(f": {first} vs {second}")
        assert f"'{first}'" in tile.sql and f"'{second}'" in tile.sql


def test_compare_with_no_group_chosen_asks_for_one_by_name(session):
    with pytest.raises(ValueError, match="Choose a value for"):
        analyses.run(session, AnalysisRequest(
            kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
            options={"aggregate": "average", "group_b": "Sales"}))


def test_compare_takes_the_catalogs_spelling_of_a_group_not_the_requests(session):
    tile = analyses.run(session, AnalysisRequest(
        kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "sum", "group_a": "engineering", "group_b": "sALES"}))
    assert "'Engineering'" in tile.sql and "'Sales'" in tile.sql
    assert "'engineering'" not in tile.sql


def test_compare_refuses_a_group_that_is_not_a_value_of_the_column(session):
    with pytest.raises(ValueError, match="is not a value in department"):
        analyses.run(session, AnalysisRequest(
            kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
            options={"group_a": "Engineering' OR 1 = 1 --", "group_b": "Sales"}))


# ---- two files -------------------------------------------------------------------------------


def test_columns_from_two_files_are_joined_through_the_active_link(session):
    """Gross pay lives in the salary register and departments live in the employee file. Each
    of the three departments is one month's payroll times two months."""
    tile = analyses.run(session, AnalysisRequest(
        kind="breakdown", inputs={"measure": "salary_register.gross",
                                  "by": "employees.department"}, options={"aggregate": "sum"}))
    assert sorted(tile.tables_used) == ["employees", "salary_register"]
    assert tile.table.display == [["Engineering", "₹12.00 L"], ["Sales", "₹6.33 L"],
                                 ["HR", "₹2.70 L"]]


def test_a_measure_from_the_one_side_grouped_by_the_many_side_is_refused(session):
    """One employee has many payslips, so summing the employee-side CTC across that join adds
    the same salary up once per payslip. This used to run and carry a caveat: the caveat sat
    under a number that was simply wrong, which is the one thing this app must not do."""
    with pytest.raises(ValueError) as caught:
        analyses.run(session, AnalysisRequest(
            kind="trend", inputs={"measure": "employees.ctc",
                                  "date": "salary_register.pay_month"},
            options={"aggregate": "sum"}))
    assert str(caught.value) == (
        "ctc is stored once per employee, but pay_month has many rows per employee, so this"
        " would count each ctc several times."
        " Pick a number from the same file as the group.")


@pytest.mark.parametrize("aggregate", ["average", "count", "median"])
def test_the_refusal_covers_every_aggregate_a_repeated_row_moves(session, aggregate):
    """An average over repeated rows is weighted by how many payslips each person has, and a
    count of employees across the link counts payslips. Both are wrong, not merely caveated."""
    with pytest.raises(ValueError, match="count each ctc several times"):
        analyses.run(session, AnalysisRequest(
            kind="trend", inputs={"measure": "employees.ctc",
                                  "date": "salary_register.pay_month"},
            options={"aggregate": aggregate}))


@pytest.mark.parametrize(("aggregate", "expected"), [("min", 900000.0), ("max", 3000000.0)])
def test_the_highest_and_lowest_still_run_across_the_link(session, aggregate, expected):
    """The smallest of a value listed twelve times is still that value, so a repeated row
    changes nothing here and refusing it would be a false alarm."""
    tile = analyses.run(session, AnalysisRequest(
        kind="trend", inputs={"measure": "employees.ctc",
                              "date": "salary_register.pay_month"},
        options={"aggregate": aggregate}))
    assert [row[1] for row in tile.table.rows] == [expected, expected]


def test_columns_from_files_that_are_not_linked_are_refused(session):
    """A cross join would multiply every attendance row by every employee row and answer a
    question nobody asked."""
    with pytest.raises(ValueError, match="not linked"):
        analyses.run(session, AnalysisRequest(
            kind="breakdown", inputs={"measure": "attendance_q2.days_present",
                                      "by": "employees.department"},
            options={"aggregate": "sum"}))


# ---- titles ----------------------------------------------------------------------------------


def test_every_title_is_title_cased_from_the_files_own_headers(session):
    """"Average ctc by department" reads as a machine's guess at a heading. The words are the
    file's own, the small ones stay small, and the acronyms an HR file is full of stay in
    capitals — str.title() would write "Ctc"."""
    assert analyses.run(session, REQUESTS["breakdown"]).title == "Average CTC by Department"
    assert analyses.run(session, REQUESTS["trend"]).title == "Total Days Present by Month"
    assert analyses.run(session, REQUESTS["top_n"]).title == "Top 5 Departments by Total CTC"
    assert analyses.run(session, REQUESTS["distribution"]).title == "How CTC Is Spread"
    assert analyses.run(session, REQUESTS["share"]).title == "Share of Total CTC by Department"
    assert analyses.run(session, REQUESTS["pivot"]).title == \
        "Number of Employees by Department and Location"
    assert analyses.run(session, REQUESTS["correlation"]).title == \
        "Days Present Against Days Absent"
    assert analyses.run(session, REQUESTS["change"]).title == "Change in Total Gross by Month"
    assert analyses.run(session, REQUESTS["outliers"]).title == "Unusual CTC Values"


def test_a_group_value_in_a_title_keeps_the_spelling_the_data_uses(session):
    """Only the headers are title-cased. A team really called "iOS" or "PreSales" must not be
    rewritten into somebody else's name by a heading."""
    session.conn.execute("UPDATE employees SET department = 'iOS' WHERE department = 'HR'")
    department = next(c for t in session.catalog.tables if t.name == "employees"
                      for c in t.columns if c.name == "department")
    department.values = ["Engineering", "Sales", "iOS"]
    tile = analyses.run(session, AnalysisRequest(
        kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "average", "group_a": "iOS", "group_b": "Sales"}))
    assert tile.title == "Average CTC: iOS vs Sales"


def test_the_chart_title_is_the_tiles_title(session):
    """One heading, not two: the card and the picture must not disagree."""
    tile = analyses.run(session, REQUESTS["breakdown"])
    assert tile.chart.title == tile.title


# ---- what a request may and may not say -----------------------------------------------------


def test_every_kind_produces_a_complete_tile(session):
    for key, request in REQUESTS.items():
        tile = analyses.run(session, request)
        assert tile.title and tile.statement.endswith(".") and tile.ask, key
        assert tile.sql.startswith(("SELECT", "WITH")), key
        assert tile.chart is not None and tile.table is not None, key


def test_the_same_request_twice_is_identical(session):
    """No model, no clock, no sampling: the second run must be the same bytes as the first."""
    for key, request in REQUESTS.items():
        assert analyses.run(session, request).model_dump() == \
               analyses.run(session, request).model_dump(), key


def test_no_analysis_can_put_a_personal_value_in_its_output(session):
    """The canary: planted PII must not reach the SQL, the rows or the sentence of any tile."""
    for key, request in REQUESTS.items():
        printed = analyses.run(session, request).model_dump_json()
        assert CANARY_NAME not in printed and CANARY_EMAIL not in printed, key


def test_every_choice_the_picker_offers_actually_runs(session):
    """An option in the list that raises is a dead button in the UI."""
    for kind in analyses.KINDS:
        base = REQUESTS[kind.key]
        for option in kind.options:
            for choice in option.choices:  # compare's groups have no fixed choices
                request = base.model_copy(update={"options": {**base.options, option.key: choice}})
                assert analyses.run(session, request).statement, (kind.key, option.key, choice)


def test_an_option_outside_its_list_is_refused(session):
    with pytest.raises(ValueError, match="is not a choice"):
        analyses.run(session, AnalysisRequest(
            kind="breakdown", inputs={"measure": "employees.ctc", "by": "employees.department"},
            options={"aggregate": "sum(ctc) FROM employees; --"}))


def test_an_option_the_kind_does_not_have_is_refused(session):
    """Silently ignoring it would answer a different question from the one that was asked."""
    with pytest.raises(ValueError, match="not something you can choose"):
        analyses.run(session, AnalysisRequest(
            kind="distribution", inputs={"measure": "employees.ctc"}, options={"top_n": "5"}))


def test_an_input_the_kind_does_not_have_is_refused(session):
    with pytest.raises(ValueError, match="not something Distribution asks for"):
        analyses.run(session, AnalysisRequest(
            kind="distribution", inputs={"measure": "employees.ctc",
                                         "by": "employees.department"}))


def test_a_missing_input_names_the_slot_to_fill(session):
    with pytest.raises(ValueError, match="Split by"):
        analyses.run(session, AnalysisRequest(kind="breakdown",
                                              inputs={"measure": "employees.ctc"}))


def test_an_unknown_kind_is_refused(session):
    with pytest.raises(ValueError, match="is not an analysis this app can run"):
        analyses.run(session, AnalysisRequest(kind="DROP TABLE employees", inputs={}))


@pytest.mark.parametrize("ref", [
    "employees.ctc; DROP TABLE employees",
    "employees.ctc, employees.name",
    '"employees"."ctc"',
    "employees.ctc OR 1=1",
    "(SELECT ctc FROM employees)",
    "employees",
    "",
])
def test_a_reference_that_is_not_a_catalog_column_never_reaches_sql(session, ref):
    with pytest.raises(ValueError):
        analyses.run(session, AnalysisRequest(
            kind="breakdown", inputs={"measure": ref, "by": "employees.department"}))


def test_a_column_of_the_wrong_kind_is_refused_with_the_slot_it_cannot_fill(session):
    with pytest.raises(ValueError, match="measure"):
        analyses.run(session, AnalysisRequest(
            kind="breakdown", inputs={"measure": "employees.department",
                                      "by": "employees.department"}))


def test_personal_data_is_refused_even_when_a_request_names_it_directly(session):
    """The picker never offers it; a request can still ask, and this is where that stops."""
    with pytest.raises(ValueError, match="personal data"):
        analyses.run(session, AnalysisRequest(
            kind="breakdown", inputs={"measure": "employees.ctc", "by": "employees.name"}))


def test_an_identifier_is_refused_as_a_group(session):
    with pytest.raises(ValueError, match="identifies a row"):
        analyses.run(session, AnalysisRequest(
            kind="breakdown", inputs={"measure": "employees.ctc", "by": "employees.emp_id"}))


# ---- the bundled sample files, through the real ingestion ------------------------------------


@pytest.fixture
def sample():
    """`demo_data` read in the way an upload is read. A picker that works against a hand-built
    catalog and not against a real one is not working."""
    if not (ROOT / "demo_data" / "employees.csv").exists():
        pytest.skip("demo_data is not generated")
    session = SessionStore().create()
    session.load_sample()
    yield session
    session.close()


def test_compare_runs_on_the_sample_data_from_the_picker_alone(sample):
    """Pick a column, take two of the values the picker published for it, run. That is the whole
    journey the tenth analysis could not complete, and it is done here with nothing typed."""
    department = next(choice for choice in analyses.catalog(sample).columns
                      if choice.ref == "employees.department")
    first, second = department.values[0], department.values[1]
    tile = analyses.run(sample, AnalysisRequest(
        kind="compare", inputs={"measure": "employees.ctc", "by": "employees.department"},
        options={"aggregate": "average", "group_a": first, "group_b": second}))
    assert tile.title == f"Average CTC: {first} vs {second}"
    assert {row[0] for row in tile.table.rows} == {first, second}
    assert first in tile.statement and second in tile.statement


def test_the_cross_file_fan_out_is_refused_on_the_sample_data(sample):
    """Average CTC by review cycle: one salary, two reviews, and the total was double. The
    sentence has to name both columns, because the analyst is looking at two pickers."""
    with pytest.raises(ValueError) as caught:
        analyses.run(sample, AnalysisRequest(
            kind="breakdown", inputs={"measure": "employees.ctc",
                                      "by": "performance_reviews.review_cycle"},
            options={"aggregate": "sum"}))
    assert str(caught.value) == (
        "ctc is stored once per employee, but Review Cycle has many rows per employee, so this"
        " would count each ctc several times."
        " Pick a number from the same file as the group.")


def test_the_same_two_files_the_other_way_round_still_run_on_the_sample_data(sample):
    """The rating lives on the many side, so counting it per department is not a fan-out. This
    is the question the refusal above must not take away."""
    tile = analyses.run(sample, AnalysisRequest(
        kind="breakdown", inputs={"measure": "performance_reviews.rating",
                                  "by": "employees.department"},
        options={"aggregate": "average"}))
    assert sorted(tile.tables_used) == ["employees", "performance_reviews"]
    assert tile.title == "Average Rating by Department" and tile.table.row_count == 6


def test_a_pay_month_column_reads_as_months_all_the_way_to_the_sentence(sample):
    """The polish that has to agree everywhere: the table, the chart's rows and the computed
    sentence are all built from the one decision `build_table` made about the column."""
    tile = analyses.run(sample, AnalysisRequest(
        kind="trend", inputs={"measure": "salary_register_2025_register.gross",
                              "date": "salary_register_2025_register.pay_month"},
        options={"aggregate": "sum", "grain": "month"}))
    assert tile.table.display[0][0] == "Jan 2025" and tile.table.display[-1][0] == "Dec 2025"
    assert tile.statement.endswith("(Dec 2025).") and "01 Jan 2025" not in tile.statement


# ---- data that is legal, empty or not a number ----------------------------------------------


@pytest.fixture
def odd(session):
    """The fixture session with three extra one-column tables: empty, holding a NaN, and
    holding the two ends of a double. A spreadsheet can produce all three, and each of them
    used to end a request somewhere other than in a sentence."""
    for name, rows in (("blank", []),
                       ("not_a_number", [(1.0,), (float("nan"),), (3.0,)]),
                       ("enormous", [(-1e308,), (1e308,)])):
        session.conn.execute(f"CREATE TABLE {name} (v DOUBLE)")
        if rows:
            session.conn.executemany(f"INSERT INTO {name} VALUES (?)", rows)
        session.catalog.tables.append(TableProfile(
            name=name, source_file=f"{name}.csv", row_count=len(rows),
            columns=[ColumnProfile(name="v", label="v", type="decimal",
                                   distinct_count=len(rows),
                                   null_fraction=0.0 if rows else 1.0)],
            health=DataHealth(rows=len(rows), columns=1)))
    return session


@pytest.mark.parametrize("table", ["blank", "not_a_number", "enormous"])
@pytest.mark.parametrize("kind", ["distribution", "outliers"])
def test_a_column_of_unrankable_numbers_gives_a_sentence_not_a_crash(odd, table, kind):
    """min/max of a column holding NaN come back empty, and 1e308 minus -1e308 overflows to
    infinity. Both used to escape as a TypeError or an OverflowError — not a ValueError, so
    not a refusal either: the analyst got a 500 where a sentence belongs."""
    tile = analyses.run(odd, AnalysisRequest(kind=kind, inputs={"measure": f"{table}.v"}))
    assert tile.statement.endswith(".") and "—" not in tile.statement


def test_a_change_over_a_table_with_no_dates_says_so(odd):
    """Zero periods is not one period. The one-period sentence names the period it found, and
    with no rows at all that name is an em dash."""
    odd.conn.execute("ALTER TABLE blank ADD COLUMN d DATE")
    profile = next(t for t in odd.catalog.tables if t.name == "blank")
    profile.columns.append(ColumnProfile(name="d", label="d", type="date", null_fraction=1.0))
    tile = analyses.run(odd, AnalysisRequest(
        kind="change", inputs={"measure": "blank.v", "date": "blank.d"},
        options={"aggregate": "sum", "grain": "month"}))
    assert tile.statement == "No row here has a date, so there are no months to compare."


def test_compare_on_a_column_that_is_empty_in_every_row_says_that(session):
    """"Too many different values" was the only refusal here, and for an empty column it names
    a cause that is the opposite of the truth."""
    session.conn.execute("CREATE TABLE blank (v DOUBLE, g VARCHAR)")
    session.catalog.tables.append(TableProfile(
        name="blank", source_file="blank.csv", row_count=0,
        columns=[ColumnProfile(name="v", label="v", type="decimal"),
                 ColumnProfile(name="g", label="g", type="text", values=[])],
        health=DataHealth(rows=0, columns=2)))
    with pytest.raises(ValueError, match="empty in every row"):
        analyses.run(session, AnalysisRequest(
            kind="compare", inputs={"measure": "blank.v", "by": "blank.g"},
            options={"group_a": "x", "group_b": "y"}))


def test_a_two_hundred_thousand_row_table_stays_inside_the_query_timeout(session):
    """Every guided analysis runs one or two DuckDB queries with no row limit beyond the
    chart's. At the size a real payroll export reaches, all of them have to finish."""
    session.conn.execute(
        "CREATE TABLE big AS SELECT i AS row_id, ('Dept ' || (i % 7)) AS department,"
        " make_date(2024, 1 + (i % 12), 1 + (i % 28)) AS order_date,"
        " (i % 1000) * 137.0 AS revenue, (i % 50) AS units FROM range(200000) t(i)")
    session.catalog.tables.append(TableProfile(
        name="big", source_file="big.csv", row_count=200_000, columns=[
            ColumnProfile(name="row_id", label="row_id", type="integer", is_identifier=True,
                          is_unique=True, distinct_count=200_000),
            ColumnProfile(name="department", label="department", type="text", distinct_count=7,
                          values=[f"Dept {i}" for i in range(7)]),
            ColumnProfile(name="order_date", label="order_date", type="date", distinct_count=336),
            ColumnProfile(name="revenue", label="revenue", type="currency", distinct_count=1000),
            ColumnProfile(name="units", label="units", type="integer", distinct_count=50),
        ], health=DataHealth(rows=200_000, columns=5)))

    started = time.perf_counter()
    for request in (
        AnalysisRequest(kind="breakdown", inputs={"measure": "big.revenue", "by": "big.department"}),
        AnalysisRequest(kind="distribution", inputs={"measure": "big.revenue"}),
        AnalysisRequest(kind="outliers", inputs={"measure": "big.revenue"}),
        AnalysisRequest(kind="correlation", inputs={"measure": "big.revenue",
                                                    "measure_b": "big.units"}),
        AnalysisRequest(kind="trend", inputs={"measure": "big.revenue", "date": "big.order_date",
                                              "by": "big.department"}),
        AnalysisRequest(kind="change", inputs={"measure": "big.revenue",
                                               "date": "big.order_date"}),
    ):
        tile = analyses.run(session, request)
        assert tile.statement and tile.table.row_count <= ROW_CAP
    assert time.perf_counter() - started < settings.query_timeout_s
