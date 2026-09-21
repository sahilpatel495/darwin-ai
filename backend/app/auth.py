"""Accounts: who a request belongs to, in the smallest form that is still honest.

A guest is a real user with no email, created by one POST and no form, so "try the live demo"
stays a single click and the demo's data and limits still have an owner. Signing up later
upgrades that same row in place, so the id survives and with it their projects (the browser
stores them under `darwinlens.projects.v1.<user id>`) and their already-loaded files.

Why a server-side account at all when DECISIONS 18 keeps projects in the browser: the server
still holds uploaded HR rows in memory, and "whose session is this?" has to have an answer
before two people share a link. That is the whole job here — not user management.

The honest limits, which belong in the README beside the other ones:
- Users live in one SQLite file (`settings.auth_db_path`), a connection per call. The table is
  a few hundred rows of names and hashes; a pool would be a moving part with nothing to gain.
  WAL stays off because a free host wipes the disk on redeploy, so its side files would buy a
  durability nobody gets — and one writer at a time is the truth about this server anyway.
- Passwords: `hashlib.scrypt` (n=2**14, r=8, p=1, 16-byte per-user salt, 32-byte key) compared
  with `hmac.compare_digest`. Memory-hard, in the standard library, no dependency.
- Tokens: `<user id>.<expiry>.<HMAC-SHA256 of the first two>`, signed with AUTH_SECRET, good for
  `settings.token_ttl_s` (a week). Stateless, so signing out is the browser forgetting its
  token: `POST /api/auth/logout` answers 204 and nothing else, and a stolen token stays valid
  until it expires. Because the upgrade keeps the id, that covers a guest token too: whoever
  held it before the sign-up still holds a live token for the member account afterwards. There
  is no way to plant one (the token is read from this origin's localStorage and never from a
  URL), and anyone who could plant one could read the new token as well, so this is the same
  accepted risk and not a second one. The upgrade path for both is a revocation table keyed by
  user id, which is also what would let `logout` mean something.
- No email verification and no password reset: there is no mail service to send either.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.contracts import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    ProfileUpdate,
    SignupRequest,
    User,
)
from app.limits import Limits

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}  # ~16 MB and ~60 ms per hash on the free instance
SALT_BYTES = 16
# One sentence for every sign-in failure. A different message for an unknown email would turn
# this route into a "does this person have an account here?" oracle, which is exactly the fact
# an HR tool should not confirm to a stranger.
_WRONG = "That email and password do not match."
# Deliberately loose: something@something.something with no spaces. The only real test of an
# address is sending mail to it, and there is no mail service, so a stricter pattern would only
# turn away people with unusual but valid addresses.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
# What a body that the contract refuses says, per field. FastAPI's own {"detail": [...]} would
# reach the browser as "something went wrong on our side", and a short password is a normal
# event, not a bug report.
_RULES = {
    "email": "That does not look like an email address.",
    "password": "A password needs at least 8 characters.",
    "name": "Please enter the name you want to be called.",
}


MIN_SECRET_CHARS = 32  # 128 bits written as hex: below that, forging a token is a search


def _start_secret() -> bytes:
    """The token signing key. Without AUTH_SECRET a random one is made here, which is safe but
    forgetful: it lives in this process only, so every restart invalidates every token. One
    warning at start-up, never the value itself, and never its length either.

    A short AUTH_SECRET is worse than no AUTH_SECRET: `AUTH_SECRET=darwinlens` is a key an attacker
    can guess offline from one token they hold, and then sign a token for any user id they like.
    Warned about rather than refused, because a server that will not start is how a deploy at
    4pm on a Friday ends with the variable deleted instead of lengthened.
    """
    if settings.auth_secret:
        if len(settings.auth_secret) < MIN_SECRET_CHARS:
            log.warning("AUTH_SECRET is shorter than %d characters. A short signing key can be "
                        "guessed from one sign-in token, which lets anyone sign in as anyone. "
                        "Replace it with the output of: python -c \"import secrets; "
                        "print(secrets.token_hex(32))\"", MIN_SECRET_CHARS)
        return settings.auth_secret.encode("utf-8")
    log.warning("AUTH_SECRET is not set, so a random signing key was generated for this process. "
                "Everyone signed in now will be signed out when the server restarts. "
                "Set AUTH_SECRET to keep sign-ins across restarts.")
    return secrets.token_hex(32).encode("utf-8")


_SECRET = _start_secret()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    email         TEXT UNIQUE,   -- lower-cased; NULL for guests, and SQLite lets NULLs repeat
    name          TEXT NOT NULL,
    role          TEXT,
    password_hash BLOB,          -- NULL for guests: there is nothing to sign in to
    salt          BLOB,
    created_at    TEXT NOT NULL, -- ISO 8601 UTC, which sorts as text, so pruning is one WHERE
    onboarded     INTEGER NOT NULL DEFAULT 0
)
"""


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    """One connection, opened and closed around one request's worth of work.

    The schema statement runs every time: it is `IF NOT EXISTS`, costs a microsecond, and saves
    an initialisation step that could be forgotten on a host that wipes the disk. Committing on
    the way out means an exception leaves the file exactly as it was.

    The file holds every password hash and salt and lives under WORK_DIR, which is `/tmp/darwinlens`
    by default. sqlite3 and mkdir would leave that 0644 inside a 0755 directory, which hands the
    whole users table to any other account on a shared host, so both are narrowed here.
    ponytail: the chmod is every call (one cheap syscall) rather than only on creation, and a
    WORK_DIR somebody else already made stays as they made it; the file is what carries hashes.
    """
    path = settings.auth_db_path
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    # 30 s, not the default 5: on the free host a tenth of a CPU is shared with whatever file is
    # being read in, and a writer that gives up early is a 500 for somebody's first click.
    conn = sqlite3.connect(path, timeout=30)
    path.chmod(0o600)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _problem(status: int, message: str, next_step: str) -> Exception:
    """The app's human error, {message, next_step}. `app.main` imports this module, so its
    exception is imported here at call time rather than at the top — the same cycle
    `app.insights.routes` documents, and the same one-line fix."""
    from app.main import ApiProblem

    return ApiProblem(status, message, next_step)


