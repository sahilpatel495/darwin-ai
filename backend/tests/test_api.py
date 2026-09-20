"""The HTTP boundary: uploads, human errors, and the streamed answer."""

import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.llm.fake import FakeLLM
from app.query import pipeline

EMPLOYEES = "Emp Code,Department,CTC\n001,Engineering,\"₹24,00,000\"\n002,Sales,\"₹12,00,000\"\n003,Sales,\"₹15,00,000\"\n"
PAYROLL = "Emp Code,Pay Month,Gross\n001,01/01/2025,\"₹2,00,000\"\n002,01/01/2025,\"₹1,00,000\"\n003,01/01/2025,\"₹1,25,000\"\n"


@pytest.fixture
def client():
    pipeline._SHARED_CACHE.clear()
    main._asks.clear()
    return TestClient(main.app)


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
