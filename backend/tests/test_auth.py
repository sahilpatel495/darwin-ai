"""Accounts: a guest is a user, signing up upgrades one, and everything else is a sentence.

Nothing here calls a model. Each test gets its own empty SQLite file (tmp_path) and its own
limiter, so one test's accounts cannot sign the next one in and one test's attempts cannot
spend another's allowance.

The two rules these tests exist to hold:
- every /api/sessions route needs a live token, and the session must belong to that token;
- nothing secret (a password, a stored hash, a token) is ever written to a log or an error body.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import stat
import time

import pytest
from app import auth, main
from app import limits as limits_module
from app.limits import Limits
from app.llm.fake import FakeLLM
from fastapi.testclient import TestClient

PASSWORD = "a long enough one"
EMAIL = "asha@example.com"
EMPLOYEES = 'Emp Code,Department,CTC\n001,Engineering,"₹24,00,000"\n002,Sales,"₹12,00,000"\n'


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A client whose accounts live in an empty file and whose limits start at zero."""
    monkeypatch.setattr(auth, "settings", dataclasses.replace(auth.settings, auth_db_path=tmp_path / "users.db"))
    monkeypatch.setattr(main, "limits", Limits(main.settings))
    monkeypatch.setattr(main, "llm", None)  # a model call from any of these routes would be a crash
    return TestClient(main.app)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def guest(client) -> tuple[str, dict]:
    """The one call the public demo makes before anything else: a user with no sign-up."""
    res = client.post("/api/auth/guest")
    assert res.status_code == 200, res.text
    return res.json()["token"], res.json()["user"]


def signup(client, token: str = "", **overrides):
    body = {"email": EMAIL, "password": PASSWORD, "name": "Asha Rao", **overrides}
    return client.post("/api/auth/signup", json=body, headers=bearer(token) if token else {})


def login(client, **overrides):
    return client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, **overrides})


def session_of(client, token: str) -> str:
    res = client.post("/api/sessions", headers=bearer(token))
    assert res.status_code == 200, res.text
    return res.json()["session_id"]


def upload(client, session_id: str, token: str):
    return client.post(f"/api/sessions/{session_id}/files", headers=bearer(token),
                       files=[("files", ("employees.csv", EMPLOYEES.encode("utf-8"), "text/csv"))])


def flip(part: str) -> str:
    """The same token with one character changed, which is all a forgery needs to be."""
    return part[:-1] + ("0" if part[-1] != "0" else "1")


# --------------------------------------------------------------------------
# Guests, sign-up, sign-in
# --------------------------------------------------------------------------


def test_a_guest_is_a_real_user_with_no_email(client):
    token, user = guest(client)
    assert user["kind"] == "guest" and user["email"] is None and user["onboarded"] is False
    assert user["id"] and user["name"] and user["created_at"]
    assert client.get("/api/auth/me", headers=bearer(token)).json()["user"] == user


def test_signup_gives_a_member_and_login_gives_the_same_person_back(client):
    created = signup(client, email=" Asha@Example.COM ")
    assert created.status_code == 200, created.text
    user = created.json()["user"]
    assert user["kind"] == "member" and user["email"] == EMAIL  # trimmed and lower-cased
    again = login(client, email="ASHA@example.com")
    assert again.status_code == 200 and again.json()["user"]["id"] == user["id"]


def test_a_wrong_password_and_an_unknown_email_get_the_very_same_sentence(client):
    """Anything else turns this route into a "does this person have an account here?" oracle."""
    signup(client)
    answers = [login(client, password="not the password"), login(client, email="nobody@example.com")]
    for res in answers:
        assert res.status_code == 401
        assert res.json()["message"] == "That email and password do not match."
    assert answers[0].json() == answers[1].json()


def test_a_duplicate_email_is_a_409_with_a_sentence(client):
    assert signup(client).status_code == 200
    res = signup(client, name="Someone Else")
    assert res.status_code == 409 and res.json()["message"] and res.json()["next_step"]