def _limiter(request: Request) -> tuple[Limits, str]:
    """The app's one limiter and the address to count against, read at call time (the same
    import cycle as above, and what lets a test swap the limiter)."""
    from app import main

    return main.limits, main._ip(request)


def _body[T: BaseModel](raw: dict, model: type[T], next_step: str) -> T:
    """One of the contract models, or the app's two sentences naming the field that is wrong."""
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        field = str(e.errors()[0]["loc"][-1])
        raise _problem(422, _RULES.get(field, "Some of those details are missing or too long."),
                       next_step) from None


def _name(value: str) -> str:
    """Trimmed, and never empty: the contract's minimum length counts a space, and a name made
    of spaces would leave the app greeting somebody as "What do you want to know, ?"."""
    trimmed = value.strip()
    if not trimmed:
        raise _problem(422, _RULES["name"], "Enter a name and try again.")
    return trimmed


def _stamp(when: float | None = None) -> str:
    return datetime.fromtimestamp(when if when is not None else time.time(), UTC).isoformat(timespec="seconds")


def _user(row: sqlite3.Row) -> User:
    return User(id=row["id"], kind=row["kind"], name=row["name"], email=row["email"],
                role=row["role"], created_at=row["created_at"], onboarded=bool(row["onboarded"]))


def _fetch(conn: sqlite3.Connection, user_id: str) -> User:
    return _user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, **SCRYPT)


# A hash of a throwaway salt, so a sign-in for an email nobody has costs the same time as a real
# one. Computed once at import, because the point is that login always pays for exactly one hash.
_NO_SUCH_USER = (b"\0" * SALT_BYTES, _hash("", b"\0" * SALT_BYTES))


