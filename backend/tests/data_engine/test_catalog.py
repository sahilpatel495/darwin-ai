"""Relationship detection and same-schema union views."""

from __future__ import annotations

import duckdb
import pytest
from app.catalog.relationships import detect_relationships
from app.catalog.unions import create_union_views, detect_unions
from app.contracts import ColumnProfile, DataHealth, Relationship, TableProfile, UnionView

from tests.fixtures import make_session

# --------------------------------------------------------------------------
# Relationships
# --------------------------------------------------------------------------


def _column(name: str, ctype: str = "text", **kw) -> ColumnProfile:
    return ColumnProfile(name=name, label=name, type=ctype, **kw)


def _table(name: str, columns: list[ColumnProfile], rows: int = 0, source: str | None = None,
           sheet: str | None = None, **health) -> TableProfile:
    return TableProfile(name=name, source_file=source or f"{name}.csv", sheet=sheet, row_count=rows, columns=columns,
                        health=DataHealth(rows=rows, columns=len(columns), **health))


def _by_id(links: list[Relationship]) -> dict[str, Relationship]:
    return {r.id: r for r in links}


def test_fixture_shapes_give_the_expected_links():
    session = make_session()
    links = _by_id(detect_relationships(session.conn, session.catalog.tables, []))

    master = links["employees.emp_id->salary_register.emp_code"]
    assert (master.cardinality, master.status, master.match_left, master.match_right) == ("1:N", "active", 1.0, 1.0)
    attendance = links["attendance_q1.emp_id->employees.emp_id"]
    assert (attendance.cardinality, attendance.status) == ("N:1", "active")
    # Attendance and payroll both hang off the employee master, so the direct N:M link
    # between them (a fan-out trap) is not advertised.
    assert sorted(links) == ["attendance_q1.emp_id->employees.emp_id", "attendance_q2.emp_id->employees.emp_id",
                             "employees.emp_id->salary_register.emp_code"]

    for link in links.values():
        assert link.left_table < link.right_table  # ids are stable because tables are sorted
        assert "attendance_all" not in (link.left_table, link.right_table)  # views are never linked
    # Two halves of the same export are stacked, not joined.
    assert "attendance_q1.emp_id->attendance_q2.emp_id" not in links
    # Measures and dates are not keys, however much their values overlap.
    assert not any("days_present" in link.id or "month" in link.id for link in links.values())


def test_no_link_between_a_measure_and_an_unrelated_integer_column():
    session = make_session()
    session.conn.execute("CREATE TABLE stock AS SELECT 'S' || i AS sku, 19 + i AS units FROM range(1, 5) t(i)")
    stock = _table("stock", [_column("sku", is_unique=True), _column("units", "integer", role="quantity", is_unique=True)], 4)
    links = detect_relationships(session.conn, [*session.catalog.tables, stock], [])
    assert not any("stock" in link.id for link in links)


def test_a_user_decision_survives_re_detection():
    session = make_session()
    found = detect_relationships(session.conn, session.catalog.tables, [])
    rejected = [r.model_copy(update={"status": "rejected"}) if r.left_table == "employees" else r for r in found]
    again = _by_id(detect_relationships(session.conn, session.catalog.tables, rejected))
    assert again["employees.emp_id->salary_register.emp_code"].status == "rejected"
    assert again["attendance_q1.emp_id->employees.emp_id"].status == "active"


_KEY = _column("emp_id", role="employee_id", is_identifier=True, is_unique=True)


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    yield connection
    connection.close()


