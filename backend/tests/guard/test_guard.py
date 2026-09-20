"""The guard is the security boundary: hostile SQL is refused, honest analytical SQL passes."""

import pytest

from app.contracts import ColumnProfile
from app.query.guard import GuardError, JoinRef, validate_sql
from tests.fixtures import make_session

SESSION = make_session()
CATALOG = SESSION.catalog

# (sql, expected GuardError.code). The first block is the corpus required by the plan.
HOSTILE = [
    ("SELECT 1; SELECT 2", "multi"),
    ("DROP TABLE employees", "write"),
    ("INSERT INTO employees (emp_id) VALUES ('E999')", "write"),
    ("UPDATE employees SET ctc = 0", "write"),
    ("DELETE FROM employees", "write"),
    ("CREATE TABLE x AS SELECT * FROM employees", "write"),
    ("COPY employees TO 'out.csv'", "write"),
    ("ATTACH 'x.db'", "not_select"),
    ("INSTALL httpfs", "not_select"),
    ("LOAD httpfs", "not_select"),
    ("PRAGMA database_list", "not_select"),
    ("SET threads=8", "not_select"),
    ("SELECT * FROM read_csv('/etc/passwd')", "table_function"),
    ("SELECT * FROM '/etc/passwd'", "unknown_table"),
    ("SELECT * FROM read_parquet('https://x/y.parquet')", "table_function"),
    ("SELECT * FROM duckdb_settings()", "table_function"),
    ("SELECT * FROM information_schema.tables", "qualified"),
    ("SELECT * FROM query('select 1')", "table_function"),
    ("SELECT getenv('HOME')", "function"),
    ("CALL pragma_version()", "not_select"),
    ("EXPORT DATABASE 'x'", "parse"),
    ("SELECT * INTO t2 FROM employees", "write"),
    ("SELECT * FROM payroll", "unknown_table"),
    ("SELECT attrition_reason FROM employees", "unknown_column"),
    # Beyond the plan: ways around a guard that only looks at the obvious places.
    ("", "parse"),
    ("-- nothing here", "parse"),
    ("SELEC name FROM employees", "parse"),
    ("SELEC x", "not_select"),  # sqlglot reads this as an aliased column, which is still not a SELECT
    ("SELECT * FROM employees; DROP TABLE employees", "multi"),
    ("WITH gone AS (DELETE FROM employees RETURNING *) SELECT * FROM gone", "write"),
    ("SELECT * FROM employees, LATERAL read_csv('/etc/passwd')", "table_function"),
    ("SELECT e.name FROM employees e WHERE e.emp_id IN (SELECT * FROM read_json('x.json'))", "table_function"),
    ("SELECT * FROM glob('/*')", "table_function"),
    ("SELECT * FROM query_table('employees')", "table_function"),
    ("SELECT * FROM main.employees", "qualified"),
    ("SELECT * FROM memory.main.employees", "qualified"),
    ('SELECT * FROM "employees.csv"', "unknown_table"),
    # A CTE name must not excuse the same name where the CTE is not visible.
    ('SELECT * FROM (WITH "/etc/passwd" AS (SELECT 1 AS x) SELECT * FROM "/etc/passwd") a, "/etc/passwd" b',
     "unknown_table"),
    ("SELECT e.emp_id FROM employees e SEMI JOIN '/etc/passwd' p ON true", "unknown_table"),
    ("SELECT e.emp_id FROM employees e ANTI JOIN read_csv('/etc/passwd') p ON true", "table_function"),
    ("SELECT ('HOME').getenv()", "function"),
    ("SELECT sleep_ms(60000)", "function"),
    ("SELECT current_setting('temp_directory')", "function"),
    ("SELECT read_text('/etc/passwd')", "function"),
    ("SELECT write_log('x')", "function"),
    ("DESCRIBE employees", "not_select"),
    ("SHOW TABLES", "not_select"),
    ("SUMMARIZE employees", "not_select"),
    ("EXPLAIN SELECT 1", "not_select"),
    ("PIVOT employees ON department USING sum(ctc)", "not_select"),  # accepted cut, DECISIONS.md 4
    # These would return PII columns without naming them, so PII tokenisation could miss them.
    ("SELECT COLUMNS('na.*') FROM employees", "unknown_column"),
    ("SELECT #2 FROM employees", "unknown_column"),
    ("SELECT e FROM employees e", "unknown_column"),
    ("SELECT e FROM employees e, generate_series(1, 1)", "unknown_column"),
    ("SELECT (SELECT e FROM generate_series(1, 1)) FROM employees e", "unknown_column"),
    # Found in review: each of these ran and returned names and emails while
    # GuardedQuery.columns listed no PII column at all.
    ("SELECT department FROM employees AS e(emp_id, department)", "unknown_column"),
    ("SELECT * FROM employees PIVOT (count(*) FOR department IN ('HR'))", "unknown_column"),
    ("SELECT * FROM employees UNPIVOT (v FOR k IN (name, email))", "unknown_column"),
    # Found in review: sqlglot types these, so the function allow-list never saw them.
    ("SELECT version()", "function"),
    ("SELECT current_user", "function"),
    ("SELECT current_database(), current_schemas(true)", "function"),
    # The security reviewer's checklist. These were already refused; they stay refused.
    ("SELECT 1 /* */; /* */ DROP TABLE employees", "multi"),
    ("SELECT 1 --\n; DROP TABLE employees", "multi"),
    ('SELECT * FROM "READ_CSV"(\'/etc/passwd\')', "table_function"),
    ("WITH x AS (SELECT * FROM read_text('/etc/passwd')) SELECT * FROM x", "table_function"),
    ("SELECT (SELECT content FROM read_blob('/etc/passwd'))", "table_function"),
    ("SELECT * FROM sniff_csv('/etc/passwd')", "table_function"),
    ("SELECT e.emp_id FROM employees e WHERE EXISTS (SELECT 1 FROM 'secrets.csv')", "unknown_table"),
    ("SELECT * FROM employees LIMIT (SELECT count(*) FROM '/etc/passwd')", "unknown_table"),
    ("ATTACH ':memory:' AS scratch", "not_select"),
    ("SELECT * FROM employees e LEFT JOIN LATERAL glob('/*') g ON true", "table_function"),
    ("SELECT * FROM employees e, LATERAL (SELECT * FROM duckdb_settings()) s", "table_function"),
    ("SELECT name FROM employees UNION ALL SELECT table_name FROM information_schema.tables", "qualified"),
    ("SELECT name FROM employees UNION ALL SELECT name FROM sqlite_master", "unknown_table"),
    ("SELECT * FROM duckdb_tables()", "table_function"),
    ("SELECT * FROM pragma_table_info('employees')", "table_function"),
    ("WITH x AS (COPY employees TO 'x.csv') SELECT 1", "parse"),
    ("SELECT * FROM employees POSITIONAL JOIN '/etc/passwd'", "unknown_table"),
    ("SELECT * FROM unnest(glob('/*'))", "function"),
    ("SELECT list_transform([1], x -> getenv('HOME'))", "function"),
]


