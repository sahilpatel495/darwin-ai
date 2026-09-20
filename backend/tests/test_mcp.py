"""MCP over the same engine: the handshake, the six tools, and the promises that ride with them.

Through the real app with a real guest token, because the wiring is the whole point: a
company's agent has to get the same numbers the browser gets, be refused by the same ownership
check, be counted against the same question allowance, and see personal data masked the same
way. The engine's arithmetic is already tested elsewhere; this file tests the door.

Hand-checked against the bundled sample company: 430 active employees, ₹54.67 Cr gross pay,
and an average CTC of ₹15.53 L in Support against ₹10.39 L in Operations.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from app import auth, main
from app.config import Settings
from app.insights import dashboard
from app.limits import Limits
from app.llm.fake import FakeLLM
from app.mcp_server import LATEST, PROTOCOL_VERSIONS, TOOLS
from app.query import pipeline
from fastapi.testclient import TestClient

META = json.dumps({"status": "meta"})  # the cheapest real answer: one model call, no SQL


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A signed-in agent, with nothing counted and no model it may call unscripted."""
    pipeline._SHARED_CACHE.clear()
    dashboard.clear_cache()  # the overview cache is process-level; one test must not answer another
    monkeypatch.setattr(auth, "settings", dataclasses.replace(auth.settings, auth_db_path=tmp_path / "users.db"))
    monkeypatch.setattr(main, "limits", Limits(main.settings))
    monkeypatch.setattr(main, "llm", FakeLLM({}))  # any unscripted model call fails loudly
    client = TestClient(main.app)
    client.headers["Authorization"] = f"Bearer {guest_token(client)}"
    yield client
    dashboard.clear_cache()


def guest_token(client) -> str:
    res = client.post("/api/auth/guest", headers={"Authorization": ""})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def rpc(client, method, params=None, *, id=1, **kwargs):
    message = {"jsonrpc": "2.0", "method": method}
    if id is not None:
        message["id"] = id
    if params is not None:
        message["params"] = params
    return client.post("/mcp", json=message, **kwargs)


def result(response) -> dict:
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def call(client, name, **arguments) -> dict:
    """One tools/call, as the protocol carries it (may be a tool error)."""
    return result(rpc(client, "tools/call", {"name": name, "arguments": arguments}))


def structured(client, name, **arguments) -> dict:
    payload = call(client, name, **arguments)
    assert payload.get("isError") is not True, payload
    assert payload["content"][0]["type"] == "text" and payload["content"][0]["text"]
    return payload["structuredContent"]


@pytest.fixture
def sample(client) -> str:
    """The bundled sample company, loaded the only way an agent can: through the tool."""
    return structured(client, "load_sample_data")["session_id"]


# --------------------------------------------------------------------------
# Protocol
# --------------------------------------------------------------------------


def test_the_handshake_echoes_a_version_we_speak_and_falls_back_to_ours(client):
    mine = result(rpc(client, "initialize", {"protocolVersion": PROTOCOL_VERSIONS[-1],
                                             "capabilities": {}, "clientInfo": {"name": "agent"}}))
    assert mine["protocolVersion"] == PROTOCOL_VERSIONS[-1]
    assert mine["capabilities"] == {"tools": {}}
    assert mine["serverInfo"]["name"] == "darwinlens"

    theirs = result(rpc(client, "initialize", {"protocolVersion": "1999-01-01"}))
    assert theirs["protocolVersion"] == LATEST

    started = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert started.status_code == 202 and not started.content
    assert result(rpc(client, "ping")) == {}


def test_every_tool_publishes_a_json_schema_object(client):
    tools = result(rpc(client, "tools/list"))["tools"]
    assert {t["name"] for t in tools} == {
        "load_sample_data", "describe_data", "get_overview", "list_analyses", "run_analysis", "ask"}
    for tool in tools:
        schema = tool["inputSchema"]
        assert tool["description"].strip(), tool["name"]
        assert schema["type"] == "object" and isinstance(schema["properties"], dict)
        # A required name that is not a property is a schema a client cannot satisfy.
        assert set(schema.get("required", [])) <= set(schema["properties"]), tool["name"]
        for name, field in schema["properties"].items():
            assert field["type"] in ("string", "boolean", "object"), (tool["name"], name)
            assert field["description"].strip(), (tool["name"], name)
    assert tools == TOOLS  # what tools/list serves is the one definition, not a copy


