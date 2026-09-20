"""The computed sentence and insight lines: true when the rows say so, silent when they don't."""

import pytest
from app.contracts import ResultTable
from app.insights.facts import NOTHING, describe, insight_lines
from app.query.presentation import to_display


def table(columns: list[str], kinds: list[str], rows: list[list], truncated: bool = False) -> ResultTable:
    """A ResultTable whose display strings come from the real formatter, so a test that reads
    "₹12.00 L" is checking what the analyst sees."""
    return ResultTable(
        columns=columns, rows=rows,
        display=[[to_display(v, k) for v, k in zip(row, kinds, strict=True)] for row in rows],
        row_count=len(rows), truncated=truncated,
    )


PAY_KINDS = ["text", "currency"]


def pay(*pairs) -> ResultTable:
    return table(["department", "total_gross"], PAY_KINDS, [list(p) for p in pairs])


# ---- nothing to say ------------------------------------------------------------------------


def test_no_rows():
    empty = table(["department", "total"], PAY_KINDS, [])
    assert describe(empty, PAY_KINDS, "breakdown", "Pay by department") == (NOTHING, [])
    assert insight_lines(empty, PAY_KINDS) == []


def test_a_result_with_nothing_numeric_still_says_something_true():
    rows = table(["department"], ["text"], [["Sales"], ["HR"]])
    statement, lines = describe(rows, ["text"], "breakdown", "Departments")
    assert statement == "Departments: 2 rows."
    assert lines == []


# ---- breakdown -----------------------------------------------------------------------------


def test_breakdown_names_the_highest_and_the_lowest():
    statement, lines = describe(
        pay(("Engineering", 2040000), ("Sales", 1205000), ("HR", 369000)),
        PAY_KINDS, "breakdown", "Gross pay by department")
    assert statement == ("Engineering is highest at ₹20.40 L and HR lowest at ₹3.69 L,"
                         " across 3 groups.")
    assert "The highest is 5.5× the lowest." in lines


def test_breakdown_reports_concentration_only_when_there_are_more_than_three_groups():
    two = describe(pay(("A", 60), ("B", 40)), PAY_KINDS, "breakdown", "t")[1]
    assert not any("Top 3" in line for line in two), "top 3 of 2 groups is always 100%"
    three = describe(pay(("A", 5), ("B", 3), ("C", 2)), PAY_KINDS, "breakdown", "t")[1]
    assert not any("Top 3" in line for line in three)
    four = describe(pay(("A", 50), ("B", 20), ("C", 20), ("D", 10)), PAY_KINDS, "breakdown", "t")[1]
    assert "Top 3 make up 90.0% of the total." in four


def test_breakdown_names_every_tied_winner_rather_than_picking_one():
    statement, _ = describe(pay(("Engineering", 100), ("Sales", 100), ("HR", 40)),
                            PAY_KINDS, "breakdown", "t")
    assert statement.startswith("Engineering and Sales are highest at ")
    assert "HR lowest" in statement


def test_breakdown_with_many_tied_winners_counts_them():
    statement, _ = describe(pay(("A", 9), ("B", 9), ("C", 9), ("D", 9), ("E", 1)),
                            PAY_KINDS, "breakdown", "t")
    assert "A, B and 2 more are highest" in statement


def test_breakdown_when_every_group_is_equal():
    statement, lines = describe(pay(("A", 10), ("B", 10)), PAY_KINDS, "breakdown", "t")
    assert statement == "All 2 groups are level at ₹10."
    assert not any("×" in line for line in lines)


def test_breakdown_with_one_group():
    statement, lines = describe(pay(("Sales", 1500)), PAY_KINDS, "breakdown", "t")
    assert statement == "Sales is the only group, at ₹1,500."
    assert lines == []


def test_breakdown_skips_empty_cells_rather_than_reading_them_as_zero():
    statement, _ = describe(pay(("A", 100), ("B", None), ("C", 40)), PAY_KINDS, "breakdown", "t")
    assert "across 2 groups" in statement
    assert "B" not in statement


def test_breakdown_with_negative_values_makes_no_ratio_or_share_claim():
    statement, lines = describe(
        pay(("A", 100), ("B", 20), ("C", -50), ("D", -80)), PAY_KINDS, "breakdown", "t")
    assert "A is highest at ₹100 and D lowest at -₹80" in statement
    assert not any("×" in line or "Top 3" in line for line in lines)


