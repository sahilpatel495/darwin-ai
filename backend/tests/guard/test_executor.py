"""A runaway or broken query must never take the session down with it."""

import pytest

from app.query.executor import QueryError, QueryTimeout, execute
from tests.fixtures import make_session


def test_runaway_query_times_out_and_the_connection_still_works():
    cursor = make_session().cursor()
    with pytest.raises(QueryTimeout) as caught:
        execute(cursor, "SELECT count(*) FROM range(100000000) a, range(100000) b", timeout_s=0.5)
    assert "0.5 seconds" in str(caught.value)
    assert execute(cursor, "SELECT 1").rows == [(1,)]


def test_row_cap_truncates_and_says_so():
    result = execute(make_session().cursor(), "SELECT * FROM range(10)", row_cap=5)
    assert len(result.rows) == 5
    assert result.truncated is True


def test_result_that_exactly_fits_the_cap_is_not_marked_truncated():
    result = execute(make_session().cursor(), "SELECT * FROM range(5)", row_cap=5)
    assert len(result.rows) == 5
    assert result.truncated is False


def test_bad_sql_raises_query_error_with_duckdbs_message():
    with pytest.raises(QueryError) as caught:
        execute(make_session().cursor(), "SELECT no_such_column FROM employees")
    assert "no_such_column" in str(caught.value)


def test_columns_and_duck_types_come_from_the_cursor_description():
    result = execute(
        make_session().cursor(),
        "SELECT department, count(*) AS people, avg(ctc) AS avg_ctc, min(date_of_joining) AS first_join"
        " FROM employees GROUP BY department ORDER BY department",
    )
    assert result.columns == ["department", "people", "avg_ctc", "first_join"]
    assert result.duck_types == ["VARCHAR", "BIGINT", "DOUBLE", "DATE"]
    assert result.rows[0][:2] == ("Engineering", 3)
    assert result.elapsed_ms >= 0