def test_a_batch_answers_only_the_messages_that_asked(client):
    res = client.post("/mcp", json=[
        {"jsonrpc": "2.0", "id": "a", "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": "b", "method": "tools/list"},
    ])
    assert res.status_code == 200
    replies = res.json()
    assert [r["id"] for r in replies] == ["a", "b"]
    assert len(replies[1]["result"]["tools"]) == 6

    only_notifications = client.post("/mcp", json=[{"jsonrpc": "2.0", "method": "notifications/initialized"}])
    assert only_notifications.status_code == 202 and not only_notifications.content


def test_an_unknown_method_is_a_jsonrpc_error_not_a_crash(client):
    body = rpc(client, "resources/list").json()
    assert body["error"]["code"] == -32601 and body["id"] == 1
    assert "tools/list" in body["error"]["message"]


def test_malformed_input_is_answered_in_jsonrpc_not_html(client):
    broken = client.post("/mcp", content=b"{not json", headers={"content-type": "application/json"})
    assert broken.status_code == 200 and broken.json()["error"]["code"] == -32700

    not_a_message = client.post("/mcp", json="hello")
    assert not_a_message.json()["error"]["code"] == -32600
    assert client.post("/mcp", json=[]).json()["error"]["code"] == -32600
    assert rpc(client, "ping", params="nope").json()["error"]["code"] == -32602


def raw(client, body: str):
    return client.post("/mcp", content=body.encode(), headers={"content-type": "application/json"})


def test_json_that_python_can_read_but_cannot_answer_is_still_a_parse_error(client):
    """Two bodies that `json.loads` does not refuse with a ValueError, and one it invents.

    Nesting deep enough costs the interpreter's own stack, and `json` accepts NaN and Infinity
    that the encoder then will not write back — both used to leave through the app's 500 handler,
    which tells an agent to reload the page. They are client mistakes, so they are -32700.
    """
    deep = raw(client, '{"jsonrpc":"2.0","id":1,"method":"ping","x":' + "[" * 20_000 + "]" * 20_000 + "}")
    assert deep.status_code == 200 and deep.json()["error"]["code"] == -32700

    for body in ('{"jsonrpc":"2.0","id":NaN,"method":"ping"}',
                 '{"jsonrpc":"2.0","id":1,"method":"ping","x":Infinity}'):
        assert raw(client, body).json()["error"]["code"] == -32700


def test_an_id_that_is_not_a_string_a_number_or_null_is_refused_not_echoed(client):
    """The id is the one part of a request that comes back verbatim, so it is checked."""
    for ident in ({"deep": [1, 2]}, [1, 2]):
        body = client.post("/mcp", json={"jsonrpc": "2.0", "id": ident, "method": "ping"}).json()
        assert body["error"]["code"] == -32600 and body["id"] is None

    for ident in ("abc", 1.5, 0):  # the shapes the protocol does allow are answered as sent
        assert rpc(client, "ping", id=ident).json()["id"] == ident
    # An explicit null id is a request, not a notification: it gets a reply carrying null back.
    assert client.post("/mcp", json={"jsonrpc": "2.0", "id": None, "method": "ping"}).json() == {
        "jsonrpc": "2.0", "id": None, "result": {}}


def test_no_token_is_a_401_that_says_how_to_get_one(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                      headers={"Authorization": ""})
    assert res.status_code == 401
    assert res.headers["www-authenticate"].startswith("Bearer")
    assert res.json()["next_step"] and "/api/auth/guest" in res.json()["next_step"]
    assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                       headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_get_is_405_because_there_is_no_server_initiated_stream(client):
    res = client.get("/mcp")
    assert res.status_code == 405 and res.headers["allow"] == "POST"
    assert res.json()["next_step"]