def test_a_guest_whose_signup_is_refused_is_still_that_guest(client):
    """The upgrade and the refusal are one statement, so there is no half-written member."""
    signup(client)  # somebody already has the address
    token, guest_user = guest(client)
    session_id = session_of(client, token)
    assert signup(client, token=token).status_code == 409

    assert auth.find(guest_user["id"]).kind == "guest"
    assert client.get(f"/api/sessions/{session_id}/catalog", headers=bearer(token)).status_code == 200
    assert login(client, password=PASSWORD).json()["user"]["id"] != guest_user["id"]


@pytest.mark.parametrize("name", ["   ", "\t"])
def test_a_name_of_spaces_is_refused_rather_than_stored(client, name):
    """The contract's minimum length counts a space; the greeting would read "know, ?"."""
    assert signup(client, name=name).status_code == 422
    token, _ = guest(client)
    assert client.patch("/api/auth/me", json={"name": name}, headers=bearer(token)).status_code == 422


@pytest.mark.parametrize("email", ["not an email", "two@@example.com", "no domain@", "@example.com",
                                   "trailing@example.", "spaces in@example.com"])
def test_a_malformed_email_is_a_422_with_a_sentence(client, email):
    res = signup(client, email=email)
    assert res.status_code == 422 and res.json()["message"] and res.json()["next_step"]


def test_a_body_the_contract_refuses_still_answers_in_sentences(client):
    """A password one character short is a normal event, not a bug report: FastAPI's own
    {"detail": [...]} would reach the browser as "something went wrong on our side"."""
    res = signup(client, password="short")
    assert res.status_code == 422 and set(res.json()) == {"message", "next_step"}
    assert "8" in res.json()["message"]


@pytest.mark.parametrize("body", [[], "a string", 7, None])
def test_a_body_that_is_not_an_object_at_all_answers_in_sentences_too(client, body):
    """Naming the field only works once the body is a dict. Below that, FastAPI answers with
    its own {"detail": [...]}, which api.ts reads as no message and shows as "something went
    wrong on our side" — a client mistake dressed as a server fault — and which echoes the
    offending input back at the visitor. main._on_bad_body is the floor under _RULES."""
    token, _ = guest(client)
    for res in (client.post("/api/auth/signup", json=body),
                client.post("/api/auth/login", json=body),
                client.patch("/api/auth/me", json=body, headers=bearer(token))):
        assert res.status_code == 422, res.text
        assert set(res.json()) == {"message", "next_step"}, res.text
        assert str(body) not in res.text  # nothing of the request is reflected


def test_the_same_floor_covers_the_session_routes(client):
    """Those routes take a contract model directly, so FastAPI validates them, not us."""
    token, _ = guest(client)
    session_id = session_of(client, token)
    for res in (client.put(f"/api/sessions/{session_id}/glossary", json={}, headers=bearer(token)),
                client.post(f"/api/sessions/{session_id}/ask", json=[], headers=bearer(token))):
        assert res.status_code == 422 and set(res.json()) == {"message", "next_step"}, res.text


def test_signing_up_with_a_guest_token_upgrades_that_guest_in_place(client):
    """The id survives, so their projects (stored in the browser under the id) and their
    already-loaded files come with them. Their old token keeps working: it signs the same id."""
    token, guest_user = guest(client)
    session_id = session_of(client, token)
    assert upload(client, session_id, token).status_code == 200

    body = signup(client, token=token).json()
    assert body["user"]["id"] == guest_user["id"] and body["user"]["kind"] == "member"
    assert body["user"]["email"] == EMAIL and body["user"]["name"] == "Asha Rao"
    for held in (body["token"], token):
        catalog = client.get(f"/api/sessions/{session_id}/catalog", headers=bearer(held))
        assert catalog.status_code == 200 and catalog.json()["tables"]