@pytest.mark.parametrize(("sql", "code"), HOSTILE, ids=[sql[:50] or "empty" for sql, _ in HOSTILE])
def test_hostile_sql_is_rejected(sql, code):
    with pytest.raises(GuardError) as caught:
        validate_sql(sql, CATALOG)
    assert caught.value.code == code
    assert caught.value.message.endswith(".")  # a sentence for the analyst, not a stack trace


ACCEPTED = [
    # Every query here has an ORDER BY (or one row): the test compares rows in order.
    "SELECT department, avg(ctc) AS avg_ctc FROM employees WHERE location = 'Pune' GROUP BY department ORDER BY 1",
    ("SELECT e.department, sum(s.gross) AS total_gross FROM employees e"
     " JOIN salary_register s ON e.emp_id = s.emp_code GROUP BY 1 ORDER BY total_gross DESC"),
    ("WITH pay AS (SELECT emp_code, sum(gross) AS gross FROM salary_register GROUP BY emp_code)"
     " SELECT e.department, sum(pay.gross) AS total_gross FROM employees e"
     " JOIN pay ON pay.emp_code = e.emp_id GROUP BY e.department ORDER BY 1"),
    ("SELECT department, emp_id, ctc FROM employees"
     " QUALIFY row_number() OVER (PARTITION BY department ORDER BY ctc DESC NULLS LAST) = 1 ORDER BY 1"),
    "SELECT source_file, sum(days_present) AS days_present FROM attendance_all GROUP BY source_file ORDER BY 1",
    "SELECT emp_id FROM employees WHERE ctc > (SELECT avg(ctc) FROM employees) ORDER BY 1",
    ("SELECT t.m AS month_no, count(e.emp_id) AS joiners FROM generate_series(1, 12) AS t(m)"
     " LEFT JOIN employees e ON month(e.date_of_joining) = t.m GROUP BY t.m ORDER BY t.m"),
    ("SELECT date_trunc('month', pay_month) AS pay_month, strftime(pay_month, '%Y-%m') AS label,"
     " sum(gross) AS total_gross FROM salary_register GROUP BY ALL ORDER BY 1"),
    ("SELECT CASE WHEN ctc >= 1500000 THEN 'high' ELSE 'other' END AS band, count(*) AS people"
     " FROM employees GROUP BY band ORDER BY band"),
    "SELECT * EXCLUDE (email) FROM employees ORDER BY emp_id",
    "SELECT department FROM employees UNION SELECT emp_code FROM salary_register ORDER BY 1",
    ("SELECT emp_id, age(coalesce(exit_date, DATE '2025-12-31'), date_of_joining) AS tenure,"
     " date_part('year', date_of_joining) AS joined_year FROM employees ORDER BY emp_id"),
    "SELECT count(*) AS headcount FROM employees;",
    "SELECT e.emp_id FROM employees e ANTI JOIN salary_register s ON e.emp_id = s.emp_code ORDER BY 1",
    # A column list after an alias is refused on real tables only, not on values the query builds.
    ("SELECT v.label, count(*) AS people FROM (VALUES ('F', 'Women'), ('M', 'Men')) AS v(code, label)"
     " JOIN employees e ON e.gender = v.code GROUP BY v.label ORDER BY v.label"),
]