def test_percentages_are_never_added_up():
    kinds = ["text", "percent"]
    rows = table(["department", "attrition_pct"], kinds,
                 [["A", 30.0], ["B", 25.0], ["C", 20.0], ["D", 5.0]])
    lines = describe(rows, kinds, "breakdown", "Attrition by department")[1]
    assert not any("Top 3" in line or "average across" in line for line in lines)
    assert "The highest is 6× the lowest." in lines  # to_display trims a bare .0


def test_a_truncated_result_makes_no_claim_about_the_whole():
    rows = table(["department", "total_gross"], PAY_KINDS,
                 [["A", 50], ["B", 20], ["C", 20], ["D", 10]], truncated=True)
    lines = describe(rows, PAY_KINDS, "breakdown", "t")[1]
    assert not any("Top 3" in line or "average across" in line for line in lines)


# ---- trend ---------------------------------------------------------------------------------

TREND_KINDS = ["date", "currency"]


def months(*pairs) -> ResultTable:
    return table(["month", "total_gross"], TREND_KINDS, [list(p) for p in pairs])


def test_trend_gives_first_last_and_peak():
    statement, lines = describe(
        months(("2025-01-01", 100), ("2025-06-01", 150), ("2025-12-01", 108)),
        TREND_KINDS, "trend", "Gross pay")
    assert statement == "Gross pay went from ₹100 (01 Jan 2025) to ₹108 (01 Dec 2025)."
    assert lines[0] == "Up 8.0% from 01 Jan 2025 to 01 Dec 2025."
    assert "Peak was ₹150 (01 Jun 2025)." in lines


def test_trend_reads_in_date_order_even_when_the_rows_are_not():
    statement, _ = describe(months(("2025-12-01", 108), ("2025-01-01", 100)),
                            TREND_KINDS, "trend", "Gross pay")
    assert statement.endswith("from ₹100 (01 Jan 2025) to ₹108 (01 Dec 2025).")


def test_trend_falling():
    lines = describe(months(("2025-01-01", 200), ("2025-02-01", 150)),
                     TREND_KINDS, "trend", "t")[1]
    assert lines[0] == "Down 25.0% from 01 Jan 2025 to 01 Feb 2025."


def test_trend_from_zero_reports_the_move_itself_not_a_percentage():
    """Dividing by a zero or negative starting point produces noise, not a fact."""
    lines = describe(months(("2025-01-01", 0), ("2025-02-01", 150)),
                     TREND_KINDS, "trend", "t")[1]
    assert lines[0] == "Up ₹150 from 01 Jan 2025 to 01 Feb 2025."


def test_trend_that_did_not_move():
    lines = describe(months(("2025-01-01", 50), ("2025-02-01", 50)), TREND_KINDS, "trend", "t")[1]
    assert lines == ["Unchanged from 01 Jan 2025 to 01 Feb 2025."]


def test_trend_with_one_period():
    statement, lines = describe(months(("2025-01-01", 50)), TREND_KINDS, "trend", "Gross pay")
    assert statement == "Gross pay has one period so far: ₹50 (01 Jan 2025)."
    assert lines == []


# ---- distribution, share, kpi, two-way -----------------------------------------------------


def test_distribution_reports_the_median_and_the_middle_half():
    kinds = ["currency", "currency", "currency"]
    rows = table(["median_ctc", "p25", "p75"], kinds, [[1500000, 1150000, 2100000]])
    statement, lines = describe(rows, kinds, "distribution", "CTC")
    assert statement == "CTC has a median of ₹15.00 L."
    assert lines[0] == "The middle half falls between ₹11.50 L and ₹21.00 L."


def test_a_histogram_reads_as_a_breakdown_over_its_buckets():
    kinds = ["text", "integer"]
    rows = table(["band", "people"], kinds, [["0-5 L", 2], ["5-10 L", 9], ["10-20 L", 4]])
    statement, _ = describe(rows, kinds, "distribution", "CTC bands")
    assert statement.startswith("5-10 L is highest at 9 and 0-5 L lowest at 2")


def test_share_uses_a_percent_column_as_it_stands():
    kinds = ["text", "percent"]
    rows = table(["gender", "share_pct"], kinds, [["F", 62.5], ["M", 37.5]])
    statement, _ = describe(rows, kinds, "share", "Gender split")
    assert statement == "F is the largest share at 62.5%."