# --------------------------------------------------------------------------
# The tools, on the sample company
# --------------------------------------------------------------------------


def test_load_sample_data_owns_the_session_and_summarises_the_files(client):
    payload = call(client, "load_sample_data")
    loaded = payload["structuredContent"]
    # Owned by the caller: the same token opens it through the REST API too.
    assert client.get(f"/api/sessions/{loaded['session_id']}/catalog").status_code == 200
    names = {t["name"] for t in loaded["tables"]}
    assert {"employees", "salary_register_2025_register", "sales"} <= names
    assert next(t for t in loaded["tables"] if t["name"] == "employees")["rows"] == 500
    assert any(v["view"] == "attendance_all" for v in loaded["combined_views"])
    assert any(link["status"] == "active" for link in loaded["links"])
    assert "employees" in payload["content"][0]["text"]


def test_describe_data_names_the_personal_columns_and_shows_no_value_from_them(client, sample):
    described = structured(client, "describe_data", session_id=sample)
    employees = next(t for t in described["tables"] if t["name"] == "employees")
    ctc = next(c for c in employees["columns"] if c["name"] == "ctc")
    assert ctc["type"] == "currency" and ctc["role"] == "ctc" and ctc["personal_data"] is False
    assert next(c for c in employees["columns"] if c["name"] == "name")["personal_data"] is True
    assert "employees.name" in described["personal_data_columns"]
    assert {m["key"] for m in described["glossary"]}  # the customer's metric dictionary
    # Names only. A value out of a personal-data column must not ride along anywhere.
    assert "Asha" not in json.dumps(described) and "@example" not in json.dumps(described)


def test_get_overview_returns_the_computed_dashboard_with_no_model(client, sample, monkeypatch):
    monkeypatch.setattr(main, "llm", None)  # any model call from here would now crash the request
    board = structured(client, "get_overview", session_id=sample)
    tiles = [tile for section in board["sections"] for tile in section["tiles"]]
    assert next(t for t in tiles if t["id"] == "people-headcount")["statement"] == "Active headcount is 430."
    assert next(t for t in tiles if t["id"] == "pay-total")["statement"] == "Total gross pay is ₹54.67 Cr."
    assert any(t["insights"] for t in tiles)
    text = call(client, "get_overview", session_id=sample)["content"][0]["text"]
    assert "430" in text and "₹54.67 Cr" in text


def test_list_analyses_publishes_the_kinds_and_the_columns_each_input_accepts(client, sample):
    listed = structured(client, "list_analyses", session_id=sample)
    breakdown = next(k for k in listed["kinds"] if k["key"] == "breakdown")
    assert [i["key"] for i in breakdown["inputs"]] == ["measure", "by"]
    assert breakdown["inputs"][0]["accepts"] == ["measure"]
    assert "sum" in next(o for o in breakdown["options"] if o["key"] == "aggregate")["choices"]
    refs = {c["ref"]: c for c in listed["columns"]}
    assert refs["employees.ctc"]["kind"] == "measure" and refs["employees.department"]["kind"] == "category"
    assert "Engineering" in refs["employees.department"]["values"]
    assert "employees.name" not in refs  # personal data is never offered as a measure or a group


def test_run_analysis_returns_the_computed_tile_with_its_sql_and_rows(client, sample, monkeypatch):
    monkeypatch.setattr(main, "llm", None)
    tile = structured(client, "run_analysis", session_id=sample, kind="breakdown",
                      inputs={"measure": "employees.ctc", "by": "employees.department"},
                      options={"aggregate": "average"})
    assert tile["statement"] == ("Support is highest at ₹15.53 L and Operations lowest at "
                                 "₹10.39 L, across 6 groups.")
    assert tile["insights"] and "AVG" in tile["sql"].upper()
    assert tile["table"]["display"][0] == ["Support", "₹15.53 L"]
    assert tile["table"]["row_count"] == 6 and tile["table"]["truncated"] is False


