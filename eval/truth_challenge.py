"""Ground truth for the challenge set: the same pandas-over-`_clean` method as eval/truth.py.

Why a second truth module rather than more functions in the first: the challenge set is graded
and reported separately and is never tuned on, so keeping its expected answers in their own file
makes it obvious that nothing here was written to make a golden number come out right.

The private helpers of eval/truth.py are reused (`_load`, `_rows`, `_active`, ...). They are
plain pandas over `demo_data/_clean`, and duplicating them would only create a second place for
a loading bug to hide. Neither module imports the app: that independence is the whole point.

Conventions are eval/truth.py's, with one addition. Where a result buckets by a category *and*
a month (`average_order_value_by_category_and_month`), the month is left out of the expected
rows for the same reason the docstring there gives for pure time buckets: "2025-01", "Jan 2025"
and a real date are all honest spellings, and the comparer only needs the expected columns to
be a subset of the ones that came back.
"""

from __future__ import annotations

import pandas as pd

from eval.truth import _active, _employees, _load, _plain, _rows, _values_in_order

_FIFTEEN_LAKH = 1_500_000


# ---------------------------------------------------------------- chains and shares


def gross_2025_by_department_for_top_rated() -> list[tuple]:
    """Three tables in one chain: performance picks the people, employees gives the department,
    payroll holds the money. A sum, not an average, because employees who joined or left during
    2025 have fewer than twelve payslips: "average monthly gross" would then mean two different
    numbers depending on whether you average rows or people."""
    reviews = _load("performance")
    top_rated = reviews[(reviews["review_cycle"] == "H2 2025") & (reviews["rating"] >= 4)]["emp_id"]
    payroll = _load("payroll")
    paid = payroll[payroll["emp_id"].isin(top_rated)].merge(_employees(), on="emp_id")
    return _rows(paid.groupby("department")["gross"].sum())


def share_of_gross_by_department_2025() -> list[tuple]:
    """Percent of total: the denominator is the whole register, not the group. A query that
    divides by the group's own total gives 100% six times over."""
    payroll = _load("payroll")
    by_department = payroll.merge(_employees(), on="emp_id").groupby("department")["gross"].sum()
    return _rows(100 * by_department / payroll["gross"].sum())


def bonus_as_share_of_gross_2025() -> float:
    """Two sheets of one workbook: bonuses over the payroll register."""
    return float(100 * _load("bonuses")["amount"].sum() / _load("payroll")["gross"].sum())


# ---------------------------------------------------------------- ranking, middle, change


def top_five_exit_reasons_2025() -> list[tuple]:
    """Top-N with a tie inside it: ranks four and five both have 3 people, so the five reasons
    are a set and not a ranking, and a query that drops a tied row returns four."""
    employees = _employees()
    counts = employees[employees["exit_date"].dt.year == 2025].groupby("exit_reason").size()
    ranked = counts.sort_values(ascending=False)
    assert ranked.iloc[4] != ranked.iloc[5], "a tie across the cut would make the top five arbitrary"
    return _rows(ranked.head(5))


def median_gross_last_quarter() -> float:
    """A median (not an average) of one payslip's gross, over a period the question only
    describes: the register runs January to December 2025, so "the last quarter of the data" is
    October to December. The whole-year median is ₹72,000, so the period has to be found."""
    payroll = _load("payroll")
    last_quarter = payroll["pay_month"].between("2025-10-01", "2025-12-31")
    return float(payroll.loc[last_quarter, "gross"].median())


def net_pay_change_month_on_month_2025() -> list[tuple]:
    """Each month against the one before: eleven differences for twelve months, some negative.
    Only the amounts are expected; see the module docstring on month spellings."""
    monthly = _load("payroll").groupby("pay_month")["net"].sum().sort_index()
    return _values_in_order(monthly.diff().dropna())


# ---------------------------------------------------------------- cohorts, conditions, absence


