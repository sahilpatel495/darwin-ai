"""The locked-down connection, Session.add_files end to end, and the LRU + TTL store."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import app.sessions as sessions_module
import duckdb
import pandas as pd
import pytest
from app.catalog.glossary import DEFAULT_GLOSSARY
from app.contracts import Answer, Metric
from app.ingest import IngestError
from app.sessions import SessionStore, Turn, new_locked_connection

from tests.data_engine.helpers import tiny_ingest

EMPLOYEES = (
    "emp_id,name,department,join_date,ctc\n"
    "E001,Asha Rao,Engineering,2019-04-01,2400000\n"
    "E002,Vikram Shah,Sales,2020-07-15,1800000\n"
    "E003,Meera Iyer,Sales,2018-01-10,\n"
)
PAYROLL = "emp_code,pay_date,gross\nE001,2025-01-31,200000\nE001,2025-02-28,200000\nE002,2025-01-31,150000\nE003,2025-01-31,125000\n"
ATTENDANCE_Q1 = "emp_id,days_absent\nE001,1\nE002,0\n"
ATTENDANCE_Q2 = "emp_id,days_absent\nE001,2\nE003,4\n"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A store whose work dir and demo data live under tmp_path, with the stand-in ingest."""
    monkeypatch.setattr(sessions_module, "settings", dataclasses.replace(
        sessions_module.settings, work_dir=tmp_path / "work", demo_data_dir=tmp_path / "demo"))
    monkeypatch.setattr(sessions_module, "ingest_file", tiny_ingest)
    return SessionStore()


def _write(folder: Path, **files: str) -> list[tuple[Path, str]]:
    """Mimic the API: bytes saved under a random name, the original name passed alongside."""
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, (name, body) in enumerate(files.items()):
        path = folder / f"upload{i}{Path(name).suffix}"
        path.write_text(body, encoding="utf-8")
        saved.append((path, name))
    return saved


# --------------------------------------------------------------------------
# new_locked_connection
# --------------------------------------------------------------------------


@pytest.fixture
def locked(tmp_path):
    conn = new_locked_connection("256MB", 2, tmp_path / "duck_tmp")
    yield conn
    conn.close()


@pytest.mark.parametrize("sql", [
    "SELECT * FROM read_csv('x.csv')",
    "SELECT * FROM 'x.csv'",
    "SET threads=8",
    "SET enable_external_access=true",
    "RESET lock_configuration",
    "COPY (SELECT 1) TO 'out.csv'",
    "ATTACH 'other.db'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "SELECT * FROM read_parquet('https://example.com/x.parquet')",  # refused before any request is made
    "SELECT * FROM read_csv('s3://bucket/x.csv')",
    "SELECT * FROM read_text('/etc/passwd')",
    "SELECT * FROM glob('/etc/*')",
    "EXPORT DATABASE 'dump'",
    "CREATE SECRET s (TYPE S3, KEY_ID 'a', SECRET 'b')",
])
def test_locked_connection_blocks_files_network_extensions_and_reconfiguration(locked, sql):
    with pytest.raises(duckdb.Error):
        locked.execute(sql)


def test_a_locked_connection_cannot_read_python_variables(locked):
    """DuckDB can normally query a DataFrame in the caller's scope by its variable name."""
    server_side = pd.DataFrame({"secret": ["hunter2"]})
    with pytest.raises(duckdb.Error):
        locked.execute("SELECT * FROM server_side")
    assert len(server_side) == 1


def test_a_cursor_of_a_locked_connection_is_locked_too(locked):
    with pytest.raises(duckdb.Error):
        locked.cursor().execute("SELECT * FROM read_csv('x.csv')")


def test_uploads_still_load_after_lock_down(locked):
    locked.register("_staging", pd.DataFrame({"a": [1, 2, 3]}))
    locked.execute('CREATE TABLE "t" AS SELECT * FROM _staging')
    locked.unregister("_staging")
    assert locked.execute("SELECT sum(a) FROM t").fetchone()[0] == 6


