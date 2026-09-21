"""The HTTP boundary: uploads, human errors, and the streamed answer."""

import asyncio
import dataclasses
import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import auth, main, sessions
from app.config import Settings
from app.contracts import AskRequest
from app.limits import LimitExceeded, Limits
from app.llm.fake import FakeLLM
from app.query import pipeline
from app.query.executor import QueryError

EMPLOYEES = "Emp Code,Department,CTC\n001,Engineering,\"₹24,00,000\"\n002,Sales,\"₹12,00,000\"\n003,Sales,\"₹15,00,000\"\n"
PAYROLL = "Emp Code,Pay Month,Gross\n001,01/01/2025,\"₹2,00,000\"\n002,01/01/2025,\"₹1,00,000\"\n003,01/01/2025,\"₹1,25,000\"\n"


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A signed-in visitor, because every /api/sessions route now needs one (app.auth).

    The guest token rides on every request as a default header, so these tests stay about
    uploads and answers. Accounts live in this test's own file; limits start at zero.
    """
    pipeline._SHARED_CACHE.clear()
    monkeypatch.setattr(auth, "settings", dataclasses.replace(auth.settings, auth_db_path=tmp_path / "users.db"))
    monkeypatch.setattr(main, "limits", Limits(main.settings))  # every test starts with nothing counted
    client = TestClient(main.app)
    client.headers["Authorization"] = f"Bearer {guest_token(client)}"
    return client


def guest_token(client) -> str:
    """The token "try the live demo" gets: an account with no sign-up (docs/DESIGN_SYSTEM §9)."""
    res = client.post("/api/auth/guest")
    assert res.status_code == 200, res.text
    return res.json()["token"]


def new_session(client) -> str:
    return client.post("/api/sessions").json()["session_id"]


def upload(client, sid, **files):
    return client.post(f"/api/sessions/{sid}/files",
                       files=[("files", (name, body.encode("utf-8"), "text/csv")) for name, body in files.items()])


def events(response):
    out = []
    for block in response.text.split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines() if ": " in l and not l.startswith(":"))
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_upload_two_files_finds_the_join_and_cleans_the_money(client):
    sid = new_session(client)
    catalog = upload(client, sid, **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL}).json()
    tables = {t["name"]: t for t in catalog["tables"]}
    assert set(tables) >= {"employees", "payroll"}
    ctc = next(c for c in tables["employees"]["columns"] if c["name"] == "ctc")
    assert ctc["type"] == "currency" and ctc["max"].startswith("2400000")
    code = next(c for c in tables["employees"]["columns"] if c["name"] == "emp_code")
    assert code["type"] == "text" and "001" in code["values"]  # leading zeros survived
    assert any({r["left_column"], r["right_column"]} == {"emp_code"} for r in catalog["relationships"])


def test_ask_streams_steps_then_an_answer(client, monkeypatch):
    sid = new_session(client)
    upload(client, sid, **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL})
    sql = "SELECT e.department, sum(p.gross) AS total_gross FROM employees e JOIN payroll p ON e.emp_code = p.emp_code GROUP BY e.department ORDER BY total_gross DESC"
    gen = json.dumps({"status": "ok", "interpretation": "Gross per department.", "plan": ["Join", "Sum"], "assumptions": [],
                      "sql": sql, "clarify_question": "", "clarify_options": [], "missing": "", "metrics_used": []})
    say = json.dumps({"text": "Sales has the highest total gross pay at ₹2.25 L.", "reading": "Adds up gross per department.", "followups": []})
    monkeypatch.setattr(main, "llm", FakeLLM({"sql": [gen], "narrate": [say]}))
    got = events(client.post(f"/api/sessions/{sid}/ask", json={"question": "Total gross pay by department?"}))
    assert [e for e, _ in got][-1] == "answer" and any(e == "step" for e, _ in got)
    answer = got[-1][1]
    assert answer["kind"] == "answer" and answer["table"]["rows"][0] == ["Sales", 225000.0]


def test_unknown_session_is_a_human_404(client):
    body = client.get("/api/sessions/nope/catalog")
    assert body.status_code == 404 and body.json()["next_step"]


def test_a_bad_file_is_rejected_with_a_sentence_not_a_trace(client):
    sid = new_session(client)
    res = upload(client, sid, **{"empty.csv": ""})
    assert res.status_code == 422 and "empty" in res.json()["message"].lower()


def test_oversize_upload_is_refused(client, monkeypatch):
    sid = new_session(client)
    monkeypatch.setattr(main, "settings", main.settings.__class__(max_upload_mb=0))
    res = upload(client, sid, **{"big.csv": EMPLOYEES})
    assert res.status_code == 413


def test_security_headers_are_set(client):
    headers = client.get("/healthz").headers
    assert headers["x-content-type-options"] == "nosniff" and "default-src 'self'" in headers["content-security-policy"]


def test_new_session_really_deletes_the_data(client):
    sid = new_session(client)
    upload(client, sid, **{"employees.csv": EMPLOYEES})
    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert client.get(f"/api/sessions/{sid}/catalog").status_code == 404


# --------------------------------------------------------------------------
# Per-user limits. The policy is tested in test_limits.py; this is the wiring.
# --------------------------------------------------------------------------

VISITOR = "203.0.113.9"
META = json.dumps({"status": "meta"})  # the cheapest real answer: one model call, no SQL, no narration


def limited(monkeypatch, **sizes) -> None:
    """Small limits, and a model that fails loudly if a test reaches it without a script."""
    monkeypatch.setattr(main, "limits", Limits(Settings(**sizes)))
    monkeypatch.setattr(main, "llm", FakeLLM({}))


def ask(client, sid, question="hi", spoof="1.1.1.1", token=""):
    headers = {"x-forwarded-for": f"{spoof}, {VISITOR}"}
    return client.post(f"/api/sessions/{sid}/ask", json={"question": question},
                       headers={**headers, "Authorization": f"Bearer {token}"} if token else headers)


def visitor(client) -> tuple[str, str]:
    """Somebody else: their own guest account and their own session, because a session belongs
    to the account that made it and questions are counted against both (app.limits)."""
    token = guest_token(client)
    return token, client.post("/api/sessions", headers={"Authorization": f"Bearer {token}"}).json()["session_id"]


def test_rate_limit_uses_the_proxy_appended_address_not_the_client_supplied_one(client, monkeypatch):
    limited(monkeypatch, asks_per_ip_per_hour=1)
    sid = new_session(client)
    assert ask(client, sid, spoof="1.1.1.1").status_code == 200
    # Neither a new spoofed first hop nor a brand-new account resets what the address has spent.
    token, other_sid = visitor(client)
    assert ask(client, other_sid, spoof="2.2.2.2", token=token).status_code == 429


def test_the_trusted_entry_is_counted_from_the_right_by_trusted_proxy_hops(client, monkeypatch):
    """Two proxies in front (a CDN, then the host's router) means the visitor is second from the
    right; the last entry is the CDN and would put every visitor in one bucket."""
    limited(monkeypatch, asks_per_ip_per_hour=1)
    monkeypatch.setattr(main, "settings", main.settings.__class__(trusted_proxy_hops=2))
    sid = new_session(client)

    def ask_via_cdn(address, cdn="70.0.0.1", session=sid, token=""):
        headers = {"x-forwarded-for": f"1.1.1.1, {address}, {cdn}"}
        return client.post(f"/api/sessions/{session}/ask", json={"question": "hi"},
                           headers={**headers, "Authorization": f"Bearer {token}"} if token else headers)

    assert ask_via_cdn(VISITOR).status_code == 200
    assert ask_via_cdn(VISITOR, cdn="70.0.0.2").status_code == 429  # same visitor, another CDN node
    # A different visitor (their own address and their own account) still has their own allowance,
    # through the same CDN node as the first one: the bucket is the visitor, not the proxy.
    token, other_sid = visitor(client)
    assert ask_via_cdn("198.51.100.7", session=other_sid, token=token).status_code == 200


def test_a_refused_question_is_a_human_429_that_says_when_to_come_back(client, monkeypatch):
    limited(monkeypatch)
    monkeypatch.setattr(main, "limits", Limits(Settings(asks_per_ip_per_hour=1), clock=lambda: 0.0))
    sid = new_session(client)
    assert ask(client, sid).status_code == 200
    res = ask(client, sid)
    assert res.status_code == 429 and res.headers["retry-after"] == "3600"
    assert res.json() == {"message": "You have reached this demo's limit of 1 question an hour.",
                          "next_step": "You can ask again in about 60 minutes."}


def test_an_answer_from_the_shared_cache_is_not_counted(client, monkeypatch):
    limited(monkeypatch, asks_per_ip_per_hour=2)
    monkeypatch.setattr(main, "llm", FakeLLM({"sql": [META]}))  # scripted for exactly one model call
    for _ in range(4):  # same file, same question: the first is answered, the rest come from the cache
        sid = new_session(client)
        upload(client, sid, **{"employees.csv": EMPLOYEES})
        res = ask(client, sid, "What data do I have?")
        assert res.status_code == 200 and events(res)[-1][1]["kind"] == "meta"
    assert events(res)[-1][1]["work"]["cached"] is True
    assert ask(client, sid, "hi").status_code == 200  # 2 of 2: an answer that is not cached still counts
    assert ask(client, sid, "hi").status_code == 429


def test_the_concurrency_slot_is_free_again_after_an_answer_an_error_answer_and_a_crash(client, monkeypatch):
    limited(monkeypatch, max_concurrent_asks=1)  # one slot: any leak turns the next question into a 429
    sid = new_session(client)
    assert events(ask(client, sid))[-1][1]["kind"] == "error"  # no data yet: an error answer

    upload(client, sid, **{"employees.csv": EMPLOYEES})
    monkeypatch.setattr(main, "llm", FakeLLM({"sql": [META]}))
    assert events(ask(client, sid, "What data do I have?"))[-1][1]["kind"] == "meta"  # a real answer

    def crash(*_):
        raise RuntimeError("the pipeline broke its never-raises contract")

    monkeypatch.setattr(main, "answer_question", crash)
    assert events(ask(client, sid))[-1][0] == "error"  # an exception in the worker thread
    assert ask(client, sid).status_code == 200  # and the slot came back that time too


def test_a_question_asked_while_the_visitor_is_at_their_concurrency_limit_is_refused_not_queued(client, monkeypatch):
    limited(monkeypatch, max_concurrent_asks_per_ip=1)
    sid = new_session(client)
    with main.limits.question(VISITOR, "their other tab"):
        res = ask(client, sid)
        assert res.status_code == 429 and "already" in res.json()["message"] and res.headers["retry-after"] == "5"
    assert ask(client, sid).status_code == 200


def test_the_slot_is_freed_when_the_browser_goes_away_before_reading_the_answer(client, monkeypatch):
    limited(monkeypatch, max_concurrent_asks=1)
    sid = new_session(client)
    gone = Request({"type": "http", "headers": [(b"x-forwarded-for", VISITOR.encode())], "client": ("10.0.0.1", 1)})
    owner = auth.find(main.store.get(sid).user_id)
    asyncio.run(main.ask(sid, AskRequest(question="hi"), gone, owner))  # called directly; its stream is never read
    deadline = time.monotonic() + 5
    while True:  # the worker thread owns the slot, so it comes back without anybody reading the stream
        try:
            with main.limits.question("198.51.100.7", "somebody else"):
                break
        except LimitExceeded:
            assert time.monotonic() < deadline, "the concurrency slot was never released"
            time.sleep(0.01)


def test_new_sessions_and_uploads_are_limited_per_address(client, monkeypatch):
    limited(monkeypatch, sessions_per_ip_per_hour=1, uploads_per_ip_per_hour=1)
    sid = new_session(client)
    res = client.post("/api/sessions")
    assert res.status_code == 429 and "1 new session an hour" in res.json()["message"] and res.headers["retry-after"]
    assert upload(client, sid, **{"employees.csv": EMPLOYEES}).status_code == 200
    assert upload(client, sid, **{"payroll.csv": PAYROLL}).status_code == 429
    assert client.post(f"/api/sessions/{sid}/sample").status_code == 429  # the sample is read in like any upload
    assert client.get(f"/api/sessions/{sid}/catalog").status_code == 200  # looking at loaded data is never limited


def test_only_one_file_is_read_in_at_a_time_and_the_second_is_refused_after_its_wait(client, monkeypatch):
    """Parsing is the memory peak on a 512 MB host, so two never run together: the second waits
    its turn (a moment here, 25 s in production) and only then is refused."""
    limited(monkeypatch)
    monkeypatch.setattr(main, "INGEST_WAIT_S", 0.05)
    sid = new_session(client)
    with main.limits.ingest():  # somebody else's file is being read right now
        res = upload(client, sid, **{"employees.csv": EMPLOYEES})
        assert res.status_code == 429 and res.headers["retry-after"] == "5"
        assert res.json() == {"message": "Another upload is being read.", "next_step": "Try again in a few seconds."}
        assert client.post(f"/api/sessions/{sid}/sample").status_code == 429  # the sample costs the same
    assert upload(client, sid, **{"employees.csv": EMPLOYEES}).status_code == 200  # the slot came back


# --------------------------------------------------------------------------
# Preview rows: shown to the data owner, never to a model
# --------------------------------------------------------------------------


def preview(client, sid, table, **params):
    return client.get(f"/api/sessions/{sid}/tables/{table}/preview", params=params)


def test_preview_formats_rows_the_way_answers_do_and_never_calls_the_model(client, monkeypatch):
    monkeypatch.setattr(main, "llm", None)  # any use of the model client would now crash the request
    sid = new_session(client)
    upload(client, sid, **{"employees.csv": EMPLOYEES, "payroll.csv": PAYROLL})
    table = preview(client, sid, "employees").json()
    assert table["columns"] == ["emp_code", "department", "ctc"]
    assert table["rows"][0] == ["001", "Engineering", 2400000.0]
    assert table["display"][0] == ["001", "Engineering", "₹24.00 L"]  # leading zeros kept, rupees as in answers
    assert table["row_count"] == 3 and table["truncated"] is False
    # Dates too, and a column holding nothing but first-of-month dates reads as the month
    # (app.query.presentation._is_month_column), exactly as it does in an answer.
    assert preview(client, sid, "payroll").json()["display"][0][1] == "Jan 2025"


def test_preview_limit_is_honoured_capped_and_says_when_there_is_more(client):
    sid = new_session(client)
    upload(client, sid, **{"many.csv": "n,label\n" + "".join(f"{i},row {i}\n" for i in range(250))})
    two = preview(client, sid, "many", limit=2).json()
    assert two["row_count"] == 2 and two["truncated"] is True
    capped = preview(client, sid, "many", limit=100000).json()
    assert capped["row_count"] == 200 and capped["truncated"] is True
    assert preview(client, sid, "many", limit=-5).json()["row_count"] == 1  # nonsense is clamped, not an error


def test_preview_of_an_unknown_table_is_a_human_404_and_the_name_never_reaches_sql(client):
    sid = new_session(client)
    upload(client, sid, **{"employees.csv": EMPLOYEES})
    for hostile in ('employees"; DROP TABLE employees; --', "information_schema.tables", "nope"):
        res = preview(client, sid, hostile)
        assert res.status_code == 404 and res.json()["message"] and res.json()["next_step"]
    assert preview(client, sid, "employees").json()["row_count"] == 3  # still there
    assert preview(client, "no-such-session", "employees").status_code == 404


def test_a_preview_that_duckdb_refuses_is_a_sentence_that_quotes_no_cell(client, monkeypatch):
    """DuckDB's own message can quote a cell value, and cells are the one thing this app
    promises not to hand out. The browser gets the usual two sentences; the log gets the rest."""
    sid = new_session(client)
    upload(client, sid, **{"employees.csv": EMPLOYEES})

    def refuse(*_, **__):
        raise QueryError("Conversion Error: Could not convert string 'Asha Rao' to INT32")

    monkeypatch.setattr(sessions, "execute", refuse)
    res = preview(client, sid, "employees")
    assert res.status_code == 500 and res.json()["message"] and res.json()["next_step"]
    assert "Asha Rao" not in res.text and "duckdb" not in res.text.lower()


def test_an_unknown_api_path_is_a_json_404_never_the_web_page(client):
    res = client.get("/api/sessions/whatever/not-a-real-route")
    assert res.status_code == 404
    if res.headers.get("content-type", "").startswith("application/json"):
        assert res.json()["next_step"]


def test_a_second_reader_waits_for_its_turn_instead_of_being_refused(client, monkeypatch):
    """A first visitor who presses the demo button twice, or arrives a second after somebody else,
    used to be told to try again. Now the second read waits for the first and then succeeds."""
    import threading
    import time

    limited(monkeypatch)
    sid = new_session(client)
    holder = main.limits.ingest()
    holder.__enter__()  # somebody else's file is being read right now
    threading.Thread(target=lambda: (time.sleep(0.3), holder.__exit__(None, None, None))).start()
    assert client.post(f"/api/sessions/{sid}/sample").status_code == 200  # waited about 0.3 s, then read