def test_me_reports_what_this_user_has_spent(client, monkeypatch):
    token, _ = guest(client)
    session_id = session_of(client, token)
    monkeypatch.setattr(main, "llm", FakeLLM({}))  # no data loaded: an error answer, still a question
    client.post(f"/api/sessions/{session_id}/ask", json={"question": "hi"}, headers=bearer(token))
    assert client.get("/api/auth/me", headers=bearer(token)).json()["usage"] == {
        "asks_this_hour": 1, "asks_per_hour": main.settings.asks_per_ip_per_hour,
        "asks_today": 1, "asks_per_day": main.settings.asks_per_ip_per_day}


def test_a_profile_update_changes_only_what_it_names(client):
    token, user = guest(client)
    named = client.patch("/api/auth/me", json={"name": "Sahil", "onboarded": True}, headers=bearer(token))
    assert named.status_code == 200
    assert named.json()["name"] == "Sahil" and named.json()["onboarded"] is True
    assert named.json()["id"] == user["id"] and named.json()["kind"] == "guest"
    kept = client.patch("/api/auth/me", json={"role": "Payroll"}, headers=bearer(token))
    assert kept.json() == {**named.json(), "role": "Payroll"}


def test_deleting_an_account_takes_the_user_and_their_loaded_files_with_it(client):
    token, user = guest(client)
    session_id = session_of(client, token)
    assert upload(client, session_id, token).status_code == 200

    assert client.delete("/api/auth/me", headers=bearer(token)).status_code == 204
    assert main.store.ids_for_user(user["id"]) == []
    with pytest.raises(KeyError):
        main.store.get(session_id)
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401  # a token for nobody