def test_settings_are_applied(locked, tmp_path):
    threads, limit, external = locked.execute(
        "SELECT current_setting('threads'), current_setting('memory_limit'), current_setting('enable_external_access')").fetchone()
    assert threads == 2 and limit == "244.1 MiB" and external is False  # DuckDB reports 256MB in MiB
    assert (tmp_path / "duck_tmp").is_dir()


# --------------------------------------------------------------------------
# Session.add_files
# --------------------------------------------------------------------------


def test_two_files_become_typed_tables_with_a_link(store, tmp_path):
    session = store.create()
    assert session.catalog.version == 0 and session.catalog.glossary == DEFAULT_GLOSSARY
    session.history.append(Turn("q", "i", "SELECT 1"))
    session.answer_cache["k"] = Answer(id="a", kind="meta", question="q", text="t")

    saved = _write(tmp_path / "up", **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL})
    catalog = session.add_files(saved)

    assert catalog is session.catalog and catalog.version == 1
    assert [t.name for t in catalog.tables] == ["employees", "payroll"]
    assert session.history == [] and session.answer_cache == {}

    described = dict(session.conn.execute("SELECT column_name, column_type FROM (DESCRIBE employees)").fetchall())
    assert described == {"emp_id": "VARCHAR", "name": "VARCHAR", "department": "VARCHAR",
                         "join_date": "DATE", "ctc": "DOUBLE"}
    assert session.cursor().execute(
        "SELECT sum(p.gross) FROM employees e JOIN payroll p ON e.emp_id = p.emp_code WHERE e.department = 'Sales'"
    ).fetchone()[0] == 275000
    assert session.conn.execute("SELECT count(*) FROM duckdb_views() WHERE view_name = '_staging'").fetchone()[0] == 0

    link = next(r for r in catalog.relationships if r.id == "employees.emp_id->payroll.emp_code")
    assert (link.cardinality, link.status, link.match_left) == ("1:N", "active", 1.0)
    assert "name" in catalog.tables[0].health.pii_columns
    assert 0 < len(catalog.suggested_questions) <= 6


def test_fingerprint_is_the_sha256_of_the_uploads_sorted_by_name(store, tmp_path):
    def expected(**files: str) -> str:
        outer = hashlib.sha256()
        for name in sorted(files):
            outer.update(name.encode() + b"\0" + hashlib.sha256(files[name].encode()).hexdigest().encode() + b"\n")
        return outer.hexdigest()

    one, two = store.create(), store.create()
    one.add_files(_write(tmp_path / "a", **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL}))
    two.add_files(_write(tmp_path / "b", **{"payroll.csv": PAYROLL}))
    two.add_files(_write(tmp_path / "c", **{"employees.csv": EMPLOYEES}))
    assert one.catalog.fingerprint == two.catalog.fingerprint == expected(**{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL})
    assert store.create().catalog.fingerprint != one.catalog.fingerprint


def test_a_bad_file_is_named_and_nothing_from_the_batch_is_loaded(store, tmp_path):
    session = store.create()
    saved = _write(tmp_path / "up", **{"employees.csv": EMPLOYEES, "broken.csv": "emp_id,ctc\n"})
    with pytest.raises(IngestError, match="broken.csv"):
        session.add_files(saved)
    assert session.catalog.version == 0 and session.catalog.tables == []
    assert session.conn.execute("SELECT count(*) FROM duckdb_tables()").fetchone()[0] == 0


def test_an_unexpected_reader_crash_becomes_a_sentence_not_a_stack_trace(store, tmp_path, monkeypatch):
    def explode(*_):
        raise RuntimeError("zipfile.BadZipFile: File is not a zip file")

    monkeypatch.setattr(sessions_module, "ingest_file", explode)
    with pytest.raises(IngestError) as caught:
        store.create().add_files(_write(tmp_path / "up", **{"report.xlsx": "not really excel"}))
    assert "report.xlsx could not be read" in str(caught.value) and "zipfile" not in str(caught.value)


