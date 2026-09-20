"""Security review, executor: allowed SQL must cost bounded time and memory, the session must
work afterwards, and nothing the executor says may name a setting an attacker could use."""

import duckdb
import pytest

from app.query.executor import QueryError, QueryTimeout, execute
from tests.fixtures import make_session

RUNAWAYS = [
    "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT count(*) FROM r",
    "SELECT sum(x) FROM generate_series(1, 100000000000000) AS t(x)",
    "SELECT count(*) FROM employees a, employees b, generate_series(1, 100000000000) AS g(i)",
]


@pytest.mark.parametrize("sql", RUNAWAYS)
def test_allowed_but_endless_queries_time_out_and_leave_the_session_usable(sql):
    session = make_session()
    with pytest.raises(QueryTimeout):
        execute(session.cursor(), sql, timeout_s=0.3)
    assert execute(session.cursor(), "SELECT count(*) FROM employees").rows == [(8,)]


@pytest.mark.parametrize("sql", [
    "SELECT list(e.name) AS names FROM employees e",
    "SELECT struct_pack(n := e.name) AS person FROM employees e",
    "SELECT histogram(e.department) AS spread FROM employees e",
])
def test_nested_columns_are_refused_before_a_row_is_copied_into_python(sql):
    cursor = make_session().cursor()
    with pytest.raises(QueryError, match="string_agg"):
        execute(cursor, sql)
    assert cursor.fetchone() is not None  # the rows were still waiting inside DuckDB


def test_a_result_with_too_much_text_is_refused_part_way_through_the_fetch():
    session = make_session()
    wide = "SELECT e.name || repeat('x', 1000) AS wide FROM employees e, generate_series(1, 500) AS g(i)"
    with pytest.raises(QueryError, match="characters of text"):
        execute(session.cursor(), wide, max_chars=100_000)
    assert len(execute(session.cursor(), wide, max_chars=10_000_000).rows) == 4000
    assert execute(session.cursor(), "SELECT count(*) FROM employees").rows == [(8,)]


def test_the_row_cap_still_holds_when_rows_arrive_in_batches():
    result = execute(make_session().cursor(), "SELECT * FROM generate_series(1, 2000) AS t(x)", row_cap=1234)
    assert [row[0] for row in result.rows] == list(range(1, 1235))
    assert result.truncated is True


def test_running_out_of_memory_is_a_sentence_that_names_no_setting():
    conn = duckdb.connect(":memory:")
    conn.execute("SET memory_limit = '40MB'")
    with pytest.raises(QueryError) as caught:
        execute(conn.cursor(), "SELECT max(s) FROM (SELECT string_agg(CAST(range AS VARCHAR), ',') AS s FROM range(8000000))")
    message = str(caught.value)
    assert "more memory" in message and "memory_limit" not in message and "PRAGMA" not in message
    assert execute(conn.cursor(), "SELECT 1").rows == [(1,)]
