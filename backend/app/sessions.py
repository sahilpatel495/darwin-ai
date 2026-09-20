"""In-memory sessions, each with its own locked-down DuckDB connection.

Invariant: model-written SQL only ever runs on a connection that was locked down at
creation (no file, network or extension access; configuration frozen) and only after
passing app.query.guard. DuckDB still permits CREATE/INSERT after lock-down, which is why
the parser guard is mandatory and this is defence in depth, not the only control.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import duckdb
import pandas as pd

from app.catalog.glossary import DEFAULT_GLOSSARY
from app.catalog.relationships import detect_relationships
from app.catalog.suggest import suggest_questions
from app.catalog.unions import create_union_views, detect_unions, quote
from app.config import settings
from app.contracts import Answer, Catalog, ColumnType, Metric, Relationship, TableProfile, UnionView
from app.ingest import IngestError, ingest_file
from app.profile import profile_table

# The prompt has a budget of about 2K tokens and link detection compares every pair of
# tables, so a workbook with hundreds of sheets is refused rather than half-handled.
MAX_TABLES_PER_SESSION = 30
MAX_TEMP_DIRECTORY_SIZE = "1GB"  # what one session may spill to disk when a query outgrows memory
_STAGING = "_staging"

# Explicit casts, so a column's DuckDB type never depends on what pandas happened to infer
# (an all-empty column, say) and identifier columns are always VARCHAR on both sides of a join.
_DUCKDB_TYPES: dict[ColumnType, str] = {
    "integer": "BIGINT", "decimal": "DOUBLE", "currency": "DOUBLE", "percent": "DOUBLE",
    "date": "DATE", "boolean": "BOOLEAN", "text": "VARCHAR",
}

# The glossary is typed by the user and its text is sent to a model on every matching
# question, so its size is bounded here, at the trust boundary.
_GLOSSARY_LIMITS = {"key": 60, "name": 80, "definition": 1000, "sql_pattern": 4000}
_MAX_SYNONYMS, _MAX_SYNONYM_CHARS = 20, 80


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
    temp_dir.mkdir(parents=True, exist_ok=True)

    def text(value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    conn = duckdb.connect(":memory:")
    for statement in (
        f"SET threads = {int(threads)}",
        f"SET memory_limit = {text(memory_limit)}",
        f"SET temp_directory = {text(temp_dir)}",
        f"SET max_temp_directory_size = {text(MAX_TEMP_DIRECTORY_SIZE)}",
        "SET autoinstall_known_extensions = false",
        "SET autoload_known_extensions = false",
        "SET allow_community_extensions = false",
        "SET enable_external_access = false",  # no files, no URLs, no ATTACH, no COPY
        "SET lock_configuration = true",  # and none of the above can be switched back on
    ):
        conn.execute(statement)
    return conn


@contextmanager
def _transaction(conn: duckdb.DuckDBPyConnection) -> Iterator[None]:
    """DuckDB's DDL is transactional, so a failure half-way through loading tables or rebuilding
    views leaves the database exactly as it was, matching the catalog we did not replace.
    Questions running on other cursors keep seeing the old state until the commit."""
    conn.execute("BEGIN")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _fingerprint(uploads: list[tuple[str, str]]) -> str:
    """sha256 over every upload's name and content hash, sorted by name, so the same files
    give the same fingerprint in any session and in any upload order. Content hashes are
    kept because the raw files are deleted as soon as they are loaded."""
    digest = hashlib.sha256()
    for name, content_hash in sorted(uploads):
        digest.update(f"{name}\0{content_hash}\n".encode())
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _check_glossary(metrics: list[Metric]) -> None:
    keys = [m.key for m in metrics]
    if len(set(keys)) != len(keys):
        raise ValueError("Two glossary entries share the same key. A key can be used more than once only by mistake; rename one.")
    for metric in metrics:
        if not metric.key.strip() or not metric.name.strip():
            raise ValueError("Every glossary entry needs a name. Give the unnamed entry a name or remove it.")
        for field_name, limit in _GLOSSARY_LIMITS.items():
            if len(getattr(metric, field_name)) > limit:
                raise ValueError(f'The {field_name.replace("_", " ")} of "{metric.name[:40]}" is longer than '
                                 f"{limit} characters. Shorten it and save again.")
        if len(metric.synonyms) > _MAX_SYNONYMS or any(len(s) > _MAX_SYNONYM_CHARS for s in metric.synonyms):
            raise ValueError(f'"{metric.name[:40]}" can have at most {_MAX_SYNONYMS} synonyms of up to '
                             f"{_MAX_SYNONYM_CHARS} characters each. Remove or shorten some and save again.")


@dataclass
class Session:
    id: str
    conn: duckdb.DuckDBPyConnection
    catalog: Catalog
    history: list[Turn] = field(default_factory=list)
    answer_cache: dict[str, Answer] = field(default_factory=dict)
    created_at: float = 0.0
    last_used: float = 0.0
    work_dir: Path | None = None  # everything this session wrote to disk; removed on close
    uploads: list[tuple[str, str]] = field(default_factory=list)  # (original file name, sha256)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def cursor(self) -> duckdb.DuckDBPyConnection:
        return self.conn.cursor()

    def add_files(self, files: list[tuple[Path, str]]) -> Catalog:
        """files = [(path on disk, original filename)]. Ingest -> profile -> load into DuckDB
        (register + CREATE TABLE AS, dates cast to DATE) -> relationships -> unions ->
        suggested questions. Bumps catalog.version, recomputes fingerprint, clears
        answer_cache. A file that fails to ingest raises IngestError naming the file.

        All or nothing: every file is read and profiled before anything is loaded, so one bad
        file leaves the session exactly as it was. A file with the same name and the same
        bytes as an earlier upload is skipped (the same file dropped twice). The same name
        with different bytes is a corrected copy and replaces the earlier one: keeping both
        would stack them in a union view and count every employee twice.
        """
        with self._lock:
            staged, uploads = self._stage(files)
            if not staged:
                return self.catalog
            replaced = {name for name, _ in uploads} & {name for name, _ in self.uploads}
            current = [t for t in self.catalog.tables if not t.is_view]
            base = [t for t in current if t.source_file not in replaced] + [profile for _, profile in staged]
            with _transaction(self.conn):
                for table in current:
                    if table.source_file in replaced:
                        self.conn.execute(f"DROP TABLE {quote(table.name)}")
                for df, profile in staged:
                    self._load(df, profile)
                catalog = self._rebuild(base, self.catalog.relationships, self.catalog.unions)
            self.uploads = [u for u in self.uploads if u[0] not in replaced] + uploads
            catalog.fingerprint = _fingerprint(self.uploads)
            catalog.suggested_questions = suggest_questions(catalog)
            self.history.clear()  # earlier turns were about a different set of tables
            return self._publish(catalog)

    def _stage(self, files: list[tuple[Path, str]]) -> tuple[list[tuple[pd.DataFrame, TableProfile]], list[tuple[str, str]]]:
        """Read and profile every new file without touching the session."""
        taken = {t.name for t in self.catalog.tables} | {_STAGING}
        seen = set(self.uploads)
        earlier_names = {name for name, _ in self.uploads}
        staged: list[tuple[pd.DataFrame, TableProfile]] = []
        uploads: list[tuple[str, str]] = []
        for path, original_name in files:
            upload = (original_name, _sha256(path))
            if upload in seen:
                continue
            seen.add(upload)
            is_replacement = original_name in earlier_names
            if is_replacement:  # the new copy takes over the table names of the one it replaces
                taken -= {t.name for t in self.catalog.tables if not t.is_view and t.source_file == original_name}
            try:
                tables = ingest_file(path, original_name, taken)
            except IngestError as e:
                message = str(e) if original_name in str(e) else f"{original_name}: {e}"
                raise IngestError(message) from e
            except Exception as e:  # a reader crashed; the user gets a sentence, the log gets the trace
                raise IngestError(
                    f"{original_name} could not be read. It may be damaged or password-protected. "
                    "Open it in Excel, save a fresh copy as .xlsx or .csv, and upload that.") from e
            for table in tables:
                taken.add(table.table_name)
                df, profile = profile_table(table)
                if is_replacement:
                    profile.health.warnings = [*profile.health.warnings, (
                        f"This replaced the {original_name} you uploaded earlier. To keep both versions, "
                        "rename one of the files and upload it again.")]
                staged.append((df, profile))
            uploads.append(upload)

        replaced = earlier_names & {name for name, _ in uploads}
        total = sum(not t.is_view and t.source_file not in replaced for t in self.catalog.tables) + len(staged)
        if total > MAX_TABLES_PER_SESSION:
            raise IngestError(f"That would make {total} tables in this session and the limit is "
                              f"{MAX_TABLES_PER_SESSION}. Upload fewer files or sheets, or start a new session.")
        return staged, uploads

    def _load(self, df: pd.DataFrame, profile: TableProfile) -> None:
        """Copy a cleaned frame into DuckDB. The frame is only registered for the length of
        one statement, so model-written SQL can never reach a pandas object."""
        columns = ", ".join(f"CAST({quote(c.name)} AS {_DUCKDB_TYPES[c.type]}) AS {quote(c.name)}"
                            for c in profile.columns)
        self.conn.register(_STAGING, df)
        try:
            self.conn.execute(f"CREATE OR REPLACE TABLE {quote(profile.name)} AS SELECT {columns} FROM {_STAGING}")
        finally:
            self.conn.unregister(_STAGING)

    def _rebuild(self, base: list[TableProfile], relationships: list[Relationship],
                 unions: list[UnionView]) -> Catalog:
        """The next catalog for these base tables: links re-detected (user decisions kept),
        union views recreated in DuckDB and profiled. Call inside a transaction."""
        relationships = detect_relationships(self.conn, base, relationships)
        # A group is renamed when a file joins it (sales_jan_all becomes sales_all). Its old view
        # would otherwise linger outside the catalog and block a later table of the same name.
        for union in self.catalog.unions:
            self.conn.execute(f"DROP VIEW IF EXISTS {quote(union.view_name)}")
        unions = detect_unions(base, unions)
        views = create_union_views(self.conn, unions, base)
        return self.catalog.model_copy(update={
            "tables": base + views, "relationships": relationships, "unions": unions,
            "version": self.catalog.version + 1})

    def _publish(self, catalog: Catalog) -> Catalog:
        """Swap the catalog in one assignment, so a question being answered on another thread
        never sees half of an update, and drop answers computed against the old one."""
        self.catalog = catalog
        self.answer_cache.clear()
        return catalog

    def load_sample(self) -> Catalog:
        """add_files over every data file in settings.demo_data_dir."""
        folder = settings.demo_data_dir
        files = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in (".csv", ".xlsx")
                       and not p.name.startswith(("~$", "."))) if folder.is_dir() else []
        if not files:
            raise IngestError("The sample data is not installed on this server. Upload your own CSV or Excel files instead.")
        with self._lock:
            self.add_files([(path, path.name) for path in files])
            starters = _read_starters(folder / "starters.json")
            if starters:  # curated for the demo data; better than anything a template can write
                self.catalog = self.catalog.model_copy(update={"suggested_questions": starters})
            return self.catalog

    def set_link_status(self, link_id: str, status: str) -> Catalog:
        """Confirm or reject a relationship or union by id; recreate union views; bump version."""
        if status not in ("active", "rejected"):
            raise ValueError('A link can only be set to "active" or "rejected".')
        with self._lock:
            catalog = self.catalog
            if link_id not in {link.id for link in (*catalog.relationships, *catalog.unions)}:
                raise KeyError(link_id)
            relationships = [r.model_copy(update={"status": status}) if r.id == link_id else r for r in catalog.relationships]
            unions = [u.model_copy(update={"status": status}) if u.id == link_id else u for u in catalog.unions]
            with _transaction(self.conn):
                updated = self._rebuild([t for t in catalog.tables if not t.is_view], relationships, unions)
            return self._publish(updated)

    def set_glossary(self, metrics: list[Metric]) -> Catalog:
        """Replace the session's glossary. Raises ValueError, with a sentence for the user,
        when an entry is unnamed, duplicated or large enough to flood a prompt."""
        _check_glossary(metrics)
        with self._lock:
            return self._publish(self.catalog.model_copy(update={
                "glossary": [m.model_copy(deep=True) for m in metrics], "version": self.catalog.version + 1}))

    def close(self) -> None:
        """Free the database and delete whatever the session left on disk."""
        try:
            self.conn.close()
        finally:
            if self.work_dir is not None:
                shutil.rmtree(self.work_dir, ignore_errors=True)


def _read_starters(path: Path) -> list[str]:
    """demo_data/starters.json is a JSON list of questions. Anything else is ignored: a broken
    starters file must not stop the sample data from loading."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [q for q in loaded if isinstance(q, str) and q.strip()] if isinstance(loaded, list) else []