def test_partial_overlap_is_only_suggested_and_a_user_can_confirm_it(conn):
    conn.execute("CREATE TABLE staff AS SELECT 'E' || i AS emp_id FROM range(10) t(i)")
    conn.execute("CREATE TABLE badges AS SELECT 'E' || i AS emp_id, DATE '2025-01-01' AS issued_on FROM range(4, 24) t(i)")  # 6 of 10, 6 of 20
    tables = [_table("staff", [_KEY], 10), _table("badges", [_KEY, _column("issued_on", "date")], 20)]
    (link,) = detect_relationships(conn, tables, [])
    assert link.id == "badges.emp_id->staff.emp_id"
    assert (link.match_left, link.match_right, link.cardinality, link.status) == (0.3, 0.6, "1:1", "suggested")

    confirmed = [link.model_copy(update={"status": "active"})]
    assert detect_relationships(conn, tables, confirmed)[0].status == "active"


def test_a_child_table_covering_few_employees_is_still_a_sound_link(conn):
    """Only a quarter of staff got a bonus, but every bonus row points at a known employee.
    That is what makes a join safe, so the link is on by default."""
    conn.execute("CREATE TABLE staff AS SELECT 'E' || i AS emp_id FROM range(100) t(i)")
    conn.execute("CREATE TABLE bonuses AS SELECT 'E' || (i % 25) AS emp_id, 1000 * i AS amount FROM range(40) t(i)")
    tables = [_table("staff", [_KEY], 100),
              _table("bonuses", [_KEY.model_copy(update={"is_unique": False}), _column("amount", "currency", role="amount")], 40)]
    (link,) = detect_relationships(conn, tables, [])
    assert (link.id, link.cardinality, link.status) == ("bonuses.emp_id->staff.emp_id", "N:1", "active")
    assert (link.match_left, link.match_right) == (1.0, 0.25)


def test_a_many_to_many_link_gives_way_to_the_master_table_whatever_the_upload_order(conn):
    conn.execute("CREATE TABLE attendance AS SELECT 'E' || (i % 5) AS emp_id, i AS days FROM range(10) t(i)")
    conn.execute("CREATE TABLE payroll AS SELECT 'E' || (i % 5) AS emp_code, i AS gross FROM range(10) t(i)")
    many = {"role": "employee_id", "is_identifier": True}
    attendance = _table("attendance", [_column("emp_id", **many), _column("days", "integer")], 10)
    payroll = _table("payroll", [_column("emp_code", **many), _column("gross", "currency")], 10)
    (direct,) = detect_relationships(conn, [attendance, payroll], [])
    assert (direct.id, direct.cardinality, direct.status) == ("attendance.emp_id->payroll.emp_code", "N:M", "active")

    # The employee master arrives in a second upload. The earlier link was switched on by the
    # detector, not by the user, so it is not a decision to preserve.
    conn.execute("CREATE TABLE staff AS SELECT 'E' || i AS emp_id FROM range(5) t(i)")
    staff = _table("staff", [_KEY], 5)
    later = _by_id(detect_relationships(conn, [attendance, payroll, staff], [direct]))
    assert sorted(later) == ["attendance.emp_id->staff.emp_id", "payroll.emp_code->staff.emp_id"]

    # A user who rejected it said something the detector would not have: that is remembered.
    rejected = [direct.model_copy(update={"status": "rejected"})]
    assert _by_id(detect_relationships(conn, [attendance, payroll, staff], rejected))[direct.id].status == "rejected"


def test_weak_overlap_is_dropped(conn):
    conn.execute("CREATE TABLE staff AS SELECT 'E' || i AS emp_id FROM range(10) t(i)")
    conn.execute("CREATE TABLE badges AS SELECT 'E' || i AS emp_id, DATE '2025-01-01' AS issued_on FROM range(6, 26) t(i)")  # 4 of 10
    tables = [_table("staff", [_KEY], 10), _table("badges", [_KEY, _column("issued_on", "date")], 20)]
    assert detect_relationships(conn, tables, []) == []