def share_of_2024_joiners_who_left_within_12_months() -> float:
    """A cohort measured against itself: the denominator is the 2024 joiners, not the headcount.
    (The generator keeps every exit 10 days clear of an anniversary, so days and months agree.)"""
    employees = _employees()
    cohort = employees[employees["date_of_joining"].dt.year == 2024]
    left_early = cohort["exit_date"] < cohort["date_of_joining"] + pd.DateOffset(years=1)
    return float(100 * left_early.sum() / len(cohort))


def active_headcount_above_and_below_15_lakh_by_location() -> list[tuple]:
    """Conditional aggregation: two counts per row from one pass, split on a boundary exactly
    one active employee sits on. "More than 15 lakh" excludes them; "15 lakh or less" keeps them."""
    counted = _active().groupby("location")["ctc"].agg(
        above=lambda ctc: (ctc > _FIFTEEN_LAKH).sum(),
        at_or_below=lambda ctc: (ctc <= _FIFTEEN_LAKH).sum(),
    )
    return [(str(location), _plain(row.above), _plain(row.at_or_below))
            for location, row in counted.iterrows()]


def departments_with_no_exits_jan_to_jun_2025() -> list[tuple]:
    """A negation: the departments that are absent from a filtered set, which needs an anti-join
    (NOT IN / NOT EXISTS / LEFT JOIN ... IS NULL), not a WHERE clause on exits.

    Why January to June and not the whole year: every department lost somebody in 2025, so the
    year-long version's honest answer is an empty table, and an empty expected result would pass
    on any query that happens to return nothing. Six months leaves exactly one row (Finance), and
    dropping June would leave the same one, so the end of the period is not a coin flip either."""
    employees = _employees()
    lost_somebody = employees.loc[employees["exit_date"].between("2025-01-01", "2025-06-30"), "department"]
    return [(str(department),) for department in sorted(set(employees["department"]) - set(lost_somebody))]


def days_absent_from_attendance_q2_file() -> int:
    """The union view filtered back down to one of the files it was stacked from, which only
    works if `attendance_all` kept a `source_file` column."""
    return int(_load("attendance_q2")["days_absent"].sum())


# ---------------------------------------------------------------- people and customers


def highest_paid_active_employee_per_department() -> list[tuple]:
    """One row per group, picked by a maximum in another column: a plain MAX(ctc) loses the name,
    and a join back on the maximum is the usual way to get it wrong.

    The names are the point of the PII rule: they reach the analyst in the result table, and the
    model only ever sees a ⟦P…⟧ token for them. In Operations the highest paid person overall has
    left, so "active" changes the answer."""
    active = _active()
    # Every row holding its department's maximum, not one per department: `idxmax` picks a winner
    # silently, so a tie has to be caught before it is thrown away. Two people on the same top
    # CTC would make this question a coin flip and a correct answer could score as wrong.
    highest = active[active["ctc"] == active.groupby("department")["ctc"].transform("max")]
    assert not highest.duplicated("department").any(), "two people tied at the top of a department"
    return [(str(row.department), str(row.name), _plain(row.ctc)) for row in highest.itertuples()]


def active_headcount_by_department() -> list[tuple]:
    """There is no `business_unit` column; `department` is the near one. The expected rows are
    what a stated assumption should produce. An honest refusal naming the missing column is
    graded as acceptable too (eval/challenge.yaml, `kind: assume_or_refuse`)."""
    return _rows(_active().groupby("department").size())


def average_order_value_by_category_and_month() -> list[tuple]:
    """Two dimensions at once, on the data that has nothing to do with HR. Average revenue per
    order, so the measure is AVG(revenue), not SUM(revenue) / a count of anything else."""
    sales = _load("sales")
    by_month = sales.groupby([sales["category"], sales["order_date"].dt.to_period("M")])["revenue"].mean()
    return [(str(category), _plain(value)) for (category, _month), value in by_month.items()]


def repeat_customers_december_2025() -> int:
    """Repeat business inside one month: customers with more than one order, counted once each.
    Counting orders instead of customers, or forgetting the month, both give a bigger number."""
    sales = _load("sales")
    december = sales[sales["order_date"].between("2025-12-01", "2025-12-31")]
    return int((december.groupby("customer").size() > 1).sum())