def test_share_computes_the_percentage_when_the_result_has_none():
    statement, _ = describe(pay(("Engineering", 60), ("Sales", 40)), PAY_KINDS, "share", "t")
    assert statement == "Engineering is the largest share at 60.0% of the total (₹60 of ₹100)."


def test_share_falls_back_when_the_total_is_not_a_whole_positive_one():
    statement, _ = describe(pay(("A", 10), ("B", -20)), PAY_KINDS, "share", "t")
    assert "is highest at" in statement  # a share of a negative total means nothing


def test_kpi_states_the_value_with_its_label():
    kinds = ["integer"]
    statement, lines = describe(table(["headcount"], kinds, [[248]]), kinds, "kpi", "Headcount")
    assert statement == "Headcount is 248."
    assert lines == []


def test_kpi_headlines_the_last_measure_and_lists_the_others():
    kinds = ["integer", "currency"]
    rows = table(["people", "avg_ctc"], kinds, [[248, 1614000]])
    statement, lines = describe(rows, kinds, "kpi", "Average CTC")
    assert statement == "Average CTC is ₹16.14 L."
    assert lines == ["People: 248."]


def test_kpi_with_no_value_says_so_instead_of_showing_a_dash():
    kinds = ["currency"]
    statement, lines = describe(table(["avg_ctc"], kinds, [[None]]), kinds, "kpi", "Average CTC")
    assert statement == "Average CTC could not be calculated from this data."
    assert lines == []


def test_two_way_names_the_largest_cell():
    kinds = ["text", "text", "integer"]
    rows = table(["department", "location", "people"], kinds,
                 [["Sales", "Mumbai", 9], ["Sales", "Pune", 2], ["HR", "Mumbai", 1]])
    statement, lines = describe(rows, kinds, "comparison", "Headcount")
    assert statement == "Sales / Mumbai is the largest at 9, across 3 combinations."
    assert lines[0] == "HR / Mumbai is the smallest at 1."


# ---- robustness ----------------------------------------------------------------------------


def test_a_tile_whose_kind_does_not_match_its_shape_falls_back_instead_of_raising():
    statement, _ = describe(pay(("A", 10), ("B", 4)), PAY_KINDS, "trend", "t")
    assert "is highest at" in statement


@pytest.mark.parametrize("kind", ["kpi", "breakdown", "trend", "distribution", "share",
                                  "comparison", "relationship", "quality", "metric"])
def test_every_kind_survives_a_result_of_all_empty_cells(kind):
    kinds = ["text", "currency"]
    rows = table(["department", "total"], kinds, [["A", None], [None, None]])
    statement, lines = describe(rows, kinds, kind, "t")
    assert statement and len(lines) <= 3


def test_at_most_three_lines_and_no_repeats():
    wide = pay(("A", 90), ("B", 50), ("C", 30), ("D", 20), ("E", 10))
    assert len(describe(wide, PAY_KINDS, "breakdown", "t")[1]) <= 3


def test_every_number_in_a_line_is_formatted_the_way_answers_format_numbers():
    """₹ lakh/crore and Indian digit grouping come from to_display, not from an f-string."""
    statement, lines = describe(pay(("A", 12345678), ("B", 1000)), PAY_KINDS, "breakdown", "t")
    assert to_display(12345678, "currency") in statement  # "₹1.23 Cr"
    assert "12345678" not in statement + " ".join(lines)


# ---- insight_lines for a model-written answer ----------------------------------------------


def test_insight_lines_reads_a_breakdown_with_no_kind_given():
    lines = insight_lines(pay(("A", 50), ("B", 20), ("C", 20), ("D", 10)), PAY_KINDS)
    assert "Top 3 make up 90.0% of the total." in lines


def test_insight_lines_reads_a_trend_with_no_kind_given():
    lines = insight_lines(months(("2025-01-01", 100), ("2025-12-01", 108)), TREND_KINDS)
    assert lines[0] == "Up 8.0% from 01 Jan 2025 to 01 Dec 2025."


def test_insight_lines_on_a_single_row_answer():
    kinds = ["integer", "currency"]
    assert insight_lines(table(["people", "avg_ctc"], kinds, [[248, 1614000]]), kinds) == ["People: 248."]