def test_ids_that_only_share_values_are_never_switched_on_automatically(conn):
    """order 1..50 and store 1..50 overlap perfectly and mean nothing; the user must confirm."""
    conn.execute("CREATE TABLE orders AS SELECT CAST(i AS VARCHAR) AS order_id FROM range(1, 51) t(i)")
    conn.execute("CREATE TABLE stores AS SELECT CAST(i AS VARCHAR) AS store_id FROM range(1, 51) t(i)")
    tables = [_table("orders", [_column("order_id", is_identifier=True, is_unique=True)], 50),
              _table("stores", [_column("store_id", is_identifier=True, is_unique=True)], 50)]
    (link,) = detect_relationships(conn, tables, [])
    assert link.status == "suggested" and link.match_left == 1.0


def test_an_employee_id_is_not_linked_to_a_manager_id_in_another_table(conn):
    conn.execute("CREATE TABLE org AS SELECT 'E' || i AS emp_id, 'E' || (i % 3) AS manager_id FROM range(10) t(i)")
    conn.execute("CREATE TABLE pay AS SELECT 'E' || i AS emp_code FROM range(10) t(i)")
    tables = [
        _table("org", [_column("emp_id", role="employee_id", is_identifier=True, is_unique=True),
                       _column("manager_id", role="manager_id", is_identifier=True)], 10),
        _table("pay", [_column("emp_code", role="employee_id", is_identifier=True, is_unique=True)], 10),
    ]
    assert [r.id for r in detect_relationships(conn, tables, [])] == ["org.emp_id->pay.emp_code"]


def test_a_shared_category_links_only_to_a_lookup_table(conn):
    conn.execute("CREATE TABLE people AS SELECT * FROM (VALUES ('Sales', 1), ('Sales', 2), ('HR', 3)) t(department, ctc)")
    conn.execute("CREATE TABLE budgets AS SELECT * FROM (VALUES ('Sales', 1), ('HR', 2), ('Finance', 3)) t(department, budget)")
    conn.execute("CREATE TABLE visits AS SELECT * FROM (VALUES ('Sales', 1), ('Sales', 2), ('HR', 3), ('HR', 4)) t(department, visitors)")
    people = _table("people", [_column("department", role="department"), _column("ctc", "integer", role="ctc")], 3)
    budgets = _table("budgets", [_column("department", role="department", is_unique=True), _column("budget", "integer")], 3)
    visits = _table("visits", [_column("department", role="department"), _column("visitors", "integer")], 4)
    ids = [r.id for r in detect_relationships(conn, [people, budgets, visits], [])]
    assert sorted(ids) == ["budgets.department->people.department", "budgets.department->visits.department"]


def test_a_hostile_workbook_of_id_columns_cannot_flood_the_prompt_with_links(conn, monkeypatch):
    from app.catalog import relationships

    monkeypatch.setattr(relationships, "MAX_CANDIDATES", 12)
    monkeypatch.setattr(relationships, "MAX_LINKS", 5)
    names = [f"k{i}_id" for i in range(6)]
    for table in ("wide_a", "wide_b"):
        conn.execute(f"CREATE TABLE {table} AS SELECT " + ", ".join(f"'V' || (i % 7) AS {n}" for n in names) + " FROM range(50) t(i)")
    a = _table("wide_a", [_column(n, is_identifier=True) for n in names], 50)
    b = _table("wide_b", [_column(n, is_identifier=True) for n in names] + [_column("note")], 50)
    executed = []
    conn_execute = conn.execute

    class Counting:
        def execute(self, sql):
            executed.append(sql)
            return conn_execute(sql)

    links = detect_relationships(Counting(), [a, b], [])
    assert len(executed) == 12 and len(links) == 5  # 36 possible pairs, 12 measured, 5 kept