def test_a_crash_while_loading_rolls_everything_back(store, tmp_path, monkeypatch):
    """All or nothing also covers our own bugs: no orphan tables, no dropped views, and the
    same files can simply be uploaded again."""
    session = store.create()
    session.add_files(_write(tmp_path / "a", **{"attendance_q1.csv": ATTENDANCE_Q1, "attendance_q2.csv": ATTENDANCE_Q2}))
    before = session.catalog

    real = sessions_module.create_union_views
    def crash_after_dropping_views(conn, unions, tables):
        conn.execute("DROP VIEW IF EXISTS attendance_all")
        raise RuntimeError("boom")
    monkeypatch.setattr(sessions_module, "create_union_views", crash_after_dropping_views)
    with pytest.raises(RuntimeError):
        session.add_files(_write(tmp_path / "b", **{"employees.csv": EMPLOYEES}))
    with pytest.raises(RuntimeError):
        session.set_link_status("attendance_all", "rejected")

    assert session.catalog is before and len(session.uploads) == 2
    tables = {r[0] for r in session.conn.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    assert tables == {"attendance_q1", "attendance_q2"}
    assert session.conn.execute("SELECT count(*) FROM attendance_all").fetchone()[0] == 4  # the view survived

    monkeypatch.setattr(sessions_module, "create_union_views", real)
    assert "employees" in {t.name for t in session.add_files(_write(tmp_path / "c", **{"employees.csv": EMPLOYEES})).tables}


def test_dropping_the_same_file_twice_changes_nothing(store, tmp_path):
    session = store.create()
    session.add_files(_write(tmp_path / "a", **{"employees.csv": EMPLOYEES}))
    again = session.add_files(_write(tmp_path / "b", **{"employees.csv": EMPLOYEES}))
    assert [t.name for t in again.tables] == ["employees"] and again.version == 1


CORRECTED_EMPLOYEES = EMPLOYEES + "E004,Rohan Das,HR,2021-09-01,1200000\n"


def test_a_corrected_copy_of_a_file_replaces_the_earlier_one(store, tmp_path):
    """Keeping both would stack them in employees_all and count everybody twice."""
    session = store.create()
    session.add_files(_write(tmp_path / "a", **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL}))
    session.set_link_status("employees.emp_id->payroll.emp_code", "rejected")
    catalog = session.add_files(_write(tmp_path / "b", **{"employees.csv": CORRECTED_EMPLOYEES}))

    assert [t.name for t in catalog.tables] == ["payroll", "employees"] and catalog.unions == []
    assert session.conn.execute("SELECT count(*) FROM employees").fetchone()[0] == 4
    employees = catalog.tables[1]
    assert employees.row_count == 4 and employees.health.warnings == [
        "This replaced the employees.csv you uploaded earlier. To keep both versions, rename one of the files and upload it again."]
    assert catalog.relationships[0].status == "rejected"  # the user's decision about this pair still stands

    fresh = store.create()
    fresh.add_files(_write(tmp_path / "c", **{"employees.csv": CORRECTED_EMPLOYEES, "payroll.csv": PAYROLL}))
    assert catalog.fingerprint == fresh.catalog.fingerprint  # same files, however they got here


def test_a_replacement_that_fails_leaves_the_earlier_file_in_place(store, tmp_path):
    session = store.create()
    session.add_files(_write(tmp_path / "a", **{"employees.csv": EMPLOYEES}))
    with pytest.raises(IngestError):
        session.add_files(_write(tmp_path / "b", **{"employees.csv": CORRECTED_EMPLOYEES, "broken.csv": "emp_id,ctc\n"}))
    assert session.conn.execute("SELECT count(*) FROM employees").fetchone()[0] == 3
    assert session.catalog.version == 1 and len(session.uploads) == 1