def test_logout_is_the_browser_forgetting_its_token(client):
    """Tokens are stateless, so the route is a 204 and nothing else; say so out loud."""
    token, _ = guest(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 200


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


def test_an_expired_token_is_refused(client):
    token, user = guest(client)
    old = auth.make_token(user["id"], now=time.time() - auth.settings.token_ttl_s - 1)
    assert client.get("/api/auth/me", headers=bearer(old)).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 200


def test_changing_one_character_of_any_part_of_a_token_refuses_it(client):
    token, _ = guest(client)
    parts = token.split(".")
    assert len(parts) == 3, "a token is <user id>.<expiry>.<signature>"
    for i in range(3):
        forged = ".".join([*parts[:i], flip(parts[i]), *parts[i + 1:]])
        res = client.get("/api/auth/me", headers=bearer(forged))
        assert res.status_code == 401 and res.json()["message"] and res.json()["next_step"]
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 200


@pytest.mark.parametrize("header", [{}, bearer(""), bearer("nonsense"), bearer("a.b.c"),
                                    # a byte no browser would send, which latin-1 decodes to a
                                    # non-ASCII character: comparing that as a string would crash
                                    {"Authorization": b"Bearer a.b.\xfc"},
                                    bearer("." * 400), bearer("x" * 5000),
                                    {"Authorization": "Basic abc"}, {"Authorization": "sometoken"}])
def test_anything_that_is_not_a_bearer_token_is_a_401(client, header):
    res = client.get("/api/auth/me", headers=header)
    assert res.status_code == 401 and res.json()["next_step"]


def test_a_token_signed_with_another_secret_is_refused(client, monkeypatch):
    real = auth._SECRET
    monkeypatch.setattr(auth, "_SECRET", b"somebody else's key")
    forged = auth.make_token("whoever")
    monkeypatch.setattr(auth, "_SECRET", real)
    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401


# --------------------------------------------------------------------------
# Whose session is this?
# --------------------------------------------------------------------------

# Every route under /api/sessions, as the browser calls it. `s` is the session id.
SESSION_ROUTES = [
    lambda c, s, h: c.get(f"/api/sessions/{s}/catalog", headers=h),
    lambda c, s, h: c.post(f"/api/sessions/{s}/files", headers=h,
                           files=[("files", ("e.csv", EMPLOYEES.encode("utf-8"), "text/csv"))]),
    lambda c, s, h: c.post(f"/api/sessions/{s}/sample", headers=h),
    lambda c, s, h: c.get(f"/api/sessions/{s}/tables/employees/preview", headers=h),
    lambda c, s, h: c.patch(f"/api/sessions/{s}/links/whatever", json={"status": "active"}, headers=h),
    lambda c, s, h: c.put(f"/api/sessions/{s}/glossary", json=[], headers=h),
    lambda c, s, h: c.post(f"/api/sessions/{s}/ask", json={"question": "hi"}, headers=h),
    lambda c, s, h: c.delete(f"/api/sessions/{s}", headers=h),
    # the three that never call a model belong to their owner just the same
    lambda c, s, h: c.get(f"/api/sessions/{s}/dashboard", headers=h),
    lambda c, s, h: c.get(f"/api/sessions/{s}/analyses", headers=h),
    lambda c, s, h: c.post(f"/api/sessions/{s}/analyses/run", headers=h,
                           json={"kind": "distribution", "inputs": {"measure": "employees.ctc"}}),
]


@pytest.mark.parametrize("call", SESSION_ROUTES)
def test_a_session_route_without_a_token_is_a_401(client, call):
    token, _ = guest(client)
    res = call(client, session_of(client, token), {})
    assert res.status_code == 401 and res.json()["message"] and res.json()["next_step"]


def test_creating_a_session_needs_a_token_too(client):
    assert client.post("/api/sessions").status_code == 401


@pytest.mark.parametrize("call", SESSION_ROUTES)
def test_another_users_token_cannot_reach_your_session(client, call):
    """404, not 403: a guessed session id learns nothing about whether it exists, and the app
    already handles this one sentence in one place (the project goes read-only and asks for the
    files again), which is exactly the right thing to show somebody holding a stale session."""
    owner, _ = guest(client)
    session_id = session_of(client, owner)
    assert upload(client, session_id, owner).status_code == 200

    stranger, _ = guest(client)
    res = call(client, session_id, bearer(stranger))
    assert res.status_code == 404
    assert res.json() == {"message": "Your session has expired.", "next_step": "Please upload your files again."}
    assert client.get(f"/api/sessions/{session_id}/catalog", headers=bearer(owner)).status_code == 200


def test_the_public_routes_stay_public(client):
    """The trust report, the sample files and the health check are the signed-out pages."""
    for path in ("/healthz", "/api/sample/files", "/api/sample/download"):
        assert client.get(path).status_code == 200, path
    assert client.get("/api/eval/report").status_code in (200, 404)  # 404 only when none was generated


def test_the_thirty_second_path_is_never_refused(client):
    """Land, "try the live demo", the sample company, the overview: no sign-up anywhere in it."""
    token, user = guest(client)
    assert user["kind"] == "guest"
    session_id = session_of(client, token)
    assert client.post(f"/api/sessions/{session_id}/sample", headers=bearer(token)).status_code == 200
    overview = client.get(f"/api/sessions/{session_id}/dashboard", headers=bearer(token))
    assert overview.status_code == 200 and overview.json()["sections"]


# --------------------------------------------------------------------------
# Limits, hashing, and what never gets written down
# --------------------------------------------------------------------------


def test_signup_login_and_guest_creation_are_limited_per_address(client):
    """The three ways in are the three cheapest things to hammer, so each has its own count."""
    for i in range(limits_module.SIGNUPS_PER_HOUR):
        assert signup(client, email=f"a{i}@example.com").status_code == 200
    refused = signup(client, email="one-too-many@example.com")
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) > 0
    assert refused.json()["message"] and refused.json()["next_step"]

    for _ in range(limits_module.LOGINS_PER_WINDOW):
        assert login(client, email="a0@example.com").status_code == 200
    assert login(client, email="a0@example.com").status_code == 429

    for _ in range(limits_module.GUESTS_PER_HOUR):
        assert client.post("/api/auth/guest").status_code == 200
    last = client.post("/api/auth/guest")
    assert last.status_code == 429 and int(last.headers["retry-after"]) > 0


