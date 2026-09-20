"""The three routes that cost nothing: the overview, the picker, and one guided analysis.

Through the real app, from upload to JSON, because that is the only place the wiring is
visible: the engine's own tests already prove the arithmetic on a hand-built session, and these
prove that a browser gets it — the same numbers, the same display strings, the same answer on a
reload, a human 404 for a dead session, a 422 for a hostile selection, and no model client
anywhere near it.

Two files, six employees, twelve payslips, all of it checkable by eye:
average CTC is ₹24.00 L in Engineering, ₹13.50 L in Sales, ₹9.00 L in HR; gross is ₹9.00 L in
each of the two months, so ₹18.00 L in total.
"""

from __future__ import annotations

import pytest
from app import main
from app.insights import dashboard
from app.insights.analyses import KINDS
from app.insights.dashboard import MAX_TILES, QUALITY_SECTION
from app.limits import Limits
from fastapi.testclient import TestClient

EMPLOYEES = (
    "Emp Code,Name,Email,Department,Location,Gender,Date of Joining,Exit Date,CTC\n"
    '001,Asha Rao,asha.rao@example.com,Engineering,Bengaluru,F,01/04/2019,,"₹24,00,000"\n'
    '002,Vikram Shah,vikram.shah@example.com,Engineering,Pune,M,15/07/2020,,"₹18,00,000"\n'
    '003,Meera Iyer,meera.iyer@example.com,Sales,Mumbai,F,10/01/2018,31/03/2025,"₹15,00,000"\n'
    '004,Rohan Das,rohan.das@example.com,Sales,Mumbai,M,01/09/2021,,"₹12,00,000"\n'
    '005,Kavya Nair,kavya.nair@example.com,HR,Bengaluru,F,14/02/2022,,"₹9,00,000"\n'
    '006,Arjun Mehta,arjun.mehta@example.com,Engineering,Hyderabad,M,20/11/2017,30/06/2025,"₹30,00,000"\n'
)
# Gross is exactly CTC/12, so every total below can be checked without running anything.
PAYROLL = "Emp Code,Pay Month,Gross,Net\n" + "".join(
    f'{code},{month},"₹{gross}","₹{net}"\n'
    for code, gross, net in (("001", "2,00,000", "1,60,000"), ("002", "1,50,000", "1,20,000"),
                             ("003", "1,25,000", "1,00,000"), ("004", "1,00,000", "80,000"),
                             ("005", "75,000", "60,000"), ("006", "2,50,000", "2,00,000"))
    for month in ("01/01/2025", "01/02/2025")
)
PII_VALUES = ("Asha Rao", "asha.rao@example.com", "Arjun Mehta")


@pytest.fixture
def client(monkeypatch):
    dashboard.clear_cache()  # the overview cache is process-level; one test must not answer another
    monkeypatch.setattr(main, "limits", Limits(main.settings))  # every test starts with nothing counted
    monkeypatch.setattr(main, "llm", None)  # any model call from these routes would now crash the request
    with TestClient(main.app) as client:
        yield client
    dashboard.clear_cache()


@pytest.fixture
def sid(client) -> str:
    """A session with the two files loaded, which is what every route here is about."""
    session_id = client.post("/api/sessions").json()["session_id"]
    res = client.post(f"/api/sessions/{session_id}/files",
                      files=[("files", (name, body.encode("utf-8"), "text/csv"))
                             for name, body in (("employees.csv", EMPLOYEES), ("payroll.csv", PAYROLL))])
    assert res.status_code == 200, res.text
    return session_id


def run(client, session_id, kind, inputs, **options):
    return client.post(f"/api/sessions/{session_id}/analyses/run",
                       json={"kind": kind, "inputs": inputs, "options": options})


# --------------------------------------------------------------------------- the overview


def test_the_overview_arrives_with_findings_and_never_quotes_a_person(client, sid):
    body = client.get(f"/api/sessions/{sid}/dashboard")
    assert body.status_code == 200
    overview = body.json()
    assert overview["session_id"] == sid and overview["catalog_version"] >= 1
    tiles = [tile for section in overview["sections"] for tile in section["tiles"]]
    assert 0 < len(tiles) <= MAX_TILES
    assert all(tile["statement"] for tile in tiles)  # a tile with no sentence is a blank card
    assert QUALITY_SECTION in [section["title"] for section in overview["sections"]]
    # The quality section names personal-data columns; no tile may carry a personal-data value.
    assert not [value for value in PII_VALUES if value in body.text]


def test_these_routes_are_not_rationed_because_they_spend_nothing(client, sid, monkeypatch):
    """No model call means no tokens to protect, so none of the three touches the limiter.
    With the limiter taken away entirely, any accounting would be an AttributeError -> 500."""
    monkeypatch.setattr(main, "limits", None)
    assert client.get(f"/api/sessions/{sid}/dashboard").status_code == 200
    assert client.get(f"/api/sessions/{sid}/analyses").status_code == 200
    assert run(client, sid, "distribution", {"measure": "employees.ctc"}).status_code == 200


def test_the_same_files_give_the_same_overview_twice(client, sid):
    """The one promise this half of the product makes. A second call is also the cached path,
    so this covers both: identical bytes, whether recomputed or remembered."""
    first = client.get(f"/api/sessions/{sid}/dashboard").json()
    assert client.get(f"/api/sessions/{sid}/dashboard").json()["sections"] == first["sections"]


# --------------------------------------------------------------------------- the picker