@pytest.mark.parametrize("sql", ACCEPTED, ids=[sql[:50] for sql in ACCEPTED])
def test_analytical_sql_is_accepted_and_the_rerendered_sql_gives_the_same_rows(sql):
    """We execute the re-rendered SQL, not the model's text, so re-rendering must not change it."""
    guarded = validate_sql(sql, CATALOG)
    expected = SESSION.conn.execute(sql).fetchall()
    assert SESSION.conn.execute(guarded.sql).fetchall() == expected


def test_aggregate_with_filter_reports_tables_columns_and_aggregates():
    q = validate_sql("SELECT department, avg(ctc) FROM employees WHERE location = 'Pune' GROUP BY 1", CATALOG)
    assert q.tables == ["employees"]
    assert set(q.columns) == {("employees", "department"), ("employees", "ctc"), ("employees", "location")}
    assert q.aggregated == [("avg", "employees", "ctc")]
    assert q.joins == []


def test_join_resolves_aliases_to_real_tables():
    q = validate_sql(
        "SELECT e.department, sum(s.gross) FROM employees e JOIN salary_register s"
        " ON e.emp_id = s.emp_code GROUP BY 1", CATALOG)
    assert q.tables == ["employees", "salary_register"]
    assert q.joins == [JoinRef("employees", "emp_id", "salary_register", "emp_code")]
    assert q.aggregated == [("sum", "salary_register", "gross")]


def test_join_keys_are_found_through_casts_using_and_where():
    cast = validate_sql("SELECT count(*) FROM employees e JOIN salary_register s"
                        " ON trim(e.emp_id) = CAST(s.emp_code AS VARCHAR)", CATALOG)
    using = validate_sql("SELECT a.emp_id FROM attendance_q1 a JOIN employees e USING (emp_id)", CATALOG)
    implicit = validate_sql("SELECT e.name FROM employees e, salary_register s WHERE e.emp_id = s.emp_code", CATALOG)
    assert cast.joins == [JoinRef("employees", "emp_id", "salary_register", "emp_code")]
    assert using.joins == [JoinRef("attendance_q1", "emp_id", "employees", "emp_id")]
    assert implicit.joins == [JoinRef("employees", "emp_id", "salary_register", "emp_code")]


def test_cte_is_not_a_real_table_and_a_join_to_it_is_not_reported():
    q = validate_sql(
        "WITH pay AS (SELECT emp_code, sum(gross) AS g FROM salary_register GROUP BY 1)"
        " SELECT sum(e.ctc), sum(pay.g) FROM employees e JOIN pay ON pay.emp_code = e.emp_id", CATALOG)
    assert q.tables == ["salary_register", "employees"]
    assert q.joins == []
    assert set(q.aggregated) == {("sum", "salary_register", "gross"), ("sum", "employees", "ctc")}


def test_exists_subquery_is_not_a_join_because_it_cannot_multiply_rows():
    q = validate_sql("SELECT sum(e.ctc) FROM employees e WHERE EXISTS"
                     " (SELECT 1 FROM salary_register s WHERE s.emp_code = e.emp_id)", CATALOG)
    assert q.joins == []
    assert ("salary_register", "emp_code") in q.columns


def test_count_star_distinct_and_expressions_inside_aggregates():
    q = validate_sql("SELECT count(*), count(DISTINCT e.emp_id), sum(e.ctc / 12), max(e.exit_date)"
                     " FROM employees e", CATALOG)
    # DISTINCT aggregates are left out on purpose: repeated rows cannot change them.
    assert q.aggregated == [("count", "*", "*"), ("sum", "employees", "ctc"), ("max", "employees", "exit_date")]


def test_generate_series_is_allowed_and_is_not_a_table():
    q = validate_sql("SELECT t.m FROM generate_series(1, 3) AS t(m)", CATALOG)
    assert q.tables == [] and q.columns == []


