"""The comparator decides the accuracy number on the Trust Report, so every rule is pinned here.

Two ways to be wrong: a false pass inflates a number a CHRO may quote; a false fail sends the
tuning loop chasing a bug that is not there. Each test below guards one of the two.
"""

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from app.contracts import ResultTable

from eval.compare import matches


def table(columns: list[str], rows: list[list]) -> ResultTable:
    return ResultTable(columns=columns, rows=rows, row_count=len(rows),
                       display=[[str(v) for v in row] for row in rows])


# ---------------------------------------------------------------- scalars


def test_a_scalar_matches_any_cell_of_a_single_row():
    assert matches(1200000, table(["department", "total_gross"], [["Engineering", 1200000.0]]))
    assert matches("engineering", table(["department", "total_gross"], [["Engineering ", 1200000.0]]))


def test_a_scalar_never_matches_a_multi_row_or_empty_result():
    assert not matches(5, table(["n"], [[5], [5]]))
    assert not matches(5, table(["n"], []))


def test_a_wrong_scalar_fails():
    assert not matches(1200000, table(["total_gross"], [[1199000.0]]))


def test_float_noise_is_tolerated():
    assert matches(0.3, table(["x"], [[0.1 + 0.2]]))


@pytest.mark.parametrize("expected, got, same", [
    (28.5714, 28.57, True),     # SQL rounded to 2 decimals
    (28.5714, 28.6, True),      # SQL rounded to 1 decimal, as the prompt rules ask for percentages
    (28.6, 28.5714, True),      # the truth function rounded, the SQL did not
    (1234567.89, 1234568, True),  # whole-rupee rounding is inside the relative tolerance
    (28.5714, 29, False),       # whole-number rounding of a small value loses the answer
    (28.57, 28.61, False),      # neither side is a 1-decimal rounding of the other
    (4.4, 4, False),
    (28.6, 0.286, False),       # a fraction is not a percentage
])
def test_rounding_rules(expected, got, same):
    assert matches(expected, table(["v"], [[got]])) is same


@pytest.mark.parametrize("expected, got", [
    (6.25, 6.3),    # DuckDB rounds a tie away from zero
    (6.25, 6.2),    # Python rounds it to even
    (8.25, 8.3),
    (0.125, 0.13),
    (0.125, 0.12),
    (2.675, 2.68),
])
def test_a_tie_may_be_rounded_either_way(expected, got):
    assert matches(expected, table(["v"], [[got]]))
    assert matches(got, table(["v"], [[expected]]))


def test_counts_must_be_exact():
    assert matches(120, table(["n"], [[120]]))
    assert not matches(120, table(["n"], [[121]]))


def test_whole_numbers_must_be_equal_however_large_they_are():
    # A relative tolerance alone would forgive all three of these wrong answers.
    assert not matches(1_000_000, table(["headcount"], [[1_000_001]]))
    assert not matches(546_657_000, table(["total_gross"], [[546_657_500.0]]))
    assert not matches([("HR", 42_754_000)], table(["d", "g"], [["HR", 42_754_040]]))
    assert matches(546_657_000, table(["total_gross"], [[546_657_000.0]]))
    assert matches(546_657_000.4, table(["total_gross"], [[546_657_000]]))  # paise rounded away by the SQL


def test_a_right_looking_number_in_the_wrong_shape_fails():
    assert not matches("Support", table(["d", "avg"], [["Support", 15.0], ["Sales", 11.5]]))  # a ranking is not "which one"
    assert not matches(5, table(["emp"], [["a"], ["b"], ["c"], ["d"], ["e"]]))  # five rows are not the number 5
    assert not matches([("A", 1), ("B", 2)], table(["k", "v"], [["A", 1], ["A", 1], ["B", 2]]))  # a fanned-out duplicate row


def test_numeric_types_compare_by_value():
    assert matches(Decimal("1500.50"), table(["v"], [[1500.5]]))
    assert matches(np.int64(42), table(["v"], [[42.0]]))
    assert matches(np.float64(2.5), table(["v"], [[2.5]]))