def test_two_files_with_the_same_name_in_one_upload_are_both_kept(store, tmp_path):
    """Picked together (Q1/attendance.csv and Q2/attendance.csv), they are two files, not two versions."""
    session = store.create()
    first, second = _write(tmp_path / "q1", **{"attendance.csv": ATTENDANCE_Q1}), _write(tmp_path / "q2", **{"attendance.csv": ATTENDANCE_Q2})
    catalog = session.add_files(first + second)
    assert [t.name for t in catalog.tables] == ["attendance", "attendance_2", "attendance_all"]
    assert session.conn.execute("SELECT count(*) FROM attendance_all").fetchone()[0] == 4


def test_a_renamed_union_leaves_no_view_behind(store, tmp_path):
    """sales_jan_north + sales_jan_south are sales_jan_all until a February file makes the group
    sales_all. The old view must go, or a later file called sales_jan_all.csv cannot load."""
    session = store.create()
    sales = "region,units\nNorth,1\nSouth,2\n"
    session.add_files(_write(tmp_path / "a", **{"sales_jan_north.csv": sales, "sales_jan_south.csv": sales + "East,3\n"}))
    assert [u.view_name for u in session.catalog.unions] == ["sales_jan_all"]
    session.add_files(_write(tmp_path / "b", **{"sales_feb_north.csv": sales + "West,4\n"}))
    assert [u.view_name for u in session.catalog.unions] == ["sales_all"]
    views = {r[0] for r in session.conn.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()}
    assert views == {"sales_all"}
    catalog = session.add_files(_write(tmp_path / "c", **{"sales_jan_all.csv": "thing,other\nx,1\n"}))
    assert "sales_jan_all" in {t.name for t in catalog.tables}


def test_same_schema_files_get_a_union_view_and_a_hostile_file_name_is_only_ever_data(store, tmp_path):
    session = store.create()
    hostile = "q2'); DROP TABLE attendance_q1; --.csv"
    saved = _write(tmp_path / "up", **{"attendance_q1.csv": ATTENDANCE_Q1, "attendance_q2.csv": ATTENDANCE_Q2})
    saved[1] = (saved[1][0], hostile)  # the second upload claims a hostile original name
    catalog = session.add_files(saved)

    view = next(t for t in catalog.tables if t.is_view)
    assert view.row_count == 4
    rows = session.conn.execute(f'SELECT source_file, sum(CAST(days_absent AS INT)) FROM "{view.name}" GROUP BY 1').fetchall()
    assert dict(rows) == {"attendance_q1.csv": 1, hostile: 6}
    assert session.conn.execute("SELECT count(*) FROM attendance_q1").fetchone()[0] == 2  # still there


def test_too_many_tables_is_refused_with_a_next_step(store, tmp_path, monkeypatch):
    monkeypatch.setattr(sessions_module, "MAX_TABLES_PER_SESSION", 2)
    session = store.create()
    files = {f"file{i}.csv": f"col{i}\n{i}\n" for i in range(3)}
    with pytest.raises(IngestError, match="limit is 2"):
        session.add_files(_write(tmp_path / "up", **files))
    assert session.catalog.tables == []


def test_add_files_with_the_real_ingest_module(tmp_path, monkeypatch):
    """The integration the API relies on."""
    monkeypatch.setattr(sessions_module, "settings", dataclasses.replace(sessions_module.settings, work_dir=tmp_path / "work"))
    session = SessionStore().create()
    employees = "Emp Code,Department,Date of Joining,CTC\n001,Engineering,01/04/2019,\"₹24,00,000\"\n002,Sales,15/07/2020,\"₹12,00,000\"\n"
    payroll = "Emp Code,Pay Month,Gross\n001,01/01/2025,\"₹2,00,000\"\n001,01/02/2025,\"₹2,00,000\"\n002,01/01/2025,\"₹1,00,000\"\n"
    catalog = session.add_files(_write(tmp_path / "up", **{"employees.csv": employees, "payroll.csv": payroll}))
    tables = {t.name: t for t in catalog.tables}
    code = next(c for c in tables["employees"].columns if c.name == "emp_code")
    assert code.type == "text" and code.values == ["001", "002"] and code.role == "employee_id"
    joined = session.conn.execute("SELECT min(date_of_joining) FROM employees").fetchone()[0]
    assert joined.isoformat() == "2019-04-01"
    assert any(r.cardinality == "1:N" and r.status == "active" for r in catalog.relationships)


