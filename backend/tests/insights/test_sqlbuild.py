"""The SQL builder: what it resolves, what it refuses, and what a request can never reach."""

import pytest
from app.insights import sqlbuild as sb
from app.query.guard import validate_sql
from tests.fixtures import make_session


@pytest.fixture
def session():
    return make_session()


# ---- resolve -------------------------------------------------------------------------------


def test_resolve_returns_catalog_spelling_and_profile(session):
    ref = sb.resolve("employees.ctc", session.catalog, ("measure",))
    assert (ref.table, ref.column) == ("employees", "ctc")
    assert ref.profile.type == "currency"
    assert tuple(ref) == (ref.table, ref.column, ref.profile)  # unpackable


def test_resolve_is_case_insensitive_but_emits_the_catalog_name(session):
    assert sb.resolve("EMPLOYEES.CTC", session.catalog).column == "ctc"


@pytest.mark.parametrize("ref", ["", "employees", "employees.", ".ctc", "a.b.c"])
def test_resolve_refuses_a_reference_that_is_not_table_dot_column(session, ref):
    with pytest.raises(ValueError, match="not a column in your files"):
        sb.resolve(ref, session.catalog)


def test_resolve_refuses_an_unknown_table(session):
    with pytest.raises(ValueError, match="no table named payroll"):
        sb.resolve("payroll.gross", session.catalog)


def test_resolve_refuses_an_unknown_column(session):
    with pytest.raises(ValueError, match="no column named bonus in employees"):
        sb.resolve("employees.bonus", session.catalog)


def test_resolve_refuses_a_pii_column_as_a_category(session):
    with pytest.raises(ValueError, match="personal data"):
        sb.resolve("employees.name", session.catalog, ("category",))


def test_resolve_refuses_a_pii_column_even_with_no_slot(session):
    """A column of email addresses is never a group, whatever slot asked for it."""
    with pytest.raises(ValueError, match="personal data"):
        sb.resolve("employees.email", session.catalog)


def test_resolve_refuses_an_identifier_column(session):
    with pytest.raises(ValueError, match="identifies a row"):
        sb.resolve("employees.emp_id", session.catalog, ("category",))


def test_resolve_refuses_the_wrong_kind_for_the_slot(session):
    with pytest.raises(ValueError, match="cannot fill the measure slot"):
        sb.resolve("employees.department", session.catalog, ("measure",))
    with pytest.raises(ValueError, match="cannot fill the category slot"):
        sb.resolve("employees.ctc", session.catalog, ("category",))


def test_resolve_accepts_a_date_in_a_date_slot(session):
    assert sb.resolve("employees.date_of_joining", session.catalog, ("date",)).column == "date_of_joining"


# ---- column_kind ---------------------------------------------------------------------------


def _profile(session, table: str, column: str):
    """A plain catalog lookup: `resolve` would refuse the PII and identifier columns this
    parametrised test needs to check the kind of."""
    return next(c for t in session.catalog.tables if t.name == table
                for c in t.columns if c.name == column)


@pytest.mark.parametrize("table,column,expected", [
    ("employees", "ctc", "measure"),
    ("attendance_q1", "days_present", "measure"),
    ("employees", "date_of_joining", "date"),
    ("employees", "department", "category"),
    ("employees", "gender", "category"),
    ("employees", "emp_id", "text"),     # identifier: never a measure or a group
    ("employees", "name", "text"),       # PII
    ("employees", "email", "text"),      # PII
])
def test_column_kind(session, table, column, expected):
    assert sb.column_kind(_profile(session, table, column)) == expected


def test_a_high_cardinality_text_column_is_text_not_a_category(session):
    profile = _profile(session, "employees", "department").model_copy(
        update={"distinct_count": sb.MAX_CATEGORY_VALUES + 1})
    assert sb.column_kind(profile) == "text"


# ---- ident, aggregate, date_bucket ---------------------------------------------------------


def test_ident_quotes_and_escapes():
    assert sb.ident("gross") == '"gross"'
    assert sb.ident('we"ird') == '"we""ird"'


