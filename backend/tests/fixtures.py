"""A tiny hand-built session so query-pipeline modules can be tested without ingestion.

Lead-owned and read-only for build agents. The numbers are small enough to verify by eye:
8 employees, 2 pay months, 2 attendance quarters. CANARY_* values are planted PII that must
never appear in any prompt payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from app.catalog.glossary import DEFAULT_GLOSSARY
from app.contracts import (
    Answer,
    Catalog,
    ColumnProfile,
    DataHealth,
    Relationship,
    TableProfile,
    UnionView,
)
from app.sessions import Turn

CANARY_NAME = "Zebulon Quartermaine"
CANARY_EMAIL = "zebulon.canary@example.com"

_EMPLOYEES = [
    # emp_id, name, email, department, location, gender, joined, exited, ctc
    ("E001", "Asha Rao", "asha.rao@example.com", "Engineering", "Bengaluru", "F", "2019-04-01", None, 2400000),
    ("E002", "Vikram Shah", "vikram.shah@example.com", "Engineering", "Pune", "M", "2020-07-15", None, 1800000),
    ("E003", "Meera Iyer", "meera.iyer@example.com", "Sales", "Mumbai", "F", "2018-01-10", "2025-03-31", 1500000),
    ("E004", "Rohan Das", "rohan.das@example.com", "Sales", "Mumbai", "M", "2021-09-01", None, 1200000),
    ("E005", "Kavya Nair", "kavya.nair@example.com", "HR", "Bengaluru", "F", "2022-02-14", None, 900000),
    ("E006", "Arjun Mehta", "arjun.mehta@example.com", "Engineering", "Hyderabad", "M", "2017-11-20", "2025-06-30", 3000000),
    ("E007", "Sana Khan", "sana.khan@example.com", "Sales", "Pune", "F", "2023-05-05", None, 1100000),
    ("E008", CANARY_NAME, CANARY_EMAIL, "HR", "Hyderabad", "M", "2024-01-08", None, None),
]

# column -> (type, role, pii, is_identifier)
_META = {
    "employees": {
        "emp_id": ("text", "employee_id", None, True),
        "name": ("text", "person_name", "person_name", False),
        "email": ("text", None, "email", False),
        "department": ("text", "department", None, False),
        "location": ("text", "location", None, False),
        "gender": ("text", "gender", None, False),
        "date_of_joining": ("date", "join_date", None, False),
        "exit_date": ("date", "exit_date", None, False),
        "ctc": ("currency", "ctc", None, False),
    },
    "salary_register": {
        "emp_code": ("text", "employee_id", None, True),
        "pay_month": ("date", "pay_month", None, False),
        "gross": ("currency", "gross", None, False),
        "net": ("currency", "net", None, False),
    },
    "attendance_q1": {
        "emp_id": ("text", "employee_id", None, True),
        "month": ("date", "date", None, False),
        "days_present": ("integer", "days_present", None, False),
        "days_absent": ("integer", "days_absent", None, False),
    },
}
_META["attendance_q2"] = _META["attendance_q1"]
_META["attendance_all"] = {**_META["attendance_q1"], "source_file": ("text", None, None, False)}


def _build_db() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE employees (emp_id VARCHAR, name VARCHAR, email VARCHAR, department VARCHAR,"
        " location VARCHAR, gender VARCHAR, date_of_joining DATE, exit_date DATE, ctc DOUBLE)"
    )
    conn.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?)", _EMPLOYEES)
    conn.execute(
        "CREATE TABLE salary_register AS SELECT emp_id AS emp_code, m AS pay_month,"
        " round(coalesce(ctc, 720000) / 12) AS gross, round(coalesce(ctc, 720000) / 12 * 0.8) AS net"
        " FROM employees, (VALUES (DATE '2025-01-01'), (DATE '2025-02-01')) t(m)"
    )
    for table, months in (("attendance_q1", (1, 2, 3)), ("attendance_q2", (4, 5, 6))):
        conn.execute(
            f"CREATE TABLE {table} AS SELECT emp_id, make_date(2025, m, 1) AS month,"
            " 20 + (row_number() OVER (ORDER BY emp_id, m)) % 3 AS days_present,"
            " 2 - (row_number() OVER (ORDER BY emp_id, m)) % 3 AS days_absent"
            f" FROM employees, (SELECT unnest({list(months)}) AS m)"
        )
    # source_file holds member TABLE names, as app.catalog.unions writes them: a file name
    # is text the uploader chose and never reaches a prompt (DECISIONS 16(b)).
    conn.execute(
        "CREATE VIEW attendance_all AS"
        " SELECT *, 'attendance_q1' AS source_file FROM attendance_q1"
        " UNION ALL BY NAME SELECT *, 'attendance_q2' AS source_file FROM attendance_q2"
    )
    return conn


def _profile(conn: duckdb.DuckDBPyConnection, table: str, source: str, is_view=False) -> TableProfile:
    rows = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    columns = []
    for name, (ctype, role, pii, is_id) in _META[table].items():
        nulls, distinct, lo, hi = conn.execute(
            f"SELECT count(*) - count({name}), count(DISTINCT {name}),"
            f" min({name})::VARCHAR, max({name})::VARCHAR FROM {table}"
        ).fetchone()
        values = None
        if not pii and distinct <= 30 and ctype == "text":
            values = [r[0] for r in conn.execute(
                f"SELECT DISTINCT {name} FROM {table} WHERE {name} IS NOT NULL ORDER BY 1").fetchall()]
        columns.append(ColumnProfile(
            name=name, label=name, type=ctype, role=role, pii=pii, is_identifier=is_id,
            is_unique=distinct == rows and nulls == 0, null_fraction=nulls / rows,
            distinct_count=distinct, min=None if pii or ctype == "text" else lo,
            max=None if pii or ctype == "text" else hi, values=values,
        ))
    health = DataHealth(rows=rows, columns=len(columns),
                        pii_columns=[c.name for c in columns if c.pii])
    return TableProfile(name=table, source_file=source, row_count=rows, columns=columns,
                        health=health, is_view=is_view)


@dataclass
class FixtureSession:
    id: str
    conn: duckdb.DuckDBPyConnection
    catalog: Catalog
    history: list[Turn] = field(default_factory=list)
    answer_cache: dict[str, Answer] = field(default_factory=dict)

    def cursor(self) -> duckdb.DuckDBPyConnection:
        return self.conn.cursor()


def make_session() -> FixtureSession:
    conn = _build_db()
    tables = [
        _profile(conn, "employees", "employees.csv"),
        _profile(conn, "salary_register", "Salary_Register_2025.xlsx"),
        _profile(conn, "attendance_q1", "attendance_q1.csv"),
        _profile(conn, "attendance_q2", "attendance_q2.csv"),
        _profile(conn, "attendance_all", "attendance_q1.csv + attendance_q2.csv", is_view=True),
    ]
    catalog = Catalog(
        session_id="fixture", version=1, fingerprint="fixture", tables=tables,
        relationships=[
            Relationship(id="employees.emp_id->salary_register.emp_code",
                         left_table="employees", left_column="emp_id",
                         right_table="salary_register", right_column="emp_code",
                         match_left=1.0, match_right=1.0, cardinality="1:N", status="active"),
            Relationship(id="attendance_q1.emp_id->employees.emp_id",
                         left_table="attendance_q1", left_column="emp_id",
                         right_table="employees", right_column="emp_id",
                         match_left=1.0, match_right=1.0, cardinality="N:1", status="active"),
        ],
        unions=[UnionView(id="attendance_all", view_name="attendance_all",
                          tables=["attendance_q1", "attendance_q2"], status="active")],
        glossary=list(DEFAULT_GLOSSARY),
    )
    return FixtureSession(id="fixture", conn=conn, catalog=catalog)
