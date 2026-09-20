"""Verification catches answers that run fine and are still wrong."""

from datetime import date, datetime
from decimal import Decimal

from app.contracts import ColumnProfile
from app.query.executor import ExecResult
from app.query.guard import validate_sql
from app.query.verify import fan_out_risks, null_caveats, results_equivalent
from tests.fixtures import make_session

CATALOG = make_session().catalog


def _risks(sql: str) -> list[str]:
    return fan_out_risks(validate_sql(sql, CATALOG), CATALOG)


def _result(*rows: tuple, columns: list[str] | None = None) -> ExecResult:
    names = columns or [f"c{i}" for i in range(len(rows[0]) if rows else 1)]
    return ExecResult(columns=names, duck_types=["ANY"] * len(names), rows=list(rows))


# ---- fan-out ------------------------------------------------------------------------------


def test_summing_the_one_side_of_a_one_to_many_join_is_flagged():
    risks = _risks("SELECT sum(e.ctc) FROM employees e JOIN salary_register s ON e.emp_id = s.emp_code")
    assert len(risks) == 1
    assert "ctc" in risks[0] and "multipl" in risks[0]
    assert "employees" in risks[0] and "salary_register" in risks[0]


def test_summing_the_many_side_is_safe():
    assert _risks("SELECT e.department, sum(s.gross) FROM employees e JOIN salary_register s"
                  " ON e.emp_id = s.emp_code GROUP BY 1") == []


def test_join_where_neither_key_is_unique_is_flagged_as_many_to_many():
    risks = _risks("SELECT sum(s.gross) FROM attendance_q1 a JOIN salary_register s ON a.emp_id = s.emp_code")
    assert len(risks) == 1
    assert "many-to-many" in risks[0]
    assert "attendance_q1" in risks[0] and "salary_register" in risks[0]


def test_pre_aggregating_the_many_side_in_a_cte_clears_the_risk():
    assert _risks("WITH pay AS (SELECT emp_code, sum(gross) AS g FROM salary_register GROUP BY 1)"
                  " SELECT sum(e.ctc), sum(pay.g) FROM employees e JOIN pay ON pay.emp_code = e.emp_id") == []


def test_distinct_counts_min_and_max_cannot_be_inflated_by_repeated_rows():
    assert _risks("SELECT count(DISTINCT e.emp_id), max(e.ctc) FROM employees e"
                  " JOIN salary_register s ON e.emp_id = s.emp_code") == []


def test_composite_key_join_is_not_called_many_to_many():
    """Neither column is unique alone, but (employee, month) can be; we cannot tell, so we stay quiet."""
    assert _risks("SELECT sum(s.gross) FROM attendance_q1 a JOIN salary_register s"
                  " ON a.emp_id = s.emp_code AND a.month = s.pay_month") == []


def test_self_join_is_not_flagged():
    """Span of control joins employees to itself; table names alone cannot say which side is counted."""
    catalog = CATALOG.model_copy(deep=True)
    catalog.tables[0].columns.append(ColumnProfile(name="manager_id", label="Manager ID", type="text"))
    query = validate_sql("SELECT m.emp_id, count(e.emp_id) AS reports FROM employees e"
                         " JOIN employees m ON e.manager_id = m.emp_id GROUP BY 1", catalog)
    assert len(query.joins) == 1
    assert fan_out_risks(query, catalog) == []


# ---- NULL and duplicate caveats -----------------------------------------------------------


def test_null_share_of_a_used_column_becomes_a_sentence_with_the_percentage():
    caveats = null_caveats(validate_sql("SELECT avg(ctc) FROM employees", CATALOG), CATALOG)
    assert len(caveats) == 1
    assert "12.5%" in caveats[0] and "ctc" in caveats[0] and "employees" in caveats[0]


def test_columns_below_the_threshold_and_empty_exit_dates_are_not_caveats():
    query = validate_sql("SELECT department, count(*) FROM employees WHERE exit_date IS NULL GROUP BY 1", CATALOG)
    assert null_caveats(query, CATALOG) == []  # exit_date is 75% empty, which means "still employed"
    assert null_caveats(validate_sql("SELECT avg(ctc) FROM employees", CATALOG), CATALOG, threshold=0.2) == []


def test_duplicates_are_reported_whether_removed_or_kept_including_behind_a_union_view():
    catalog = CATALOG.model_copy(deep=True)
    tables = {t.name: t for t in catalog.tables}
    tables["salary_register"].health.duplicate_rows = 6
    tables["salary_register"].health.duplicates_removed = True
    tables["attendance_q1"].health.duplicate_rows = 1

    removed = null_caveats(validate_sql("SELECT sum(gross) FROM salary_register", catalog), catalog)
    kept = null_caveats(validate_sql("SELECT sum(days_present) FROM attendance_all", catalog), catalog)
    assert removed == ["6 exact duplicate rows were removed from salary_register before answering."]
    assert kept == ["attendance_q1 has 1 exact duplicate row that was kept, so totals may count it twice."]


# ---- cross-check equivalence --------------------------------------------------------------


def test_same_rows_in_a_different_order_with_different_column_names_are_equivalent():
    a = _result(("Sales", 3), ("HR", 2), columns=["department", "people"])
    b = _result(("HR", 2), ("Sales", 3), columns=["dept", "headcount"])
    assert results_equivalent(a, b)


def test_column_order_does_not_matter_but_row_pairing_does():
    assert results_equivalent(_result(("Sales", 3), ("HR", 2)), _result((2, "HR"), (3, "Sales")))
    assert not results_equivalent(_result(("Sales", 3), ("HR", 2)), _result(("Sales", 2), ("HR", 3)))


def test_float_noise_is_ignored_and_a_real_difference_is_not():
    assert results_equivalent(_result((0.1 + 0.2,)), _result((0.3,)))
    assert not results_equivalent(_result((412345678.0,)), _result((412355678.0,)))  # Rs 10,000 apart
    assert not results_equivalent(_result(("Sales", 3), ("HR", 2)), _result(("Sales", 3), ("HR", 4)))


def test_an_extra_column_on_one_side_is_allowed_when_the_rest_matches():
    a = _result((1500000.0,), (900000.0,))
    b = _result(("Sales", 1500000.0), ("HR", 900000.0))
    assert results_equivalent(a, b) and results_equivalent(b, a)
    assert not results_equivalent(a, _result(("Sales", 1500000.0), ("HR", 1.0)))


def test_different_row_counts_are_never_equivalent():
    assert not results_equivalent(_result((1,), (2,)), _result((1,)))
    assert results_equivalent(_result(), _result())


def test_decimal_int_and_float_compare_numerically_and_dates_by_value():
    assert results_equivalent(_result((Decimal("2.50"), 3)), _result((2.5, 3.0)))
    assert results_equivalent(_result((date(2025, 4, 1),)), _result((datetime(2025, 4, 1, 0, 0),)))
    assert not results_equivalent(_result((date(2025, 4, 1),)), _result((date(2025, 4, 2),)))


def test_nulls_and_text_must_match_exactly():
    assert results_equivalent(_result(("HR", None)), _result(("HR", None)))
    assert not results_equivalent(_result(("HR", None)), _result(("HR", 0)))
    assert not results_equivalent(_result(("HR",)), _result(("Sales",)))