def _insert(conn: sqlite3.Connection, kind: str, name: str, email: str | None,
            role: str | None, password: str | None) -> str:
    """One new row; returns its id. Raises sqlite3.IntegrityError when the email is taken."""
    user_id = secrets.token_hex(16)
    salt = secrets.token_bytes(SALT_BYTES) if password else None
    conn.execute(
        "INSERT INTO users (id, kind, email, name, role, password_hash, salt, created_at, onboarded)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
        (user_id, kind, email, name, role, _hash(password, salt) if password else None, salt, _stamp()))
    return user_id


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


def _sign(body: str) -> str:
    return hmac.new(_SECRET, body.encode("utf-8"), hashlib.sha256).hexdigest()


def make_token(user_id: str, now: float | None = None) -> str:
    """`<user id>.<expiry>.<signature>`. The expiry is inside the signed part, so a client that
    edits it invalidates the whole token rather than extending it."""
    body = f"{user_id}.{int((now if now is not None else time.time()) + settings.token_ttl_s)}"
    return f"{body}.{_sign(body)}"


def find(user_id: str) -> User | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user(row) if row else None


def user_for_token(token: str) -> User | None:
    """The signed-in user, or None for anything that is not a live signature over a live user.

    In this order: signature (constant time), then expiry, then the row. Signature first means a
    tampered token never reaches the database, and the row last means deleting an account really
    does sign it out — the token stays well-formed and stops working the moment the row is gone.
    """
    user_id, _, rest = token.partition(".")
    expires, _, signature = rest.partition(".")
    # Compared as bytes: `compare_digest` refuses two strings when either holds a non-ASCII
    # character, and a header is whatever the client typed, so that would be a 500 for a forgery.
    if not signature or not hmac.compare_digest(_sign(f"{user_id}.{expires}").encode("ascii"),
                                                signature.encode("utf-8")):
        return None
    if not expires.isdigit() or int(expires) < time.time():
        return None
    return find(user_id)