def test_an_engine_refusal_is_a_tool_error_carrying_the_engines_sentence(client, sample):
    refused = call(client, "run_analysis", session_id=sample, kind="astrology", inputs={})
    assert refused["isError"] is True
    assert "astrology" in refused["content"][0]["text"]
    assert "structuredContent" not in refused

    missing = call(client, "run_analysis", session_id=sample, kind="breakdown",
                   inputs={"measure": "employees.ctc"})
    assert missing["isError"] is True and "Split by" in missing["content"][0]["text"]


def test_somebody_elses_session_is_refused_exactly_as_the_rest_api_refuses_it(client, sample):
    intruder = guest_token(client)
    res = rpc(client, "tools/call", {"name": "describe_data", "arguments": {"session_id": sample}},
              headers={"Authorization": f"Bearer {intruder}"})
    assert res.status_code == 404
    assert res.json() == client.get(f"/api/sessions/{sample}/catalog",
                                    headers={"Authorization": f"Bearer {intruder}"}).json()


# --------------------------------------------------------------------------
# ask: the full question pipeline, with the same budget and the same PII rules
# --------------------------------------------------------------------------

HEADCOUNT_SQL = "SELECT count(*) AS headcount FROM employees"


def scripted(monkeypatch, sql: str, text: str) -> None:
    generation = json.dumps({"status": "ok", "interpretation": "Counts the rows.", "plan": ["Count"],
                             "assumptions": [], "sql": sql, "clarify_question": "", "clarify_options": [],
                             "missing": "", "metrics_used": []})
    narration = json.dumps({"text": text, "reading": "Counts every employee row.", "followups": []})
    monkeypatch.setattr(main, "llm", FakeLLM({"sql": [generation], "narrate": [narration]}))


def test_ask_runs_the_whole_pipeline_and_returns_the_verified_answer(client, sample, monkeypatch):
    scripted(monkeypatch, HEADCOUNT_SQL, "There are 500 employees on file.")
    answered = structured(client, "ask", session_id=sample, question="How many employees are on file?")
    assert answered["kind"] == "answer"
    assert answered["answer"] == "There are 500 employees on file."
    assert answered["confidence"]["level"] in ("high", "medium", "low") and answered["confidence"]["reasons"]
    assert answered["sql"] and answered["table"]["rows"] == [[500]]
    assert answered["table"]["display"] == [["500"]]


def test_an_ambiguous_word_asks_for_the_customers_definition_then_uses_it(client, sample, monkeypatch):
    """The first turn spends no model call at all: the ambiguity check is deterministic."""
    asked = structured(client, "ask", session_id=sample, question="What is the average salary?")
    assert asked["kind"] == "clarify" and asked["table"] is None
    options = {o["value"] for o in asked["clarification"]["options"]}
    assert "employees.ctc" in options and asked["clarification"]["term"] == "salary"

    scripted(monkeypatch, "SELECT avg(ctc) AS average_ctc FROM employees",
             "That is the average annual CTC across the company.")
    resolved = structured(client, "ask", session_id=sample, question="What is the average salary?",
                          clarification={"salary": "employees.ctc"})
    assert resolved["kind"] == "answer" and "AVG" in resolved["sql"].upper()


def test_rows_mask_personal_data_unless_the_caller_asks_for_it(client, sample, monkeypatch):
    scripted(monkeypatch, "SELECT name, department FROM employees LIMIT 3", "Here are the first three.")
    masked = structured(client, "ask", session_id=sample, question="List three employees and their department")
    assert masked["kind"] == "answer"
    assert masked["table"]["rows"][0] == ["[hidden: personal data]", "[hidden: personal data]"]
    assert masked["table"]["display"][0] == ["[hidden: personal data]", "[hidden: personal data]"]
    assert masked["table"]["hidden_columns"] == ["department", "name"]

    # The same question again is a fresh answer, not a cache hit: the first turn is now
    # conversational context, so it is scripted again. Only the caller's flag has changed.
    scripted(monkeypatch, "SELECT name, department FROM employees LIMIT 3", "Here are the first three.")
    shown = structured(client, "ask", session_id=sample, include_personal_data=True,
                       question="List three employees and their department")
    assert shown["table"]["hidden_columns"] == []
    assert shown["table"]["rows"][0][0] not in ("[hidden: personal data]", None)


