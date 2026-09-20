"""Run guarded SQL with a timeout, a row cap and a size cap.

Why all three: the SQL is written by a model. A cross join over two large files would hold
the only worker for minutes, and an unbounded result would be pulled into memory and then into
the browser. Rows alone do not bound a result: one cell can hold 400 MB of text, and DuckDB's
memory_limit stops counting once a value is copied into Python. This module does not check
the SQL itself: only ever pass `GuardedQuery.sql`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

import duckdb


class QueryTimeout(RuntimeError): ...


class QueryError(RuntimeError): ...


# A result is copied three times on its way out (Python rows, the JSON answer, the event
# stream), so its text is budgeted. 10 million characters is 5,000 rows of 40 columns of 50
# characters: more than the table view shows, far less than the server's memory.
MAX_RESULT_CHARS = 10_000_000
_FETCH_ROWS = 500  # rows copied into Python between two looks at the budget
# A list of 12 million integers is 96 MB inside DuckDB and took this process to 2 GB once it
# was copied into Python objects (measured), and nothing in the UI draws a list. One row per
# item, or string_agg, says the same thing.
_NESTED_TYPES = {"list", "array", "struct", "map", "union"}


@dataclass
class ExecResult:
    columns: list[str]
    duck_types: list[str]  # DuckDB type names per column, e.g. "DOUBLE", "DATE", "VARCHAR"
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0


def execute(
    cursor: duckdb.DuckDBPyConnection, sql: str, *, timeout_s: float = 10, row_cap: int = 5000,
    max_chars: int = MAX_RESULT_CHARS,
) -> ExecResult:
    """Run one query on its own cursor, stopping it after `timeout_s` seconds.

    DuckDB has no statement timeout, so a timer thread calls `cursor.interrupt()`, which makes
    the running query raise. Interrupting is safe for the session: the same connection runs
    the next query normally, and a timer that fires just after the query finished is a no-op.
    The timer covers the fetch as well, because DuckDB does part of the work lazily there.

    We fetch `row_cap + 1` rows: the extra row is never returned, it only tells us whether
    more rows existed, so the UI can say "showing the first N rows" instead of guessing.

    Rows are fetched a few hundred at a time so the text budget (`max_chars`) is checked before
    much has been copied. Nested columns are refused from the result's description, before a
    single row is copied. Neither limit can stop DuckDB building one huge value in the first
    place; the guard refuses the functions that do that in one call.

    Raises QueryTimeout (a sentence for the user) or QueryError (DuckDB's own message, for the
    repair step). That message can quote a cell value ("Could not convert string 'Asha Rao'
    to INT32"), so it must never be pasted into a prompt as it is: generator._safe_problem
    strips it on the way to the model. The sentences written here quote nothing.
    """
    timer = threading.Timer(timeout_s, cursor.interrupt)
    started = time.perf_counter()
    timer.start()
    try:
        cursor.execute(sql)
        description = cursor.description or []
        _refuse_nested_columns(description)
        rows: list[tuple[Any, ...]] = []
        chars = 0
        while len(rows) <= row_cap:
            batch = cursor.fetchmany(min(_FETCH_ROWS, row_cap + 1 - len(rows)))
            if not batch:
                break
            chars += sum(len(c) for row in batch for c in row if isinstance(c, (str, bytes)))
            if chars > max_chars:
                raise QueryError(
                    f"The result holds more than {max_chars:,} characters of text, which is too"
                    " much to show. Select fewer or shorter columns, or summarise with GROUP BY."
                )
            rows += batch
    except duckdb.InterruptException as exc:
        raise QueryTimeout(
            f"The query took longer than {timeout_s:g} seconds, so it was stopped."
            " Try narrowing the question, for example to one year or one department."
        ) from exc
    except duckdb.OutOfMemoryException as exc:
        # DuckDB's text lists settings to raise (memory_limit, threads), which are locked here.
        raise QueryError(
            "The query needed more memory than one session is allowed. Filter or aggregate each"
            " table before joining it, and never join without a condition."
        ) from exc
    except duckdb.Error as exc:
        raise QueryError(str(exc)) from exc
    finally:
        timer.cancel()
    return ExecResult(
        columns=[column[0] for column in description],
        duck_types=[str(column[1]) for column in description],
        rows=rows[:row_cap],
        truncated=len(rows) > row_cap,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def _refuse_nested_columns(description: list[tuple[Any, ...]]) -> None:
    nested = [column[0] for column in description if column[1].id in _NESTED_TYPES]
    if nested:
        raise QueryError(
            f"The column {nested[0]} holds a list or a struct in every row, which cannot be shown"
            " or charted. Return one row per item (GROUP BY), or join the items into text with"
            " string_agg."
        )