def test_star_counts_as_touching_every_column_so_pii_handling_sees_it():
    plain = validate_sql("SELECT * FROM employees", CATALOG)
    excluded = validate_sql("SELECT * EXCLUDE (email) FROM employees", CATALOG)
    with_function_source = validate_sql("SELECT * FROM employees, generate_series(1, 2)", CATALOG)
    assert ("employees", "name") in plain.columns and ("employees", "email") in plain.columns
    assert ("employees", "name") in excluded.columns and ("employees", "email") not in excluded.columns
    assert ("employees", "email") in with_function_source.columns
    assert "EXCLUDE" in excluded.sql  # the executed SQL stays what the model wrote


def test_pii_column_is_recorded_even_where_sqlglot_cannot_qualify_it():
    beside_function = validate_sql("SELECT name FROM employees, generate_series(1, 2)", CATALOG)
    correlated = validate_sql("SELECT (SELECT max(name) FROM generate_series(1, 1)) FROM employees", CATALOG)
    through_cte = validate_sql("WITH people AS (SELECT name AS who FROM employees) SELECT who FROM people", CATALOG)
    for query in (beside_function, correlated, through_cte):
        assert ("employees", "name") in query.columns


@pytest.mark.parametrize("sql", [
    "SELECT name AS department FROM employees",
    "SELECT department: name FROM employees",
    "SELECT * REPLACE (name AS department) FROM employees",
    "WITH t(department) AS (SELECT name FROM employees) SELECT department FROM t",
    "SELECT department FROM employees UNION ALL SELECT name FROM employees",
    "SELECT unnest({'department': name}) FROM employees",
])
def test_a_pii_column_renamed_to_look_harmless_is_still_reported(sql):
    """Every one of these returns names under the header `department`. The guard cannot tell
    an honest rename from a dishonest one, so its job is to keep saying employees.name was
    read. Whoever hides PII from the narration model must go by this list, not by the header."""
    assert ("employees", "name") in validate_sql(sql, CATALOG).columns


def test_names_are_matched_case_insensitively_and_reported_as_the_catalog_spells_them():
    q = validate_sql('SELECT E.Department FROM Employees AS E WHERE "Location" = \'Pune\'', CATALOG)
    assert q.tables == ["employees"]
    assert set(q.columns) == {("employees", "department"), ("employees", "location")}


def test_comments_are_dropped_from_the_sql_we_execute():
    q = validate_sql("SELECT count(*) FROM employees -- ; DROP TABLE employees", CATALOG)
    assert "DROP" not in q.sql.upper()


def test_a_refused_statement_is_not_copied_into_the_server_log(caplog):
    """sqlglot warns with the full statement, literals included, when it only half understands one."""
    with pytest.raises(GuardError):
        validate_sql("PREPARE p AS SELECT * FROM employees WHERE name = 'Asha Rao'", CATALOG)
    assert "Asha Rao" not in caplog.text


def test_unknown_table_suggests_the_closest_real_one():
    with pytest.raises(GuardError) as caught:
        validate_sql("SELECT * FROM employee", CATALOG)
    assert caught.value.code == "unknown_table"
    assert caught.value.suggestion == "Did you mean employees?"


def test_unknown_column_suggests_the_closest_real_one():
    catalog = CATALOG.model_copy(deep=True)
    catalog.tables[0].columns.append(ColumnProfile(name="exit_reason", label="Exit Reason", type="text"))
    for sql in ("SELECT attrition_reason FROM employees", "SELECT e.attrition_reason FROM employees e"):
        with pytest.raises(GuardError) as caught:
            validate_sql(sql, catalog)
        assert caught.value.code == "unknown_column"
        assert "attrition_reason" in caught.value.message
        assert caught.value.suggestion == "Did you mean employees.exit_reason?"


def test_unknown_column_prefers_a_suggestion_from_the_tables_in_the_query():
    with pytest.raises(GuardError) as caught:
        validate_sql("SELECT s.emp_id FROM salary_register s", CATALOG)
    assert caught.value.suggestion == "Did you mean salary_register.emp_code?"


def test_column_with_no_close_match_has_no_suggestion():
    with pytest.raises(GuardError) as caught:
        validate_sql("SELECT zzzz FROM employees", CATALOG)
    assert caught.value.suggestion is None


def test_column_present_in_two_joined_tables_must_say_which_one():
    with pytest.raises(GuardError) as caught:
        validate_sql("SELECT emp_id FROM employees e JOIN attendance_q1 a ON e.emp_id = a.emp_id", CATALOG)
    assert caught.value.code == "unknown_column"
    assert "employees" in caught.value.message and "attendance_q1" in caught.value.message


def test_select_aliases_are_not_mistaken_for_columns():
    q = validate_sql("SELECT department, sum(ctc) AS total FROM employees GROUP BY department"
                     " HAVING total > 10 ORDER BY total DESC", CATALOG)
    assert q.aggregated == [("sum", "employees", "ctc")]
