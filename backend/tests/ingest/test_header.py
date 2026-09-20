"""Header-row and footer-total detection: the two structural traps in HR exports."""

from __future__ import annotations

import time

from app.ingest.header import (
    count_inner_totals,
    detect_header_row,
    drop_empty_columns,
    drop_footer_totals,
)

HEADER = ["Emp Code", "Pay Month", "Gross"]


def test_title_rows_above_the_header_are_skipped():
    grid = [
        ["Salary Register for the month of Jan 2025", None, None],
        [None, None, None],
        ["Generated on 05/02/2025", None, None],
        HEADER,
        ["000457", "01/01/2025", "₹1,20,000"],
        ["000458", "01/01/2025", "₹95,000"],
    ]
    assert detect_header_row(grid) == 3


def test_plain_csv_header_is_row_zero():
    grid = [HEADER, ["000457", "01/01/2025", "120000"], ["000458", "01/01/2025", "95000"]]
    assert detect_header_row(grid) == 0


def test_all_text_table_prefers_the_earliest_row():
    grid = [["Name", "City"], ["Asha", "Pune"], ["Vikram", "Mumbai"]]
    assert detect_header_row(grid) == 0


def test_header_with_a_blank_cell_still_beats_all_text_data():
    """Otherwise the first data row becomes the column names and a person goes missing."""
    grid = [
        ["Name", "Dept", None, "City"],
        ["Asha", "HR", "x", "Pune"],
        ["Vik", "IT", "y", "Mumbai"],
    ]
    assert detect_header_row(grid) == 0


def test_title_above_a_header_made_of_years():
    grid = [
        ["Headcount by year", None, None, None],
        ["Dept", "2023", "2024", "2025"],
        ["Engineering", "120", "130", "140"],
    ]
    assert detect_header_row(grid) == 1


def test_key_value_block_above_the_header():
    grid = [
        ["Company:", "Acme Ltd", None, None, None],
        ["Period:", "Jan 2025", None, None, None],
        ["Emp Code", "Name", "Dept", "City", "CTC"],
        ["001", "Asha", "HR", "Pune", "1200000"],
    ]
    assert detect_header_row(grid) == 2


def test_very_sparse_grid_falls_back_to_the_first_row_with_content():
    grid = [[None, None, None, None], ["note", None, None, None], ["x", None, None, None]]
    assert detect_header_row(grid) == 1


def test_header_is_only_searched_in_the_first_15_rows():
    grid = [["note", None, None]] * 20 + [HEADER, ["1", "2", "3"]]
    assert detect_header_row(grid) < 15


def test_grand_total_footer_is_dropped():
    rows = [["000457", "Jan", "1,20,000"], ["Grand Total", None, "12,34,567"]]
    kept, totals, notes = drop_footer_totals(rows)
    assert kept == rows[:1]
    assert (totals, notes) == (1, 0)


def test_total_variants_match_case_insensitively():
    for first in ("Total", "TOTAL:", "  grand   total ", "total :"):
        kept, totals, _ = drop_footer_totals([["a", "1"], [first, "9"]])
        assert totals == 1 and kept == [["a", "1"]], first


def test_total_label_may_sit_in_a_later_cell():
    kept, totals, _ = drop_footer_totals([["a", "x", "1"], [None, "Total", "9"]])
    assert totals == 1 and len(kept) == 1


def test_data_row_that_merely_contains_total_is_kept():
    rows = [["Totally Fine Corp", "Pune", "5"], ["Total Solutions Ltd", "Pune", "7"]]
    assert drop_footer_totals(rows) == (rows, 0, 0)


def test_total_row_in_the_middle_is_not_a_footer():
    rows = [["Total", "1"], ["a", "2"]]
    assert drop_footer_totals(rows) == (rows, 0, 0)


def test_note_rows_after_the_total_go_with_it():
    """A sign-off line under the total must not shield the total from being dropped,
    otherwise every SUM over the column double-counts."""
    rows = [
        ["000457", "Jan", "100"],
        ["Grand Total", None, "100"],
        ["Prepared by payroll team", None, None],
    ]
    kept, totals, notes = drop_footer_totals(rows)
    assert kept == rows[:1]
    assert (totals, notes) == (1, 1)


def test_last_subtotal_goes_with_the_grand_total():
    """A register grouped by department ends "Sub Total", "Grand Total". The subtotal used
    to stop the scan and stay in the data."""
    rows = [["IT", "E1", "100"], ["Sub-Total", None, "100"], ["Grand Total", None, "100"]]
    kept, totals, _ = drop_footer_totals(rows)
    assert (kept, totals) == (rows[:1], 2)


def test_subtotals_inside_the_table_are_counted_not_dropped():
    rows = [
        ["HR", "E1", "100"],
        ["Total", None, "100"],
        ["IT", "E2", "200"],
        ["Subtotal:", None, "200"],
        ["Total Solutions Ltd", "E3", "5"],
    ]
    assert drop_footer_totals(rows) == (rows, 0, 0)
    assert count_inner_totals(rows) == 2


def test_a_total_label_padded_with_spaces_cannot_stall_the_scan():
    """The label was once matched on the raw cell, where `\\s*:?\\s*$` backtracks
    quadratically: 30,000 spaces took 3 seconds, and a cell can hold 130,000."""
    rows = [["a", "1", "2"], ["total" + " " * 30_000 + "x", "1", "2"]]
    started = time.perf_counter()
    assert drop_footer_totals(rows) == (rows, 0, 0)
    assert time.perf_counter() - started < 1


def test_a_header_cell_padded_with_spaces_cannot_stall_header_detection():
    grid = [["Emp ID", "-" + " " * 1_000 + "x"], ["E1", "5"], ["E2", "6"]]
    started = time.perf_counter()
    assert detect_header_row(grid) == 0
    assert time.perf_counter() - started < 1


def test_trailing_note_without_a_total_is_kept():
    rows = [["000457", "Jan", "100"], ["some remark", None, None]]
    assert drop_footer_totals(rows) == (rows, 0, 0)


def test_columns_that_are_blank_everywhere_are_dropped():
    grid = [[None, "a", "", "b"], [None, "1", "  ", "2"]]
    assert drop_empty_columns(grid) == [["a", "b"], ["1", "2"]]