def test_a_boolean_spelled_as_text_never_unmasks_personal_data(client, sample, monkeypatch):
    """`include_personal_data` is consent, so it is read as a JSON boolean and nothing else.

    A model emitting the *string* "false" is the commonest wrong-typed tool argument there is,
    and `bool("false")` is True: read loosely, the one argument that turns masking off would be
    turned on by a client trying to leave it off. Every non-boolean is refused before the
    session is even looked up, so no model runs and no allowance is spent on a call we will not
    honour — `llm` is None here, which would crash the request if anything reached the pipeline.
    """
    monkeypatch.setattr(main, "llm", None)
    for flag in ("false", "true", "0", 1, 0, [], {}, None):
        refused = call(client, "ask", session_id=sample, question="List three employees",
                       include_personal_data=flag)
        assert refused["isError"] is True, flag
        assert "must be true or false" in refused["content"][0]["text"], flag
        assert call(client, "run_analysis", session_id=sample, kind="breakdown", inputs={},
                    include_personal_data=flag)["isError"] is True, flag
    assert client.get("/api/auth/me").json()["usage"]["asks_this_hour"] == 0


def test_ask_is_charged_to_the_question_allowance_and_the_free_tools_are_not(client, sample, monkeypatch):
    monkeypatch.setattr(main, "limits", Limits(Settings(asks_per_ip_per_hour=1)))
    monkeypatch.setattr(main, "llm", FakeLLM({"sql": [META]}))
    assert structured(client, "ask", session_id=sample, question="What data do I have?")["kind"] == "meta"

    spent = rpc(client, "tools/call", {"name": "ask", "arguments": {"session_id": sample, "question": "and now?"}})
    assert spent.status_code == 429 and spent.headers["retry-after"]
    assert spent.json()["next_step"]
    # Nothing here spends a token, so nothing here spends the allowance either.
    assert structured(client, "get_overview", session_id=sample)["sections"]
    assert structured(client, "describe_data", session_id=sample)["tables"]


def test_one_refusal_in_a_batch_does_not_discard_the_other_replies(client, sample, monkeypatch):
    """A stranger's session and a spent allowance are HTTP statuses when a message travels alone.

    In a batch they cannot be: there is no status true of every reply, and answering the whole
    request with one throws away work the earlier messages were already charged for. Each keeps
    its own sentence and carries the status it would have had in `error.data`.
    """
    intruder = guest_token(client)
    replies = client.post("/mcp", headers={"Authorization": f"Bearer {intruder}"}, json=[
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "describe_data", "arguments": {"session_id": sample}}},
    ]).json()
    assert replies[0]["result"] == {}  # the innocent message still gets its answer
    assert replies[1]["error"]["data"]["httpStatus"] == 404
    assert "Your session has expired." in replies[1]["error"]["message"]

    monkeypatch.setattr(main, "limits", Limits(Settings(asks_per_ip_per_hour=1)))
    monkeypatch.setattr(main, "llm", FakeLLM({"sql": [META]}))  # one answer's worth, no more
    asked = [{"jsonrpc": "2.0", "id": n, "method": "tools/call",
              "params": {"name": "ask", "arguments": {"session_id": sample, "question": q}}}
             for n, q in ((1, "What data do I have?"), (2, "And what else?"))]
    spent = client.post("/mcp", json=asked).json()
    assert spent[0]["result"]["structuredContent"]["kind"] == "meta"  # charged for, so returned
    assert spent[1]["error"]["data"] == {"httpStatus": 429, "retryAfterSeconds": 3600}


def test_a_tool_that_needs_a_session_says_so_instead_of_failing_obscurely(client):
    for name in ("describe_data", "get_overview", "list_analyses"):
        refused = call(client, name)
        assert refused["isError"] is True and "session_id" in refused["content"][0]["text"]
    unknown = rpc(client, "tools/call", {"name": "delete_everything", "arguments": {}}).json()
    assert unknown["error"]["code"] == -32602 and "tools/list" in unknown["error"]["message"]