@pytest.mark.parametrize("func,expected", [
    ("sum", 'sum("x")'), ("average", 'avg("x")'), ("median", 'median("x")'),
    ("min", 'min("x")'), ("max", 'max("x")'),
])
def test_aggregate(func, expected):
    assert sb.aggregate(func, '"x"') == expected


def test_count_counts_rows_not_filled_cells():
    assert sb.aggregate("count", '"x"') == "count(*)"


def test_aggregate_refuses_anything_off_the_allow_list():
    with pytest.raises(ValueError, match="not something this can calculate"):
        sb.aggregate("sum(x) FROM employees; DROP TABLE employees; --", '"x"')


@pytest.mark.parametrize("grain", sb.GRAINS)
def test_date_bucket(grain):
    assert sb.date_bucket('"m"', grain) == f"date_trunc('{grain}', \"m\")"


def test_date_bucket_refuses_an_unknown_grain():
    with pytest.raises(ValueError, match="not a period this can group by"):
        sb.date_bucket('"m"', "fortnight")


def test_date_bucket_refuses_an_injected_grain():
    with pytest.raises(ValueError, match="not a period this can group by"):
        sb.date_bucket('"m"', "month') , read_csv('/etc/passwd') --")


# ---- from_clause ---------------------------------------------------------------------------


def test_one_table_is_a_plain_from(session):
    ref = sb.resolve("employees.ctc", session.catalog)
    assert sb.from_clause([ref, ref], session.catalog) == 'FROM "employees"'


def test_two_tables_join_through_the_active_link(session):
    refs = [sb.resolve("employees.department", session.catalog),
            sb.resolve("salary_register.gross", session.catalog)]
    clause = sb.from_clause(refs, session.catalog)
    assert clause == ('FROM "employees" JOIN "salary_register"'
                      ' ON "employees"."emp_id" = "salary_register"."emp_code"')


def test_the_join_runs_and_the_guard_accepts_it(session):
    """The clause is not just the right text: it parses, passes the guard and returns rows."""
    group, measure = (sb.resolve("employees.department", session.catalog, ("category",)),
                      sb.resolve("salary_register.gross", session.catalog, ("measure",)))
    refs = [group, measure]
    total = sb.aggregate("sum", f"{sb.ident(measure.table)}.{sb.ident(measure.column)}")
    sql = (f"SELECT {sb.ident(group.table)}.{sb.ident(group.column)} AS department,"
           f" {total} AS total_gross {sb.from_clause(refs, session.catalog)} GROUP BY 1")
    query = validate_sql(sql, session.catalog)
    assert sorted(query.tables) == ["employees", "salary_register"]
    assert len(session.cursor().execute(query.sql).fetchall()) == 3


def test_unlinked_tables_are_refused_rather_than_cross_joined(session):
    refs = [sb.resolve("salary_register.gross", session.catalog),
            sb.resolve("attendance_q1.days_present", session.catalog)]
    with pytest.raises(ValueError, match="not linked"):
        sb.from_clause(refs, session.catalog)


def test_a_rejected_link_is_not_used(session):
    for link in session.catalog.relationships:
        link.status = "rejected"
    refs = [sb.resolve("employees.department", session.catalog),
            sb.resolve("salary_register.gross", session.catalog)]
    with pytest.raises(ValueError, match="not linked"):
        sb.from_clause(refs, session.catalog)


def test_a_many_to_many_link_is_refused_because_it_would_double_count(session):
    session.catalog.relationships[0].cardinality = "N:M"
    refs = [sb.resolve("employees.department", session.catalog),
            sb.resolve("salary_register.gross", session.catalog)]
    with pytest.raises(ValueError, match="more than once"):
        sb.from_clause(refs, session.catalog)