def test_the_picker_offers_every_kind_and_no_personal_or_identifier_column(client, sid):
    catalog = client.get(f"/api/sessions/{sid}/analyses").json()
    assert [kind["key"] for kind in catalog["kinds"]] == [kind.key for kind in KINDS]
    columns = {column["ref"]: column for column in catalog["columns"]}
    assert columns["employees.ctc"]["kind"] == "measure"
    assert columns["employees.department"]["kind"] == "category"
    assert columns["payroll.pay_month"]["kind"] == "date"
    assert columns["employees.department"]["table_label"] == "employees.csv"  # the file, not the table
    # A name, an email and an employee code are never something to measure or group by.
    assert not [ref for ref in columns if ref.split(".")[1] in ("name", "email", "emp_code")]


# --------------------------------------------------------------------------- running one


def test_a_breakdown_comes_back_with_the_hand_checked_numbers_and_a_bar(client, sid):
    tile = run(client, sid, "breakdown",
               {"measure": "employees.ctc", "by": "employees.department"}, aggregate="average").json()
    assert tile["table"]["rows"] == [["Engineering", 2400000.0], ["Sales", 1350000.0], ["HR", 900000.0]]
    assert tile["table"]["display"][0] == ["Engineering", "₹24.00 L"]
    assert tile["chart"]["type"] == "bar"
    assert "₹24.00 L" in tile["statement"] and tile["sql"].lower().startswith("select")


def test_a_trend_buckets_the_dates_and_sums_both_months(client, sid):
    tile = run(client, sid, "trend", {"measure": "payroll.gross", "date": "payroll.pay_month"},
               aggregate="sum", grain="month").json()
    assert tile["table"]["display"] == [["01 Jan 2025", "₹9.00 L"], ["01 Feb 2025", "₹9.00 L"]]
    assert tile["kind"] == "trend" and tile["chart"]["type"] == "line"


def test_comparing_two_groups_uses_the_columns_own_values(client, sid):
    tile = run(client, sid, "compare", {"measure": "employees.ctc", "by": "employees.department"},
               aggregate="average", group_a="engineering", group_b="Sales").json()
    assert tile["table"]["rows"] == [["Engineering", 2400000.0], ["Sales", 1350000.0]]
    assert "₹10.50 L" in tile["statement"]  # the gap, formatted exactly as an answer would


# --------------------------------------------------------------------------- refusals


HOSTILE = [
    # a column reference carrying SQL
    ("breakdown", {"measure": 'employees.ctc"; DROP TABLE employees; --', "by": "employees.department"}, {}),
    ("breakdown", {"measure": "employees.ctc", "by": "employees.department'; DELETE FROM employees"}, {}),
    # a column that is not there, and one that is personal data or an identifier
    ("breakdown", {"measure": "employees.salary", "by": "employees.department"}, {}),
    ("breakdown", {"measure": "employees.ctc", "by": "employees.name"}, {}),
    ("breakdown", {"measure": "employees.ctc", "by": "employees.emp_code"}, {}),
    # an input the kind does not take, and a missing one
    ("distribution", {"measure": "employees.ctc", "by": "employees.department"}, {}),
    ("breakdown", {"by": "employees.department"}, {}),
    # an option outside its allow-list, and an option nobody offers
    ("breakdown", {"measure": "employees.ctc", "by": "employees.department"},
     {"aggregate": "sum) AS x FROM employees; --"}),
    ("breakdown", {"measure": "employees.ctc", "by": "employees.department"}, {"top_n": "5"}),
    # a group value that is not one of the column's own values
    ("compare", {"measure": "employees.ctc", "by": "employees.department"},
     {"group_a": "Engineering' OR 1=1 --", "group_b": "Sales"}),
    # a kind that does not exist
    ("drop_everything", {"measure": "employees.ctc"}, {}),
]


@pytest.mark.parametrize(("kind", "inputs", "options"), HOSTILE)
def test_a_hostile_selection_is_a_422_with_a_sentence(client, sid, kind, inputs, options):
    res = run(client, sid, kind, inputs, **options)
    assert res.status_code == 422, res.text
    assert res.json()["message"] and res.json()["next_step"] == "Change the selection and try again."


def test_nothing_hostile_changed_anything(client, sid):
    """The refusals above must be refusals, not failed attempts: same rows, same catalog after."""
    for kind, inputs, options in HOSTILE:
        assert run(client, sid, kind, inputs, **options).status_code == 422
    catalog = client.get(f"/api/sessions/{sid}/catalog").json()
    assert {table["name"]: table["row_count"] for table in catalog["tables"]} == {"employees": 6, "payroll": 12}
    tile = run(client, sid, "breakdown",
               {"measure": "employees.ctc", "by": "employees.department"}, aggregate="average").json()
    assert tile["table"]["rows"] == [["Engineering", 2400000.0], ["Sales", 1350000.0], ["HR", 900000.0]]


@pytest.mark.parametrize("call", [
    lambda c, s: c.get(f"/api/sessions/{s}/dashboard"),
    lambda c, s: c.get(f"/api/sessions/{s}/analyses"),
    lambda c, s: c.post(f"/api/sessions/{s}/analyses/run",
                        json={"kind": "distribution", "inputs": {"measure": "employees.ctc"}}),
])
def test_an_unknown_session_is_the_apps_human_404(client, call):
    res = call(client, "no-such-session")
    assert res.status_code == 404
    assert res.json() == {"message": "Your session has expired.", "next_step": "Please upload your files again."}
