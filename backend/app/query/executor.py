"""Run guarded SQL with a timeout and a row cap.

Why both limits: the SQL is written by a model. A cross join over two large files would hold
the only worker for minutes, and an unbounded result would be pulled into memory and then into
the browser. This module does not check the SQL itself: only ever pass `GuardedQuery.sql`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

import duckdb


class QueryTimeout(RuntimeError): ...


class QueryError(RuntimeError): ...


@dataclass
class ExecResult:
    columns: list[str]
    duck_types: list[str]  # DuckDB type names per column, e.g. "DOUBLE", "DATE", "VARCHAR"
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0


def execute(
    cursor: duckdb.DuckDBPyConnection, sql: str, *, timeout_s: float = 10, row_cap: int = 5000
) -> ExecResult:
    """Run one query on its own cursor, stopping it after `timeout_s` seconds.

    DuckDB has no statement timeout, so a timer thread calls `cursor.interrupt()`, which makes
    the running query raise. Interrupting is safe for the session: the same connection runs
    the next query normally, and a timer that fires just after the query finished is a no-op.
    The timer covers the fetch as well, because DuckDB does part of the work lazily there.

    We fetch `row_cap + 1` rows: the extra row is never returned, it only tells us whether
    more rows existed, so the UI can say "showing the first N rows" instead of guessing.

    Raises QueryTimeout (a sentence for the user) or QueryError (DuckDB's own message, for the
    repair step). That message can quote a cell value ("Could not convert string 'Asha Rao'
    to INT32"), so it must never be pasted into a prompt as it is: generator._safe_problem
    strips it on the way to the model.
    """
    timer = threading.Timer(timeout_s, cursor.interrupt)
    started = time.perf_counter()
    timer.start()
    try:
        cursor.execute(sql)
        rows = cursor.fetchmany(row_cap + 1)
        description = cursor.description or []
    except duckdb.InterruptException as exc:
        raise QueryTimeout(
            f"The query took longer than {timeout_s:g} seconds, so it was stopped."
            " Try narrowing the question, for example to one year or one department."
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
