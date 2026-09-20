"""Security review, guard: SQL that parses as a SELECT and would still hurt.

Two families. SUMMARIZE in brackets returns personal data without naming a column, so the
narration model would have been sent real names. The rest are queries that take the server
down rather than the data out: DuckDB's memory_limit does not cover the text a function
builds, and its interrupt cannot stop one long function call.
"""

import pytest

from app.query.guard import MAX_BUILT_CHARS, MAX_SQL_CHARS, GuardError, validate_sql
from tests.fixtures import CANARY_NAME, make_session

SESSION = make_session()
CATALOG = SESSION.catalog

REFUSED = [
    # Statements that are not SELECT, hidden where only a SELECT was expected.
    ("SELECT * FROM (SUMMARIZE employees)", "not_select"),
    ("SELECT * FROM (SUMMARIZE SELECT e.name FROM employees e)", "not_select"),
    ("WITH s AS (SUMMARIZE employees) SELECT * FROM s", "not_select"),
    ("SELECT * FROM (DESCRIBE employees)", "not_select"),
    # One call that builds one enormous value.
    ("SELECT repeat('x', 4000000000) AS bomb", "function"),
    ("SELECT repeat(e.name, e.ctc) AS bomb FROM employees e", "function"),
    ("SELECT repeat('x', 1000 * 1000 * 1000) AS bomb", "function"),
    ("SELECT lpad('x', 300000000, 'y') AS bomb", "function"),
    ("SELECT rpad(e.name, 300000000, 'y') AS bomb FROM employees e", "function"),
    ("SELECT printf('%0300000000d', 1) AS bomb", "function"),
    ("SELECT format('{:>{}}', 'x', 300000000) AS bomb", "function"),
    ("SELECT range(30000000) AS bomb", "function"),
    ("SELECT generate_series(1, 30000000) AS bomb", "function"),
    ("SELECT unnest(range(30000000)) AS bomb", "function"),
    ("SELECT x FROM unnest(generate_series(1, 30000000)) AS t(x)", "function"),
    # Quadratic in the length of the text, and deaf to the timeout while it runs.
    ("SELECT levenshtein(e.name, f.name) FROM employees e, employees f", "function"),
    ("SELECT editdist3(e.name, f.name) FROM employees e, employees f", "function"),
    ("SELECT damerau_levenshtein(e.name, f.name) FROM employees e, employees f", "function"),
    # The guard's own parsing is work done before any timeout applies.
    ("SELECT 1 AS n " + "UNION ALL SELECT 1 " * (MAX_SQL_CHARS // 19), "parse"),
]

STILL_ALLOWED = [
    "SELECT lpad(CAST(month(e.date_of_joining) AS VARCHAR), 2, '0') AS mm FROM employees e",
    f"SELECT repeat('*', {MAX_BUILT_CHARS}) AS bar",
    "SELECT m.month FROM generate_series(DATE '2025-01-01', DATE '2025-12-01', INTERVAL 1 MONTH) AS m(month)",
    "SELECT e.emp_id, g.i FROM employees e, LATERAL generate_series(1, 3) AS g(i)",
    "SELECT jaro_winkler_similarity(e.name, f.name) AS alike FROM employees e, employees f",
    "SELECT v.x FROM (VALUES (1), (2)) AS v(x)",
    "WITH d AS (SELECT e.department FROM employees e) SELECT count(*) AS n FROM (SELECT * FROM d UNION ALL SELECT * FROM d) AS twice",
]


@pytest.mark.parametrize(("sql", "code"), REFUSED)
def test_harmful_selects_are_refused(sql, code):
    with pytest.raises(GuardError) as caught:
        validate_sql(sql, CATALOG)
    assert caught.value.code == code


@pytest.mark.parametrize("sql", STILL_ALLOWED)
def test_the_honest_uses_of_the_same_functions_still_pass(sql):
    SESSION.cursor().execute(validate_sql(sql, CATALOG).sql).fetchall()  # and DuckDB runs them


def test_why_summarize_matters_it_returns_names_without_naming_a_column():
    """What the refusal prevents. The pipeline hides the columns the guard reports; this query
    reported none and its result holds the planted name (max of the name column)."""
    rows = SESSION.cursor().execute("SELECT * FROM (SUMMARIZE employees)").fetchall()
    assert any(CANARY_NAME in map(str, row) for row in rows)