def test_a_measure_from_the_one_side_grouped_by_the_many_side_is_refused(session):
    """One employee has many payslips, so a CTC summed across that join is counted once per
    payslip. A caveat under the number was not enough: the number itself is wrong."""
    ctc = sb.resolve("employees.ctc", session.catalog, ("measure",))
    month = sb.resolve("salary_register.pay_month", session.catalog, ("date",))
    with pytest.raises(ValueError) as caught:
        sb.from_clause([ctc, month], session.catalog, measure=ctc)
    assert str(caught.value) == (
        "ctc is stored once per employee, but pay_month has many rows per employee, so this"
        " would count each ctc several times."
        " Pick a number from the same file as the group.")


def test_a_measure_from_the_many_side_grouped_by_the_one_side_is_still_allowed(session):
    """The common cross-file question — gross pay by department — is not a fan-out: the
    payslips are on the many side and each one is counted once."""
    gross = sb.resolve("salary_register.gross", session.catalog, ("measure",))
    department = sb.resolve("employees.department", session.catalog, ("category",))
    assert sb.from_clause([gross, department], session.catalog, measure=gross).startswith(
        'FROM "salary_register" JOIN "employees"')


def test_the_one_side_is_read_from_the_cardinality_not_from_the_order_of_the_columns(session):
    """The attendance link is recorded the other way round (attendance -> employees, N:1), so
    the one side is that link's right-hand table. The same refusal has to fire."""
    ctc = sb.resolve("employees.ctc", session.catalog, ("measure",))
    month = sb.resolve("attendance_q1.month", session.catalog, ("date",))
    with pytest.raises(ValueError, match="count each ctc several times"):
        sb.from_clause([ctc, month], session.catalog, measure=ctc)


def test_a_one_to_one_link_never_repeats_a_row(session):
    session.catalog.relationships[0].cardinality = "1:1"
    ctc = sb.resolve("employees.ctc", session.catalog, ("measure",))
    month = sb.resolve("salary_register.pay_month", session.catalog, ("date",))
    assert "JOIN" in sb.from_clause([ctc, month], session.catalog, measure=ctc)


def test_one_file_is_never_a_fan_out_whatever_the_measure(session):
    ctc = sb.resolve("employees.ctc", session.catalog, ("measure",))
    group = sb.resolve("employees.department", session.catalog, ("category",))
    assert sb.from_clause([ctc, group], session.catalog, measure=ctc) == 'FROM "employees"'


def test_three_tables_are_refused(session):
    refs = [sb.resolve("employees.department", session.catalog),
            sb.resolve("salary_register.gross", session.catalog),
            sb.resolve("attendance_q1.days_present", session.catalog)]
    with pytest.raises(ValueError, match="two files at a time"):
        sb.from_clause(refs, session.catalog)


def test_no_columns_is_refused(session):
    with pytest.raises(ValueError, match="at least one column"):
        sb.from_clause([], session.catalog)


# ---- nothing from a request reaches the SQL ------------------------------------------------

HOSTILE = [
    "employees.ctc; DROP TABLE employees",
    'employees."ctc" UNION SELECT email FROM employees',
    "employees.ctc' OR '1'='1",
    "employees.*",
    "employees.ctc--",
    "information_schema.tables",
    "read_csv('/etc/passwd').x",
]


@pytest.mark.parametrize("ref", HOSTILE)
def test_a_hostile_reference_never_resolves(session, ref):
    """Every refusal is a plain sentence, and nothing of `ref` is handed back as SQL."""
    with pytest.raises(ValueError) as caught:
        sb.resolve(ref, session.catalog, ("measure", "category", "date"))
    assert "\n" not in str(caught.value)


def test_a_hostile_reference_that_starts_with_a_real_column_still_fails(session):
    """"employees.ctc; DROP ..." must not be truncated to the real column it starts with."""
    with pytest.raises(ValueError):
        sb.resolve("employees.ctc; DROP TABLE employees", session.catalog)


def test_every_identifier_emitted_comes_from_the_catalog(session):
    """The only text a caller can put in the statement is a name that already existed."""
    names = {t.name for t in session.catalog.tables} | {
        c.name for t in session.catalog.tables for c in t.columns}
    ref = sb.resolve("EmPlOyEeS.CtC", session.catalog)
    assert ref.table in names and ref.column in names
    assert sb.ident(ref.column) == '"ctc"'