def test_passwords_are_stored_as_scrypt_with_the_parameters_we_publish(client):
    """The README claims scrypt with these parameters; this is the line that makes it true."""
    assert signup(client, email="one@example.com").status_code == 200
    assert signup(client, email="two@example.com").status_code == 200
    with auth._db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY email").fetchall()
    one, two = rows
    assert len(one["salt"]) == 16 and one["salt"] != two["salt"]  # a salt per user, not per app
    assert one["password_hash"] != two["password_hash"]  # so the same password stores differently
    assert one["password_hash"] == hashlib.scrypt(PASSWORD.encode("utf-8"), salt=one["salt"],
                                                  n=2**14, r=8, p=1, dklen=32)
    assert PASSWORD not in str(tuple(one))


def test_the_users_file_is_readable_by_this_server_and_nobody_else(monkeypatch, tmp_path):
    """It holds every hash and salt and lives in /tmp by default, where sqlite3 would leave it
    0644 inside a 0755 folder: on a shared host that is the users table handed to any account."""
    monkeypatch.setattr(auth, "settings",
                        dataclasses.replace(auth.settings, auth_db_path=tmp_path / "work" / "users.db"))
    monkeypatch.setattr(main, "limits", Limits(main.settings))
    client = TestClient(main.app)
    assert client.post("/api/auth/guest").status_code == 200

    path = auth.settings.auth_db_path
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700  # the folder _db created itself


def test_a_short_auth_secret_is_warned_about_and_never_printed(monkeypatch, caplog):
    """`AUTH_SECRET=verity` is worse than no AUTH_SECRET: it is guessable offline from one
    token, and then anyone can sign a token for any user id."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(auth, "settings", dataclasses.replace(auth.settings, auth_secret="verity"))
    assert auth._start_secret() == b"verity"
    written = "\n".join(record.getMessage() for record in caplog.records)
    assert "AUTH_SECRET" in written and str(auth.MIN_SECRET_CHARS) in written
    assert "verity" not in written  # the warning names the rule, never the value

    caplog.clear()
    long_enough = "a" * auth.MIN_SECRET_CHARS
    monkeypatch.setattr(auth, "settings", dataclasses.replace(auth.settings, auth_secret=long_enough))
    assert auth._start_secret() == long_enough.encode("utf-8")
    assert caplog.records == []


def test_a_guest_older_than_a_token_is_pruned_at_start_up(client):
    """Their token cannot be live, sessions die with the process, so the row owns nothing."""
    _, old = guest(client)
    _, fresh = guest(client)
    with auth._db() as conn:
        conn.execute("UPDATE users SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (old["id"],))
    auth.prune_guests()
    assert auth.find(old["id"]) is None and auth.find(fresh["id"]) is not None


def test_a_member_is_never_pruned(client):
    user = signup(client).json()["user"]
    with auth._db() as conn:
        conn.execute("UPDATE users SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (user["id"],))
    auth.prune_guests()
    assert auth.find(user["id"]) is not None


def test_no_password_hash_or_token_ever_reaches_a_log_or_an_error_body(client, caplog):
    caplog.set_level(logging.DEBUG)
    token, _ = guest(client)
    answers = [signup(client), signup(client), login(client), login(client, password="wrong"),
               login(client, email="nobody@example.com"), signup(client, password="short"),
               signup(client, email="bad"), client.get("/api/auth/me", headers=bearer(token)),
               client.get("/api/auth/me", headers=bearer(flip(token))),
               client.patch("/api/auth/me", json={"name": "Asha"}, headers=bearer(token)),
               client.post("/api/sessions", headers=bearer(token))]
    with auth._db() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE email = ?", (EMAIL,)).fetchone()[0]

    written = "\n".join(f"{record.getMessage()} {record.args}" for record in caplog.records)
    for secret in (PASSWORD, token, stored.hex(), auth._SECRET.decode("utf-8", "replace")):
        assert secret not in written
        assert [res for res in answers if secret in res.text] == []