def test_pii_columns_are_not_offered_as_join_keys_but_nulls_and_quotes_are_handled(conn):
    conn.execute('CREATE TABLE a AS SELECT * FROM (VALUES (\'x\', \'Asha\'), (NULL, \'Ravi\')) t("emp_id", "name")')
    conn.execute('CREATE TABLE b AS SELECT * FROM (VALUES (\'x\', \'Asha\'), (\'y\', \'Ravi\')) t("emp_id", "name")')
    columns = [_column("emp_id", is_identifier=True), _column("name", pii="person_name", is_unique=True)]
    a, b = _table("a", columns, 2), _table("b", [c.model_copy() for c in columns] + [_column("extra")], 2)
    links = detect_relationships(conn, [a, b], [])
    assert [r.id for r in links] == ["a.emp_id->b.emp_id"]
    assert (links[0].match_left, links[0].match_right) == (1.0, 0.5)  # the null is not a value


# --------------------------------------------------------------------------
# Unions
# --------------------------------------------------------------------------


def _attendance(name: str, source: str | None = None, sheet: str | None = None, **kw) -> TableProfile:
    return _table(name, [_column("emp_id", is_identifier=True), _column("days_absent", "integer")], source=source, sheet=sheet, **kw)


def test_same_schema_tables_are_grouped_and_named_from_their_common_tokens():
    tables = [_attendance("attendance_q1"), _attendance("attendance_q2"), _table("employees", [_column("emp_id")])]
    (union,) = detect_unions(tables, [])
    assert union == UnionView(id="attendance_all", view_name="attendance_all",
                              tables=["attendance_q1", "attendance_q2"], status="active")


@pytest.mark.parametrize(("names", "view"), [
    (["sales_jan", "sales_feb"], "sales_all"),
    (["payroll_2025_h1", "payroll_2025_h2"], "payroll_2025_all"),
    (["north", "south"], "combined_1"),
    (["sales", "sales_2"], "sales_all"),
])
def test_view_names(names, view):
    assert detect_unions([_attendance(n) for n in names], [])[0].view_name == view


def test_different_types_or_columns_are_not_the_same_schema():
    text_days = _table("attendance_q3", [_column("emp_id", is_identifier=True), _column("days_absent", "text")])
    extra = _table("attendance_q4", [_column("emp_id"), _column("days_absent", "integer"), _column("note")])
    assert detect_unions([_attendance("attendance_q1"), text_days, extra], []) == []


def test_views_are_never_members_and_a_rejection_is_remembered():
    view = _attendance("attendance_all").model_copy(update={"is_view": True})
    existing = [UnionView(id="attendance_all", view_name="attendance_all", tables=["attendance_q1", "attendance_q2"], status="rejected")]
    (union,) = detect_unions([_attendance("attendance_q1"), _attendance("attendance_q2"), _attendance("attendance_q3"), view], existing)
    assert union.tables == ["attendance_q1", "attendance_q2", "attendance_q3"] and union.status == "rejected"


def test_a_view_name_never_collides_with_a_real_table():
    tables = [_attendance("attendance_q1"), _attendance("attendance_q2"), _table("attendance_all", [_column("x")])]
    assert detect_unions(tables, [])[0].view_name == "attendance_all_2"


def test_tables_that_already_have_a_source_file_column_are_left_alone():
    tables = [_table(n, [_column("emp_id"), _column("source_file")]) for n in ("a_1", "a_2")]
    assert detect_unions(tables, []) == []


def _load_attendance(conn) -> list[TableProfile]:
    conn.execute("CREATE TABLE attendance_q1 AS SELECT * FROM (VALUES ('E1', 1, 'Pune'), ('E2', 0, 'Pune')) t(emp_id, days_absent, site)")
    conn.execute("CREATE TABLE attendance_q2 AS SELECT * FROM (VALUES (2, 'E1', 'Pune'), (NULL, 'E3', 'Goa')) t(days_absent, emp_id, site)")
    def columns(sites):
        return [_column("emp_id", role="employee_id", is_identifier=True, is_unique=True, values=None),
                _column("days_absent", "integer", role="days_absent"),
                _column("site", values=sites)]
    return [_table("attendance_q1", columns(["Pune"]), 2, duplicate_rows=1),
            _table("attendance_q2", columns(["Goa", "Pune"]), 2, duplicate_rows=3, duplicates_removed=True)]


