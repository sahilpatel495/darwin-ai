"""HTTP layer: thin routes over sessions and the query pipeline.

Everything interesting happens elsewhere. This file's job is the boundary: size caps, rate
limits, human error messages, and streaming pipeline steps to the browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import shutil
import threading
import time
import uuid
from contextlib import ExitStack
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app import auth
from app.config import settings
from app.contracts import (
    AskRequest,
    Catalog,
    ErrorResponse,
    LinkUpdate,
    Metric,
    ResultTable,
    StepEvent,
    User,
)
from app.ingest import IngestError
from app.insights import dashboard
from app.insights.routes import router as insights_router
from app.limits import LimitExceeded, Limits, client_ip
from app.llm.client import PoolClient
from app.mcp_server import router as mcp_router
from app.query.executor import QueryError, QueryTimeout
from app.query.pipeline import answer_question
from app.sample_files import router as sample_router
from app.sessions import Session, SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("darwinlens")

ROOT = Path(__file__).resolve().parents[2]
MAX_FILES_PER_UPLOAD = 10
HEARTBEAT_S = 15

app = FastAPI(title="DarwinLens", docs_url=None, redoc_url=None)
app.include_router(sample_router)  # before the SPA catch-all below, which would swallow /api/sample/*
store = SessionStore()
llm = PoolClient()
limits = Limits(settings)
app.include_router(insights_router)  # the no-model routes; also before the SPA catch-all
app.include_router(auth.router)  # accounts; also before the SPA catch-all
app.include_router(mcp_router)  # MCP over the same engine (docs/MCP.md); also before the SPA catch-all
auth.prune_guests()  # start-up housekeeping: a guest whose token has expired owns nothing


class ApiProblem(Exception):
    def __init__(self, status: int, message: str, next_step: str):
        self.status, self.message, self.next_step = status, message, next_step


def _problem(status: int, message: str, next_step: str) -> JSONResponse:
    return JSONResponse(ErrorResponse(message=message, next_step=next_step).model_dump(), status_code=status)


@app.exception_handler(ApiProblem)
async def _on_problem(_: Request, e: ApiProblem) -> JSONResponse:
    return _problem(e.status, e.message, e.next_step)


@app.exception_handler(LimitExceeded)
async def _on_limit(_: Request, e: LimitExceeded) -> JSONResponse:
    """A per-user limit was hit (app.limits): the usual two sentences, plus Retry-After in
    seconds for clients that back off by themselves."""
    response = _problem(429, e.message, e.next_step)
    response.headers["Retry-After"] = str(e.retry_after_s)
    return response


@app.exception_handler(RequestValidationError)
async def _on_bad_body(_: Request, __: RequestValidationError) -> JSONResponse:
    """A body, path or query value FastAPI itself refused, in the app's two sentences.

    Its own answer is `{"detail": [...]}`, which `api.ts` reads as no message at all and shows
    as "something went wrong on our side" — a client mistake dressed as a server fault. It also
    echoes the offending input back, and nothing else here reflects a request at the visitor.
    The routes that can say something more useful already do: they take the body as a dict and
    name the field themselves (`app.auth._body`, `_RULES`). This is the floor under them, and
    under every route that takes a contract model directly.
    """
    return _problem(422, "Some of those details are missing or in the wrong format.",
                    "Check what you sent, then try again.")


@app.exception_handler(Exception)
async def _on_crash(_: Request, e: Exception) -> JSONResponse:
    log.exception("unhandled error", exc_info=e)  # the trace stays in the server log
    return _problem(500, "Something went wrong on our side.", "Please try again. If it keeps happening, reload the page.")


@app.middleware("http")
async def _limit_body(request: Request, call_next):
    """Starlette writes a multipart body to temp files BEFORE the route runs, so the per-file
    cap in _save_upload comes too late to protect the disk. Check the declared size first.
    ponytail: a chunked body with no Content-Length skips this; the per-file cap still applies."""
    declared = request.headers.get("content-length", "")
    if request.method in ("POST", "PUT", "PATCH") and declared.isdigit():
        is_upload = request.url.path.endswith("/files")
        limit_mb = settings.max_upload_mb * MAX_FILES_PER_UPLOAD + 1 if is_upload else 1
        if int(declared) > limit_mb * 1024 * 1024:
            return _problem(413, "That request is larger than this server accepts.",
                            f"Keep each file under {settings.max_upload_mb} MB and upload at most {MAX_FILES_PER_UPLOAD} at a time.")
    return await call_next(request)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")  # answers and previews hold HR data
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


def _session(session_id: str, user: User) -> Session:
    """This user's session, or the one sentence the app has for "that data is not here".

    Somebody else's session answers 404, not 403, for two reasons: a guessed id learns nothing
    about whether it exists, and the browser already handles this exact sentence in one place
    (the project goes read-only and asks for the files again), which is the right thing to show
    anyone holding a session they cannot open — expired, deleted or never theirs.
    """
    try:
        session = store.get(session_id)
    except KeyError:
        session = None
    if session is None or session.user_id != user.id:
        raise ApiProblem(404, "Your session has expired.", "Please upload your files again.")
    return session


def _drop_session(session_id: str) -> None:
    """Everything this server holds for one session: the tables, the history, the temp folder,
    and the overview computed from them. Deleting an account does this for each of theirs."""
    store.delete(session_id)
    dashboard.clear_cache(session_id)


def _ip(request: Request) -> str:
    """One half of who the limits count against (app.auth's user id is the other): the address
    a request came from, which is what a new guest account cannot change."""
    return client_ip(request.headers.get("x-forwarded-for", ""),
                     request.client.host if request.client else None,
                     settings.trusted_proxy_hops)


# --------------------------------------------------------------------------
# Sessions and data
# --------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions")
def create_session(request: Request, user: User = Depends(auth.current_user)) -> dict[str, str]:
    """A place to put files, owned by whoever asked for it (a guest counts)."""
    limits.new_session(_ip(request))
    return {"session_id": store.create(user.id).id}


def _save_upload(upload: UploadFile, folder: Path) -> tuple[Path, str]:
    """Stream to disk with a hard cap, so a huge upload never sits in memory."""
    name = Path(upload.filename or "upload").name  # drop any client-supplied directories
    target = folder / f"{uuid.uuid4().hex}{Path(name).suffix.lower()}"
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    with target.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                out.close()
                target.unlink(missing_ok=True)
                raise ApiProblem(413, f"{name} is larger than the {settings.max_upload_mb} MB limit.",
                                 "Upload a smaller extract, or run DarwinLens locally where the limit is configurable.")
            out.write(chunk)
    return target, name


@app.post("/api/sessions/{session_id}/files", response_model=Catalog)
async def upload_files(session_id: str, request: Request, files: list[UploadFile] = File(...),
                       user: User = Depends(auth.current_user)) -> Catalog:
    session = _session(session_id, user)
    # ponytail: FastAPI has already received the request body when this runs, so the limit
    # saves the expensive part (reading the file in), not bandwidth. Refuse at the proxy for that.
    limits.upload(_ip(request))
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise ApiProblem(413, f"That is more than {MAX_FILES_PER_UPLOAD} files at once.", "Upload them in smaller batches.")
    folder = settings.work_dir / session.id / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        saved = [await run_in_threadpool(_save_upload, f, folder) for f in files]
        with limits.ingest():  # one file read at a time on this host: LimitExceeded -> 429
            return await run_in_threadpool(session.add_files, saved)
    except IngestError as e:
        raise ApiProblem(422, str(e), "Fix or remove that file and upload again. The other files were not loaded.") from None
    finally:
        shutil.rmtree(folder, ignore_errors=True)  # cleaned data lives in DuckDB; raw uploads are not kept


@app.post("/api/sessions/{session_id}/sample", response_model=Catalog)
async def load_sample(session_id: str, request: Request, user: User = Depends(auth.current_user)) -> Catalog:
    session = _session(session_id, user)
    limits.upload(_ip(request))  # the sample is read in exactly like an upload, so it costs the same
    try:
        with limits.ingest():  # the sample is read in like any upload, so it queues for nothing either
            return await run_in_threadpool(session.load_sample)
    except IngestError as e:
        raise ApiProblem(422, str(e), "Upload your own CSV or Excel files instead.") from None


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user: User = Depends(auth.current_user)) -> None:
    """"New session" in the UI: the tables, the history and the temp folder are dropped now,
    not when the TTL gets round to it."""
    _session(session_id, user)  # somebody else's session is not theirs to delete
    _drop_session(session_id)


@app.get("/api/sessions/{session_id}/catalog", response_model=Catalog)
def get_catalog(session_id: str, user: User = Depends(auth.current_user)) -> Catalog:
    return _session(session_id, user).catalog


@app.get("/api/sessions/{session_id}/tables/{table_name}/preview", response_model=ResultTable)
async def preview_table(session_id: str, table_name: str, limit: int = 50,
                        user: User = Depends(auth.current_user)) -> ResultTable:
    """The first rows of one uploaded table, for the data owner's own browser. This route
    never touches the LLM client: rows are shown to the person who uploaded them, not to a model."""
    try:
        return await run_in_threadpool(_session(session_id, user).preview, table_name, limit)
    except (QueryError, QueryTimeout):
        # DuckDB's message can quote a cell value ("Could not convert string 'Asha Rao'"), so it
        # stays in the server log and the browser gets a sentence, like every other failure here.
        log.exception("preview failed")
        raise ApiProblem(500, "That table could not be read back.",
                         "Reload the page. If it keeps happening, upload the file again.") from None
    except KeyError:
        raise ApiProblem(404, "That table is no longer loaded.", "Reload the page to see your current files.") from None


@app.patch("/api/sessions/{session_id}/links/{link_id:path}", response_model=Catalog)
async def update_link(session_id: str, link_id: str, body: LinkUpdate,
                      user: User = Depends(auth.current_user)) -> Catalog:
    session = _session(session_id, user)
    try:
        return await run_in_threadpool(session.set_link_status, link_id, body.status)
    except KeyError:
        raise ApiProblem(404, "That link no longer exists.", "Reload the page to see the current links.") from None
    except ValueError as e:  # these messages are written for users
        raise ApiProblem(422, str(e), "Change it and try again.") from None


@app.put("/api/sessions/{session_id}/glossary", response_model=Catalog)
async def put_glossary(session_id: str, metrics: list[Metric],
                       user: User = Depends(auth.current_user)) -> Catalog:
    if len(metrics) > 50:
        raise ApiProblem(413, "That is more than 50 glossary entries.", "Remove some entries and save again.")
    try:
        return await run_in_threadpool(_session(session_id, user).set_glossary, metrics)
    except ValueError as e:  # these messages are written for users
        raise ApiProblem(422, str(e), "Change the entry and save again.") from None


# --------------------------------------------------------------------------
# Asking
# --------------------------------------------------------------------------


def _sse(event: str, payload: str) -> str:
    return f"event: {event}\ndata: {payload}\n\n"


@app.post("/api/sessions/{session_id}/ask")
async def ask(session_id: str, body: AskRequest, request: Request,
              user: User = Depends(auth.current_user)) -> StreamingResponse:
    session = _session(session_id, user)
    ip = _ip(request)
    # The question is admitted here, so a refusal is a plain 429 before any streaming starts,
    # but its concurrency slot has to be freed by the worker thread. ExitStack is the standard
    # way to enter a `with` in one place and leave it in another.
    slot = ExitStack()
    slot.enter_context(limits.question(ip, session.id, user.id))  # raises LimitExceeded
    events: queue.Queue[tuple[str, str]] = queue.Queue()

    def work() -> None:
        def emit(step: StepEvent) -> None:
            events.put(("step", step.model_dump_json()))
        try:
            # The slot belongs to this thread, not to the connection: if the browser goes away
            # the thread still runs to the end and frees it. It is freed before the last event
            # is sent, so the visitor's next question never races their previous one.
            with slot:
                answer = answer_question(session, body, llm, emit)
                if answer.work.cached:  # served from the shared cache: no model was called
                    limits.refund_question(ip, session.id, user.id)
            final = ("answer", answer.model_dump_json())
        except Exception:  # answer_question never raises by contract; this guards the contract
            log.exception("ask failed")
            final = ("error", ErrorResponse(message="Something went wrong while answering that.",
                                            next_step="Please ask again.").model_dump_json())
        events.put(final)

    try:
        threading.Thread(target=work, daemon=True).start()
    except BaseException:  # no thread, so nobody else would ever free the slot
        slot.close()
        raise

    async def stream():
        last_beat = time.monotonic()
        while True:
            try:
                event, payload = events.get_nowait()
            except queue.Empty:
                if time.monotonic() - last_beat > HEARTBEAT_S:  # keeps proxies from closing an idle stream
                    last_beat = time.monotonic()
                    yield ": ping\n\n"
                await asyncio.sleep(0.05)
                continue
            yield _sse(event, payload)
            if event in ("answer", "error"):
                return

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# --------------------------------------------------------------------------
# Trust report and the single-page app
# --------------------------------------------------------------------------


@app.get("/api/eval/report")
def eval_report() -> JSONResponse:
    path = ROOT / "eval" / "report.json"
    if not path.exists():
        raise ApiProblem(404, "No evaluation report has been generated yet.", "Run `make eval` to create one.")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def unknown_api_path(path: str) -> JSONResponse:
    """Registered last among the API routes, so it only ever sees paths nothing else claimed.

    An unknown API path must never be answered with the web page and a 200 (the UI would try to
    read HTML as data and report a mystery failure), nor with a bare framework 404 that has no
    next step. Lives outside the dist/ block so it holds with or without a built frontend.
    """
    return _problem(404, "This server does not know that request.",
                    "The app and the server are out of step. Restart the server, then reload the page.")


_DIST = ROOT / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Serve real files from dist/, and index.html for everything else (client-side routes)."""
        candidate = (_DIST / path).resolve()
        if path and candidate.is_file() and _DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
