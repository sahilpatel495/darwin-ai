"""In-memory sessions, each with its own locked-down DuckDB connection.

Invariant: model-written SQL only ever runs on a connection that was locked down at
creation (no file, network or extension access; configuration frozen) and only after
passing app.query.guard. DuckDB still permits CREATE/INSERT after lock-down, which is why
the parser guard is mandatory and this is defence in depth, not the only control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import duckdb

from app.contracts import Answer, Catalog, Metric


@dataclass
class Turn:
    """Conversation memory for follow-ups. Never holds result rows."""

    question: str
    interpretation: str
    sql: str


class SessionLike(Protocol):
    """What the query pipeline needs from a session (tests use a lightweight fake)."""

    id: str
    catalog: Catalog
    history: list[Turn]
    answer_cache: dict[str, Answer]

    def cursor(self) -> duckdb.DuckDBPyConnection: ...


def new_locked_connection(memory_limit: str, threads: int, temp_dir: Path) -> duckdb.DuckDBPyConnection:
    """Open :memory: and lock it down. Order matters and both locks are one-way:
    threads, memory_limit, temp_directory, max_temp_directory_size ->
    autoinstall_known_extensions/autoload_known_extensions/allow_community_extensions = false ->
    enable_external_access=false -> lock_configuration=true.
    Verified on DuckDB 1.5.5: con.register(df) still works afterwards."""
    raise NotImplementedError


@dataclass
class Session:
    id: str
    conn: duckdb.DuckDBPyConnection
    catalog: Catalog
    history: list[Turn] = field(default_factory=list)
    answer_cache: dict[str, Answer] = field(default_factory=dict)
    created_at: float = 0.0
    last_used: float = 0.0

    def cursor(self) -> duckdb.DuckDBPyConnection:
        return self.conn.cursor()

    def add_files(self, files: list[tuple[Path, str]]) -> Catalog:
        """files = [(path on disk, original filename)]. Ingest -> profile -> load into DuckDB
        (register + CREATE TABLE AS, dates cast to DATE) -> relationships -> unions ->
        suggested questions. Bumps catalog.version, recomputes fingerprint, clears
        answer_cache. A file that fails to ingest raises IngestError naming the file."""
        raise NotImplementedError

    def load_sample(self) -> Catalog:
        """add_files over every data file in settings.demo_data_dir."""
        raise NotImplementedError

    def set_link_status(self, link_id: str, status: str) -> Catalog:
        """Confirm or reject a relationship or union by id; recreate union views; bump version."""
        raise NotImplementedError

    def set_glossary(self, metrics: list[Metric]) -> Catalog:
        raise NotImplementedError


class SessionStore:
    """LRU + TTL store. ponytail: process memory, single worker; move to Redis + persisted
    DuckDB files if this ever needs more than one process."""

    def create(self) -> Session:
        raise NotImplementedError

    def get(self, session_id: str) -> Session:
        """Raises KeyError for unknown or expired sessions."""
        raise NotImplementedError