class SessionStore:
    """LRU + TTL store. ponytail: process memory, single worker; move to Redis + persisted
    DuckDB files if this ever needs more than one process."""

    def __init__(self, max_sessions: int | None = None, ttl_s: float | None = None) -> None:
        self._max = settings.max_sessions if max_sessions is None else max_sessions
        self._ttl = settings.session_ttl_s if ttl_s is None else ttl_s
        self._sessions: OrderedDict[str, Session] = OrderedDict()  # least recently used first
        self._lock = threading.Lock()  # routes run on a thread pool

    def create(self) -> Session:
        # The id is the only credential a session has (it travels in the URL), so it comes
        # from the OS random source. It is also a folder name, hence hex.
        session_id = secrets.token_hex(16)
        folder = settings.work_dir / session_id
        conn = new_locked_connection(settings.duckdb_memory_limit, settings.duckdb_threads, folder / "duckdb_tmp")
        now = time.time()
        session = Session(
            id=session_id, conn=conn, created_at=now, last_used=now, work_dir=folder,
            catalog=Catalog(session_id=session_id, version=0, fingerprint="",
                            glossary=[m.model_copy(deep=True) for m in DEFAULT_GLOSSARY]))
        with self._lock:
            for stale in [s for s in self._sessions.values() if now - s.last_used > self._ttl]:
                self._drop(stale.id)
            self._sessions[session_id] = session
            while len(self._sessions) > self._max:
                self._drop(next(iter(self._sessions)))
        return session

    def get(self, session_id: str) -> Session:
        """Raises KeyError for unknown or expired sessions."""
        now = time.time()
        with self._lock:
            session = self._sessions[session_id]
            if now - session.last_used > self._ttl:
                self._drop(session_id)
                raise KeyError(session_id)
            session.last_used = now
            self._sessions.move_to_end(session_id)
            return session

    def delete(self, session_id: str) -> None:
        """The user asked for their data to be gone. Unknown ids are not an error."""
        with self._lock:
            if session_id in self._sessions:
                self._drop(session_id)

    def _drop(self, session_id: str) -> None:
        self._sessions.pop(session_id).close()