def test_true_is_not_the_number_one():
    assert matches(True, table(["v"], [[True]]))
    assert not matches(1, table(["v"], [[True]]))
    assert not matches(True, table(["v"], [[1]]))


# ---------------------------------------------------------------- row lists


EXPECTED_BY_DEPT = [("Engineering", 1200000.0), ("Sales", 633334.0), ("HR", 270000.0)]


def test_rows_compare_as_a_multiset_ignoring_order_and_column_names():
    got = table(["dept", "gross_total"], [["HR", 270000.0], ["Engineering", 1200000.0], ["Sales", 633334.0]])
    assert matches(EXPECTED_BY_DEPT, got)


def test_extra_predicted_columns_are_allowed_and_columns_are_mapped_by_value():
    got = table(["headcount", "total", "department"],
                [[3, 1200000.0, "Engineering"], [3, 633334.0, "Sales"], [2, 270000.0, "HR"]])
    assert matches(EXPECTED_BY_DEPT, got)


def test_a_missing_expected_column_fails():
    assert not matches(EXPECTED_BY_DEPT, table(["department"], [["Engineering"], ["Sales"], ["HR"]]))


def test_one_differing_value_fails():
    got = table(["d", "g"], [["Engineering", 1200000.0], ["Sales", 633334.0], ["HR", 270001.0]])
    assert not matches(EXPECTED_BY_DEPT, got)


def test_values_must_sit_in_the_same_row_not_just_the_same_column():
    got = table(["d", "g"], [["Engineering", 633334.0], ["Sales", 1200000.0], ["HR", 270000.0]])
    assert not matches(EXPECTED_BY_DEPT, got)


def test_different_row_counts_fail():
    assert not matches(EXPECTED_BY_DEPT, table(["d", "g"], [["Engineering", 1200000.0]]))
    assert not matches(EXPECTED_BY_DEPT[:2], table(["d", "g"], [list(r) for r in EXPECTED_BY_DEPT]))


def test_duplicates_count():
    assert matches([("a", 1), ("a", 1)], table(["k", "v"], [["a", 1], ["a", 1]]))
    assert not matches([("a", 1), ("a", 1)], table(["k", "v"], [["a", 1], ["b", 1]]))


def test_two_numeric_columns_are_told_apart_by_their_values():
    expected = [("F", 3, 37.5), ("M", 5, 62.5)]
    got = table(["gender", "share_pct", "n"], [["M", 62.5, 5], ["F", 37.5, 3]])
    assert matches(expected, got)


def test_order_matters_only_when_asked():
    ranked = [("Engineering", 1200000.0), ("Sales", 633334.0)]
    reversed_rows = table(["d", "g"], [["Sales", 633334.0], ["Engineering", 1200000.0]])
    assert matches(ranked, reversed_rows)
    assert not matches(ranked, reversed_rows, ordered=True)
    assert matches(ranked, table(["d", "g"], [["Engineering", 1200000.0], ["Sales", 633334.0]]), ordered=True)


def test_empty_expected_matches_only_an_empty_result():
    assert matches([], table(["d"], []))
    assert not matches([], table(["d"], [["HR"]]))


def test_rows_with_rounded_percentages_match():
    expected = [("Engineering", 100 * 2 / 7), ("Sales", 100 * 1 / 3)]
    assert matches(expected, table(["d", "attrition_pct"], [["Sales", 33.3], ["Engineering", 28.6]]))


# ---------------------------------------------------------------- dates, text, nulls


def test_dates_compare_by_value_whatever_their_type():
    got = table(["month", "n"], [["2025-01-01", 8], ["2025-02-01", 7]])
    assert matches([(date(2025, 1, 1), 8), (date(2025, 2, 1), 7)], got)
    assert matches([(pd.Timestamp("2025-01-01"), 8), (datetime(2025, 2, 1), 7)], got)  # noqa: DTZ001 - pandas truth values are naive
    assert matches([("2025-01-01", 8), ("2025-02-01", 7)], table(["m", "n"], [["2025-01-01T00:00:00", 8], ["2025-02-01 00:00:00", 7]]))
    assert not matches([(date(2025, 1, 2), 8), (date(2025, 2, 1), 7)], got)


