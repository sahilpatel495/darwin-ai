"""Two verification rules that decide whether a correct answer keeps its badge.

Both come from the final evaluation run: a rounded cross-check was called a disagreement, and
a question naming a period was answered from a query that never looked at a date.
"""

from decimal import Decimal

from app.query.executor import ExecResult
from app.query.guard import validate_sql
from app.query.verify import period_risks, results_equivalent
from tests.fixtures import make_session

CATALOG = make_session().catalog
NAN = float("nan")


def _result(*rows: tuple) -> ExecResult:
    names = [f"c{i}" for i in range(len(rows[0]) if rows else 1)]
    return ExecResult(columns=names, duck_types=["ANY"] * len(names), rows=list(rows))


def _agree(x, y) -> bool:
    """Equivalence must not depend on which model is called the primary."""
    forwards, backwards = results_equivalent(_result((x,)), _result((y,))), \
        results_equivalent(_result((y,)), _result((x,)))
    assert forwards == backwards, f"{x!r} and {y!r} compared differently in the two directions"
    return forwards


# ---- rounding-tolerant cross-check ---------------------------------------------------------


def test_the_real_false_alarm_rounded_average_against_the_raw_one():
    """Eval 2026-09-20: ROUND(AVG(rating), 2) = 3.38 vs AVG(rating) = 3.3812 was a
    DISAGREEMENT, and a correct answer was badged Low."""
    assert _agree(3.38, 3.3812)


def test_one_decimal_rounds_the_other():
    assert _agree(12.5, 12.46)


def test_whole_numbers_stay_strict():
    """430 employees and 430.4 are different answers, not a rounding choice."""
    assert not _agree(430, 430.4)
    assert not _agree(430.0, 430.4)
    assert not _agree(412345678.0, 412355678.0)  # Rs 10,000 apart, the existing guard


def test_percent_against_fraction_is_still_a_disagreement():
    assert not _agree(28.6, 0.286)
    assert not _agree(0.286, 28.6)


def test_a_real_difference_at_the_same_scale_is_still_a_disagreement():
    assert not _agree(3.38, 3.42)
    assert not _agree(12.5, 12.44)  # rounds to 12.4, not 12.5


def test_negatives_round_like_positives():
    assert _agree(-3.38, -3.3812)
    assert not _agree(-430, -430.4)
    assert not _agree(3.38, -3.38)


def test_decimals_ints_and_floats_mix():
    assert _agree(Decimal("3.38"), 3.3812)
    assert _agree(Decimal("12.50"), 12.46)  # trailing zero does not make it two decimals
    assert not _agree(3, 3.4)
    assert _agree(Decimal("3.3812"), Decimal("3.38"))


def test_four_decimals_is_the_ceiling():
    assert _agree(1.2346, 1.23456)
    assert not _agree(1.23456, 1.234564)  # five decimals: noise, not a rounding choice
    assert _agree(1.234561, 1.23456)  # still inside the 1e-6 tolerance


def test_the_widened_rule_does_not_narrow_the_old_one():
    """Everything the plain tolerance already accepted still passes: float noise on a crore-
    scale sum (both sides whole numbers, so the rounding clause is switched off), a trailing
    zero written by DuckDB's DECIMAL, and the -0.0 a SUM of nothing can return."""
    assert _agree(123456789.0, 123456789.00000001)
    assert _agree(Decimal("3.380"), 3.38)
    assert _agree(-0.0, 0)


def test_nulls_and_nans_are_untouched():
    assert not _agree(None, 3.38)
    assert not _agree(NAN, 3.38)
    assert _agree(None, None)
    assert _agree(NAN, None)  # both are "no value" to the comparer


def test_rounding_tolerance_applies_per_cell_of_a_grouped_result():
    rounded = _result(("Sales", 3.38), ("HR", 4.1))
    raw = _result(("Sales", 3.3812), ("HR", 4.0951))
    assert results_equivalent(rounded, raw)
    assert not results_equivalent(rounded, _result(("Sales", 3.3812), ("HR", 4.51)))


# ---- a named period the SQL ignores --------------------------------------------------------


def _period(question: str, sql: str) -> list[str]:
    return period_risks(question, validate_sql(sql, CATALOG), CATALOG)


def test_a_year_the_query_never_filters_on():
    risks = _period("How many people joined in 2025?", "SELECT count(*) FROM employees")
    assert len(risks) == 1
    assert "2025" in risks[0] and "employees" in risks[0]
    assert "Nov 2017 to Jun 2025" in risks[0]  # joining dates start in 2017


def test_silent_when_the_query_uses_a_date_of_that_table():
    assert _period("How many people joined in 2025?",
                   "SELECT count(*) FROM employees WHERE date_of_joining >= DATE '2025-01-01'") == []