def signed_in(request: Request) -> User | None:
    """Whoever this request carries a live token for, or None. Sign-up reads it this way,
    because arriving with no token at all is the normal case there."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return user_for_token(token.strip()) if scheme.lower() == "bearer" and token.strip() else None


def current_user(request: Request) -> User:
    """The dependency every route that touches somebody's data goes through.

    401 rather than 403: the browser's answer to both is the same (get a guest token, or sign
    in), and the message says so in the app's two sentences.
    """
    user = signed_in(request)
    if user is None:
        raise _problem(401, "You are not signed in, or your sign-in has expired.",
                       "Reload the page to start again, or sign in.")
    return user


def prune_guests() -> None:
    """Drop guests whose token can no longer be live. Called once at start-up.

    Their sessions died with the previous process (sessions are in memory), and their token
    expired with `token_ttl_s`, so the row is unreachable by anyone — keeping it would only grow
    the file. Members are never touched. Housekeeping never stops a server from starting, hence
    the catch: a locked or unreadable file is a problem for the first real request, not for boot.
    """
    try:
        with _db() as conn:
            conn.execute("DELETE FROM users WHERE kind = 'guest' AND created_at < ?",
                         (_stamp(time.time() - settings.token_ttl_s),))
    except sqlite3.Error:
        log.warning("could not prune expired guest accounts", exc_info=True)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.post("/guest", response_model=AuthResponse)
def create_guest(request: Request) -> AuthResponse:
    """An account with no sign-up, so the public demo needs no form and still has an owner."""
    limits, ip = _limiter(request)
    limits.new_guest(ip)
    with _db() as conn:
        user = _fetch(conn, _insert(conn, kind="guest", name="Guest", email=None, role=None, password=None))
    return AuthResponse(token=make_token(user.id), user=user)


@router.post("/signup", response_model=AuthResponse)
def signup(body: dict, request: Request) -> AuthResponse:
    """Create a member — or turn the caller's own guest into one, keeping their id.

    The body arrives as a dict and is validated here so that a password one character short is
    answered in the app's sentences like every other refusal (see `_body`).
    """
    limits, ip = _limiter(request)
    limits.signup(ip)
    form = _body(body, SignupRequest, "Check the details and try again.")
    email, name = form.email.strip().lower(), _name(form.name)
    if not _EMAIL.match(email):
        raise _problem(422, _RULES["email"], "Check it and try again.")

    guest = _caller_guest(request)
    with _db() as conn:
        # An email already taken raises out of here before the commit, so a guest whose sign-up
        # is refused is still a guest with their files, not a half-written member.
        try:
            upgraded = conn.execute(
                "UPDATE users SET kind = 'member', email = ?, name = ?, role = ?, password_hash = ?, salt = ?"
                " WHERE id = ? AND kind = 'guest'",
                (email, name, form.role, *_credentials(form.password), guest.id)
            ).rowcount if guest else 0
            user_id = guest.id if upgraded else _insert(
                conn, kind="member", name=name, email=email, role=form.role, password=form.password)
        except sqlite3.IntegrityError:
            raise _problem(409, "There is already an account with that email address.",
                           "Sign in instead, or use another email address.") from None
        user = _fetch(conn, user_id)
    return AuthResponse(token=make_token(user.id), user=user)


def _credentials(password: str) -> tuple[bytes, bytes]:
    salt = secrets.token_bytes(SALT_BYTES)
    return _hash(password, salt), salt


def _caller_guest(request: Request) -> User | None:
    """The guest whose token came with this sign-up, if any. A member signing up again gets a
    second account rather than overwriting the one they are already signed in to."""
    user = signed_in(request)
    return user if user and user.kind == "guest" else None


@router.post("/login", response_model=AuthResponse)
def login(body: dict, request: Request) -> AuthResponse:
    """One sentence for every failure, and the same work whether or not the email exists.

    An email nobody has is charged a hash against a throwaway salt, so the answer takes as long
    as a wrong password does; without it the response time alone would list our customers.
    """
    limits, ip = _limiter(request)
    limits.login(ip)
    form = _body(body, LoginRequest, "Check them and try again.")
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ? AND kind = 'member'",
                           (form.email.strip().lower(),)).fetchone()
    salt, expected = (row["salt"], row["password_hash"]) if row else _NO_SUCH_USER
    if not hmac.compare_digest(_hash(form.password, salt), expected) or row is None:
        raise _problem(401, _WRONG, "Check them and try again, or create an account.")
    return AuthResponse(token=make_token(row["id"]), user=_user(row))


@router.get("/me", response_model=MeResponse)
def me(request: Request, user: User = Depends(current_user)) -> MeResponse:
    """Who you are and how much of the demo's allowance you have spent."""
    limits, _ = _limiter(request)
    return MeResponse(user=user, usage=limits.usage(user.id))


@router.patch("/me", response_model=User)
def update_me(body: dict, user: User = Depends(current_user)) -> User:
    """The three things a person can change about themselves. A field left out is left alone.

    The column names in the statement are the contract model's own field names, never keys from
    the request, so the values are the only thing that travels as parameters.
    """
    form = _body(body, ProfileUpdate, "Change it and try again.")
    updates = {k: v for k, v in form.model_dump(exclude_unset=True).items() if v is not None or k == "role"}
    if "name" in updates:
        updates["name"] = _name(updates["name"])
    if "onboarded" in updates:
        updates["onboarded"] = int(updates["onboarded"])
    if not updates:
        return user
    with _db() as conn:
        conn.execute(f"UPDATE users SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
                     (*updates.values(), user.id))
        return _fetch(conn, user.id)


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(current_user)) -> None:
    """Everything this server holds about them: the row, and any files still loaded in memory.

    The sessions go through `app.main`'s own delete, so the overview computed from those files
    goes with them; their token keeps its shape but stops working, because `user_for_token`
    looks the row up on every request.
    """
    from app import main

    for session_id in main.store.ids_for_user(user.id):
        main._drop_session(session_id)
    with _db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user.id,))


@router.post("/logout", status_code=204)
def logout() -> None:
    """Nothing to do here: tokens are stateless, so signing out is the browser forgetting its
    token. The route exists so the client has one call to make, and so that this file says out
    loud that a copied token stays valid until it expires."""