def test_pii_that_the_real_ingest_types_as_an_amount_never_reaches_the_prompt(tmp_path, monkeypatch):
    """End to end through ingest, profile and the prompt builder: account numbers under a
    header containing "salary", lower-case PANs, a date of birth and a team lead's name."""
    from app.catalog.prompt_context import build_schema_context

    monkeypatch.setattr(sessions_module, "settings", dataclasses.replace(sessions_module.settings, work_dir=tmp_path / "work"))
    rows = [f"E{i:03d},5010023456{i:04d},abcde{1000 + i}f,{1 + i:02d}/01/19{70 + i},Lead Person{i},{1500 + i}" for i in range(12)]
    body = "Emp Code,Salary Account,Tax Ref,DOB,Team Lead Name,Mobile Allowance\n" + "\n".join(rows) + "\n"
    catalog = SessionStore().create().add_files(_write(tmp_path / "up", **{"staff.csv": body}))

    staff = catalog.tables[0]
    assert staff.health.pii_columns == ["salary_account", "tax_ref", "team_lead_name"]  # the allowance is an amount
    prompt = build_schema_context(catalog)
    for leaked in ("50100234560000", "abcde1000f", "1970", "Lead Person"):
        assert leaked not in prompt, leaked
    assert "mobile_allowance" in prompt and "1500" in prompt  # its range is still useful to the model


# --------------------------------------------------------------------------
# load_sample, set_link_status, set_glossary
# --------------------------------------------------------------------------


def test_load_sample_reads_data_files_and_curated_starters(store, tmp_path):
    demo = tmp_path / "demo"
    (demo / "_clean").mkdir(parents=True)
    (demo / "employees.csv").write_text(EMPLOYEES, encoding="utf-8")
    (demo / "payroll.csv").write_text(PAYROLL, encoding="utf-8")
    (demo / "_clean" / "truth.csv").write_text("a\n1\n", encoding="utf-8")  # sub-folders are ignored
    (demo / "README.md").write_text("synthetic", encoding="utf-8")
    (demo / "~$payroll.csv").write_text("lock file", encoding="utf-8")
    (demo / "starters.json").write_text(json.dumps(["What is the total gross by department?"]), encoding="utf-8")

    catalog = store.create().load_sample()
    assert [t.name for t in catalog.tables] == ["employees", "payroll"]
    assert catalog.suggested_questions == ["What is the total gross by department?"]


def test_load_sample_falls_back_to_generated_questions_when_starters_are_unusable(store, tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    (demo / "employees.csv").write_text(EMPLOYEES, encoding="utf-8")
    (demo / "starters.json").write_text('{"not": "a list"}', encoding="utf-8")
    assert store.create().load_sample().suggested_questions  # generated, not empty


def test_load_sample_without_sample_files_says_what_to_do(store):
    with pytest.raises(IngestError, match="Upload your own"):
        store.create().load_sample()


def test_rejecting_a_union_drops_its_view_and_confirming_brings_it_back(store, tmp_path):
    session = store.create()
    session.add_files(_write(tmp_path / "up", **{"attendance_q1.csv": ATTENDANCE_Q1, "attendance_q2.csv": ATTENDANCE_Q2}))
    assert "attendance_all" in {t.name for t in session.catalog.tables}
    session.answer_cache["k"] = Answer(id="a", kind="meta", question="q", text="t")

    rejected = session.set_link_status("attendance_all", "rejected")
    assert rejected.version == 2 and session.answer_cache == {}
    assert "attendance_all" not in {t.name for t in rejected.tables}
    with pytest.raises(duckdb.Error):
        session.conn.execute("SELECT * FROM attendance_all")

    restored = session.set_link_status("attendance_all", "active")
    assert "attendance_all" in {t.name for t in restored.tables}
    assert session.conn.execute("SELECT count(*) FROM attendance_all").fetchone()[0] == 4


def test_a_rejected_relationship_stays_rejected_when_more_files_arrive(store, tmp_path):
    session = store.create()
    session.add_files(_write(tmp_path / "a", **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL}))
    link_id = "employees.emp_id->payroll.emp_code"
    session.set_link_status(link_id, "rejected")
    catalog = session.add_files(_write(tmp_path / "b", **{"attendance_q1.csv": ATTENDANCE_Q1}))
    assert next(r for r in catalog.relationships if r.id == link_id).status == "rejected"
    assert any(r.left_table == "attendance_q1" for r in catalog.relationships)  # new links still appear