def test_a_date_matches_midnight_but_not_another_time_of_day():
    assert matches(date(2025, 1, 1), table(["d"], [["2025-01-01T00:00:00"]]))
    assert not matches(date(2025, 1, 1), table(["d"], [["2025-01-01T12:00:00"]]))


def test_a_month_label_means_the_first_of_that_month():
    assert matches([(date(2025, 4, 1), 12)], table(["month", "exits"], [["2025-04", 12]]))


def test_strings_are_trimmed_and_case_insensitive():
    assert matches([("Bengaluru", 3)], table(["location", "n"], [[" bengaluru ", 3]]))
    assert not matches([("Bengaluru", 3)], table(["location", "n"], [["Bangalore", 3]]))


def test_an_id_read_as_a_number_by_pandas_still_matches_the_text_id():
    # pandas reads 000123 from the clean CSV as 123 unless told otherwise; DuckDB keeps the text.
    assert matches([(123, 5)], table(["emp_id", "n"], [["000123", 5]]))
    assert matches([(2025, 5)], table(["year", "n"], [["2025", 5]]))
    assert not matches([(124, 5)], table(["emp_id", "n"], [["000123", 5]]))


def test_missing_values_match_each_other_and_nothing_else():
    assert matches([("HR", None), ("Sales", 2.0)], table(["d", "v"], [["Sales", 2.0], ["HR", None]]))
    assert matches([(float("nan"), 4), (pd.NaT, 5)], table(["k", "n"], [[None, 4], [None, 5]]))
    assert not matches([("HR", 0)], table(["d", "v"], [["HR", None]]))


# ---------------------------------------------------------------- shapes truth.py may return


def test_a_bare_tuple_is_one_row():
    assert matches(("Engineering", 1200000.0), table(["d", "g"], [["Engineering", 1200000.0]]))


def test_a_list_of_scalars_is_one_column():
    assert matches(["HR", "Sales"], table(["d", "n"], [["Sales", 1], ["HR", 2]]))


def test_dicts_series_and_frames_are_accepted():
    got = table(["d", "n"], [["Sales", 3], ["HR", 2]])
    assert matches({"HR": 2, "Sales": 3}, got)
    assert matches(pd.Series({"HR": 2, "Sales": 3}), got)
    assert matches(pd.DataFrame({"d": ["HR", "Sales"], "n": [2, 3]}), got)
    assert matches({("HR", "F"): 1}, table(["d", "g", "n"], [["HR", "F", 1]]))


def test_a_grouped_frame_keeps_the_labels_held_in_its_index():
    grouped = pd.DataFrame({"d": ["HR", "Sales"], "n": [2, 3]}).set_index("d")
    assert matches(grouped, table(["d", "n"], [["Sales", 3], ["HR", 2]]))
    assert not matches(grouped, table(["d", "n"], [["Finance", 2], ["Support", 3]]))  # right numbers, wrong labels


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NaT])
def test_a_missing_expected_value_is_a_golden_set_bug_and_says_so(missing):
    # Graded as a value, it would pass on any one-row result that happens to hold a blank cell.
    with pytest.raises(ValueError, match="expected value is missing"):
        matches(missing, table(["d", "v"], [["HR", None]]))


def test_ragged_expected_rows_are_a_golden_set_bug_and_say_so():
    with pytest.raises(ValueError, match="same number of values"):
        matches([("HR", 1), ("Sales",)], table(["d", "n"], [["HR", 1], ["Sales", 2]]))


def test_a_wide_select_star_is_still_matched_quickly():
    columns = [f"c{i}" for i in range(300)]
    rows = [[f"r{r}-{c}" for c in range(300)] for r in range(50)]
    expected = [(row[7], row[211]) for row in rows]
    assert matches(expected, table(columns, rows))
