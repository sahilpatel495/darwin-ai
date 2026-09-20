"""The two real file sets, through the real ingestion, with no model anywhere.

`test_files/` is the messy set (a fictional retailer) and carries the question this module
exists to answer: does "net pay by region" come out whole? The number is only right when
both sheets of the staff workbook are stacked *and* the payroll link reaches the stacked
view, so this file is the regression test for both.

`demo_data/` is the golden set the eval scores against. Its numbers must not move, so the
second half of this file pins its tables, row counts and active links.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.sessions import SessionStore

ROOT = Path(__file__).resolve().parents[3]
TEST_FILES = ROOT / "test_files"
# The generated 15 MB attendance file is git-ignored and adds seconds; everything the
# headline number needs is committed.
MESSY_FILES = ["staff_master.xlsx", "payroll_register_2025.csv", "stores.csv", "sales_jan.csv",
               "sales_feb.csv", "sales_mar.csv", "exit_interviews.csv",
               "appraisal_two_row_header.xlsx"]

# EXPECTED.md #6, written by pandas from the clean frames before any mess was added.
NET_PAY_BY_REGION = [("West", 35831335), ("South", 33784199), ("East", 32780627), ("North", 32720826)]


@pytest.fixture
def messy():
    missing = [name for name in MESSY_FILES if not (TEST_FILES / name).exists()]
    if missing:
        pytest.skip(f"test_files is not generated: {', '.join(missing)}")
    session = SessionStore().create()
    session.add_files([(TEST_FILES / name, name) for name in MESSY_FILES])
    yield session
    session.close()


def _active(session) -> dict[str, str]:
    return {r.id: r.cardinality for r in session.catalog.relationships if r.status == "active"}


def test_the_two_staff_sheets_are_offered_as_one_combined_view(messy):
    (staff,) = [u for u in messy.catalog.unions if u.view_name.startswith("staff")]
    assert staff.tables == ["staff_master_active", "staff_master_separated"]
    assert staff.status == "active"  # by default: a person would obviously stack these
    view = next(t for t in messy.catalog.tables if t.name == "staff_master_all")
    assert view.is_view and view.row_count == 362 + 58
    # The Active sheet's LWD column is empty, so the view takes the Separated sheet's date.
    lwd = next(c for c in view.columns if c.name == "lwd")
    assert (lwd.type, lwd.null_fraction) == ("date", round(1 - 58 / 420, 4))


def test_payroll_links_to_the_whole_staff_master_not_to_one_sheet(messy):
    active = _active(messy)
    assert active["payroll_register_2025.emp_no->staff_master_all.emp_no"] == "N:1"
    assert not any("staff_master_active" in link or "staff_master_separated" in link
                   for link in active), "a link to half the staff master is the silent-loss bug"


def test_net_pay_by_region_matches_the_expected_answer_to_the_rupee(messy):
    """The headline: payroll -> staff (combined) -> stores, with the links Verity switches
    on by itself. Answered from the Active sheet alone this is 6.3% low."""
    rows = messy.cursor().execute(
        'SELECT s.region, round(sum(p.net_pay)) AS net_pay'
        ' FROM payroll_register_2025 p'
        ' JOIN staff_master_all st ON st.emp_no = p.emp_no'
        ' JOIN stores s ON s.store_code = st.store_code'
        ' GROUP BY 1 ORDER BY 2 DESC'
    ).fetchall()
    assert [(region, int(total)) for region, total in rows] == NET_PAY_BY_REGION


def test_spelling_variants_do_not_split_the_sales_department(messy):
    """EXPECTED.md #3: 195 people in Sales, of whom 164 are active."""
    cursor = messy.cursor()
    assert cursor.execute("SELECT count(*) FROM staff_master_all WHERE department = 'Sales'").fetchone()[0] == 195
    assert cursor.execute("SELECT count(*) FROM staff_master_active WHERE department = 'Sales'").fetchone()[0] == 164
    departments = next(c for t in messy.catalog.tables if t.name == "staff_master_all"
                       for c in t.columns if c.name == "department")
    assert departments.distinct_count == 5


def test_the_two_row_header_file_keeps_its_key_and_joins(messy):
    appraisal = next(t for t in messy.catalog.tables if t.name == "appraisal_two_row_header")
    assert next(c.name for c in appraisal.columns) == "emp_no"
    assert any(link.startswith("appraisal_two_row_header.emp_no->") for link in _active(messy))


def test_the_empty_notes_sheet_is_reported_rather_than_dropped_in_silence(messy):
    active = next(t for t in messy.catalog.tables if t.name == "staff_master_active")
    assert any("Notes" in w and "skipped" in w for w in active.health.warnings)


# --------------------------------------------------------------------------
# demo_data: the golden set, which must keep producing exactly the same numbers
# --------------------------------------------------------------------------

DEMO_ROWS = {"salary_register_2025_register": 5088, "salary_register_2025_bonuses": 150,
             "attendance_q1": 1229, "attendance_q2": 1251, "employees": 500,
             "performance_reviews": 816, "sales": 800, "attendance_all": 2480}
# Every link that was active before combined views were linked, minus the two per-half
# attendance links, which are now one link from the view.
DEMO_LINKS = {
    "attendance_all.emp_id->employees.emp_id": "N:1",
    "employees.emp_id->performance_reviews.employee_id": "1:N",
    "employees.emp_id->salary_register_2025_bonuses.emp_code": "1:N",
    "employees.emp_id->salary_register_2025_register.emp_code": "1:N",
}


@pytest.fixture
def demo():
    if not (ROOT / "demo_data" / "employees.csv").exists():
        pytest.skip("demo_data is not generated")
    session = SessionStore().create()
    session.load_sample()
    yield session
    session.close()


def test_the_sample_data_still_loads_exactly_the_same_tables(demo):
    assert {t.name: t.row_count for t in demo.catalog.tables} == DEMO_ROWS


def test_the_sample_data_links_are_unchanged_apart_from_the_view(demo):
    assert _active(demo) == DEMO_LINKS
    assert [(u.view_name, u.tables, u.status) for u in demo.catalog.unions] == [
        ("attendance_all", ["attendance_q1", "attendance_q2"], "active")]


def test_no_sample_value_is_rewritten_as_a_spelling_variant(demo):
    """The eval's answers are counts and sums over these values. Folding one of them would
    move a number the golden set asserts, so the sample data must have nothing to fold."""
    assert [w for t in demo.catalog.tables for w in t.health.warnings if "read as" in w] == []