def test_silent_when_the_table_holds_nothing_outside_the_period():
    """The sample register is 2025 only, so there is nothing to filter out and nothing to say.
    The evaluation cache depends on this staying quiet."""
    assert _period("What did we pay in total in 2025?",
                   "SELECT sum(gross) FROM salary_register") == []


def test_silent_without_a_named_period():
    assert _period("What did we pay in total?", "SELECT sum(gross) FROM salary_register") == []


def test_relative_periods_are_out_of_scope():
    assert _period("What did we pay last quarter?", "SELECT sum(gross) FROM salary_register") == []
    assert _period("What did we pay this year?", "SELECT sum(gross) FROM salary_register") == []


def test_two_named_periods_are_left_alone():
    assert _period("Compare total pay in 2024 and 2025",
                   "SELECT sum(gross) FROM salary_register") == []


def test_fiscal_years_run_april_to_march():
    """FY25 is Apr 2024 - Mar 2025 and contains the whole register; FY26 starts after it."""
    assert _period("What did we pay in FY25?", "SELECT sum(gross) FROM salary_register") == []
    risks = _period("What did we pay in FY26?", "SELECT sum(gross) FROM salary_register")
    assert len(risks) == 1 and "FY26" in risks[0] and "Jan 2025 to Feb 2025" in risks[0]


def test_the_written_out_fiscal_year_reads_the_same():
    assert _period("What did we pay in FY 2024-25?",
                   "SELECT sum(gross) FROM salary_register") == []
    assert len(_period("What did we pay in FY 2025-26?",
                       "SELECT sum(gross) FROM salary_register")) == 1


def test_a_month_with_a_year():
    risks = _period("What did we pay in January 2025?", "SELECT sum(gross) FROM salary_register")
    assert len(risks) == 1 and "January 2025" in risks[0]  # February is in the register too
    assert _period("How many days were worked in Jan 2025?",
                   "SELECT sum(days_present) FROM attendance_q1") != []  # Jan to Mar


def test_quarters_are_fiscal_quarters():
    """Q4 2024 is Jan-Mar 2025 and holds the whole register; Q1 2025 is Apr-Jun 2025."""
    assert _period("What did we pay in Q4 2024?", "SELECT sum(gross) FROM salary_register") == []
    risks = _period("What did we pay in Q1 2025?", "SELECT sum(gross) FROM salary_register")
    assert len(risks) == 1 and "Q1 2025" in risks[0]
    assert _period("What did we pay in Q1 FY25?",
                   "SELECT sum(gross) FROM salary_register") != []  # Apr-Jun 2024


def test_a_table_joined_only_for_a_label_is_never_named():
    """Sample data, 2026-09-20: employees' joining dates start in 2015, so naming every table
    the query reads put "the query does not use any date from employees" on four of the dev
    questions in eval/golden.yaml (joi-01, joi-02, joi-03, fan-01), all of them correct
    answers whose period was already pinned by the register they joined."""
    assert _period("What did we pay each joiner in 2025?",
                   "SELECT e.emp_id, sum(s.gross) FROM employees e"
                   " JOIN salary_register s ON e.emp_id = s.emp_code GROUP BY 1") == []


def test_the_table_the_number_comes_from_is_still_checked_through_a_join():
    """FY26 starts after the whole register, so nothing pins the query to it. The register is
    named because the sum is taken from it; employees is not, although its dates also fall
    outside FY26 - it only supplies the department label."""
    risks = _period("What did we pay each department in FY26?",
                    "SELECT e.department, sum(s.gross) FROM employees e"
                    " JOIN salary_register s ON e.emp_id = s.emp_code GROUP BY 1")
    assert len(risks) == 1
    assert "salary_register" in risks[0] and "employees" not in risks[0]


def test_counting_rows_names_every_table_because_count_names_none():
    """count(*) takes its number from no column, so every table read is part of the answer."""
    risks = _period("How many payslips did we issue in FY26?",
                    "SELECT count(*) FROM employees e"
                    " JOIN salary_register s ON e.emp_id = s.emp_code")
    assert len(risks) == 2
    assert any("from employees, which covers Nov 2017 to Jun 2025." in r for r in risks)
    assert any("from salary_register, which covers Jan 2025 to Feb 2025." in r for r in risks)


def test_the_words_quoted_back_are_the_words_the_question_used():
    """The period is read from the question as written. Lower-casing it first shifted the
    offsets after any character that grows when lowered, and quoted "025" back at the user."""
    risks = _period("What did the İstanbul office pay in 2025?",
                    "SELECT count(*) FROM employees")
    assert len(risks) == 1 and "names 2025," in risks[0]


def test_nonsense_never_raises():
    query = validate_sql("SELECT sum(gross) FROM salary_register", CATALOG)
    for question in ["", "FY 2024-2026?", "q9 2025", "FY", "2025-26", "Q1 March 2025",
                     "13/2025 fy'2 0 2 5", "… 2025 … 2024 …"]:
        assert isinstance(period_risks(question, query, CATALOG), list)