def test_the_view_stacks_members_by_name_and_is_profiled_from_the_real_rows(conn):
    tables = _load_attendance(conn)
    unions = detect_unions(tables, [])
    (view,) = create_union_views(conn, unions, tables)

    rows = conn.execute("SELECT emp_id, days_absent, source_file FROM attendance_all ORDER BY source_file, emp_id").fetchall()
    assert rows == [("E1", 1, "attendance_q1.csv"), ("E2", 0, "attendance_q1.csv"),
                    ("E1", 2, "attendance_q2.csv"), ("E3", None, "attendance_q2.csv")]

    assert view.is_view and view.name == "attendance_all" and view.row_count == 4
    assert view.source_file == "attendance_q1.csv + attendance_q2.csv"
    assert [c.name for c in view.columns] == ["emp_id", "days_absent", "site", "source_file"]
    emp_id, days, site, source = view.columns
    assert emp_id.is_identifier and emp_id.role == "employee_id"
    assert not emp_id.is_unique and emp_id.distinct_count == 3  # E1 is in both files
    assert (days.min, days.max, days.null_fraction) == ("0", "2", 0.25)
    assert site.values == ["Goa", "Pune"]
    assert (source.type, source.values, source.pii) == ("text", ["attendance_q1.csv", "attendance_q2.csv"], None)
    assert view.health.rows == 4 and view.health.duplicate_rows == 1  # only duplicates that are still in the data


def test_a_column_that_is_pii_in_any_member_is_pii_in_the_view(conn):
    tables = _load_attendance(conn)
    tables[1].columns[2].pii = "person_name"
    tables[1].columns[2].values = None
    (view,) = create_union_views(conn, detect_unions(tables, []), tables)
    site = view.columns[2]
    assert site.pii == "person_name" and site.values is None and view.health.pii_columns == ["site"]


def test_a_date_of_birth_has_no_range_in_the_view_either(conn):
    for name, born in (("staff_a", "1990-05-01"), ("staff_b", "1979-02-14")):
        conn.execute(f"CREATE TABLE {name} AS SELECT 'E1' AS emp_id, DATE '{born}' AS dob, DATE '2020-01-01' AS doj")
    tables = [_table(n, [_column("emp_id", is_identifier=True), _column("dob", "date", role="birth_date"),
                         _column("doj", "date", role="join_date")], 1) for n in ("staff_a", "staff_b")]
    (view,) = create_union_views(conn, detect_unions(tables, []), tables)
    _, dob, doj, _ = view.columns
    assert (dob.min, dob.max) == (None, None) and (doj.min, doj.max) == ("2020-01-01", "2020-01-01")


def test_sheets_of_one_workbook_are_told_apart_in_source_file(conn):
    conn.execute("CREATE TABLE att_jan AS SELECT 'E1' AS emp_id, 1 AS days_absent")
    conn.execute("CREATE TABLE att_feb AS SELECT 'E1' AS emp_id, 2 AS days_absent")
    tables = [_attendance("att_jan", source="Attendance.xlsx", sheet="Jan"), _attendance("att_feb", source="Attendance.xlsx", sheet="Feb")]
    (view,) = create_union_views(conn, detect_unions(tables, []), tables)
    assert view.columns[-1].values == ["Attendance.xlsx / Feb", "Attendance.xlsx / Jan"]
    assert conn.execute("SELECT source_file FROM att_all WHERE days_absent = 2").fetchone()[0] == "Attendance.xlsx / Feb"


def test_rejected_unions_have_no_view(conn):
    tables = _load_attendance(conn)
    unions = detect_unions(tables, [])
    create_union_views(conn, unions, tables)
    rejected = [unions[0].model_copy(update={"status": "rejected"})]
    assert create_union_views(conn, rejected, tables) == []
    with pytest.raises(duckdb.Error):
        conn.execute("SELECT * FROM attendance_all")