def test_unknown_link_ids_and_statuses_are_refused(store):
    session = store.create()
    with pytest.raises(KeyError):
        session.set_link_status("no.such->link.here", "active")
    with pytest.raises(ValueError):
        session.set_link_status("anything", "suggested")


def test_set_glossary_replaces_the_list_and_bumps_the_version(store):
    session = store.create()
    session.answer_cache["k"] = Answer(id="a", kind="meta", question="q", text="t")
    mine = Metric(key="regretted_attrition", name="Regretted attrition", synonyms=["regretted exits"],
                  definition="Exits of employees rated 4 or above.", required_roles=["exit_date", "rating"],
                  sql_pattern="SELECT count(*) FROM {exit_date@table} WHERE {rating} >= 4")
    catalog = session.set_glossary([mine])
    assert catalog.glossary == [mine] and catalog.version == 1 and session.answer_cache == {}
    assert DEFAULT_GLOSSARY and DEFAULT_GLOSSARY[0].key != "regretted_attrition"  # the defaults are untouched


@pytest.mark.parametrize("change", [
    {"definition": "x" * 1001}, {"sql_pattern": "x" * 4001}, {"synonyms": ["s"] * 21}, {"name": " "},
])
def test_set_glossary_refuses_entries_that_would_flood_the_prompt(store, change):
    metric = Metric(key="k", name="Name", synonyms=[], definition="d", required_roles=[], sql_pattern="SELECT 1")
    with pytest.raises(ValueError):
        store.create().set_glossary([metric.model_copy(update=change)])


def test_set_glossary_refuses_duplicate_keys(store):
    metric = Metric(key="k", name="Name", synonyms=[], definition="d", required_roles=[], sql_pattern="SELECT 1")
    with pytest.raises(ValueError, match="more than once"):
        store.create().set_glossary([metric, metric])


# --------------------------------------------------------------------------
# SessionStore
# --------------------------------------------------------------------------


def test_created_sessions_are_locked_down_and_have_unguessable_ids(store):
    a, b = store.create(), store.create()
    assert a.id != b.id and len(a.id) >= 32
    with pytest.raises(duckdb.Error):
        a.conn.execute("SET threads=8")
    with pytest.raises(duckdb.Error):
        a.cursor().execute("SELECT * FROM read_csv('/etc/passwd')")
    assert store.get(a.id) is a


def test_unknown_session_raises_key_error(store):
    with pytest.raises(KeyError):
        store.get("nope")


def test_least_recently_used_session_is_evicted_and_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions_module, "settings", dataclasses.replace(sessions_module.settings, work_dir=tmp_path))
    store = SessionStore(max_sessions=2)
    first, second = store.create(), store.create()
    store.get(first.id)  # first is now the most recently used
    third = store.create()

    assert store.get(first.id) is first and store.get(third.id) is third
    with pytest.raises(KeyError):
        store.get(second.id)
    with pytest.raises(duckdb.Error):
        second.conn.execute("SELECT 1")  # closed
    assert not (tmp_path / second.id).exists() and (tmp_path / first.id).exists()


def test_idle_sessions_expire_and_are_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions_module, "settings", dataclasses.replace(sessions_module.settings, work_dir=tmp_path))
    store = SessionStore(ttl_s=60)
    session = store.create()
    assert store.get(session.id) is session
    session.last_used -= 61
    with pytest.raises(KeyError):
        store.get(session.id)
    with pytest.raises(duckdb.Error):
        session.conn.execute("SELECT 1")
