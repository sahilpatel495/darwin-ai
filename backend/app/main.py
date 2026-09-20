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
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.contracts import AskRequest, Catalog, ErrorResponse, LinkUpdate, Metric, StepEvent
from app.ingest import IngestError
from app.llm.client import PoolClient
from app.query.pipeline import answer_question
from app.sessions import Session, SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("verity")

ROOT = Path(__file__).resolve().parents[2]
MAX_FILES_PER_UPLOAD = 10
HEARTBEAT_S = 15

app = FastAPI(title="Verity", docs_url=None, redoc_url=None)
store = SessionStore()
llm = PoolClient()


class ApiProblem(Exception):
    def __init__(self, status: int, message: str, next_step: str):
        self.status, self.message, self.next_step = status, message, next_step


def _problem(status: int, message: str, next_step: str) -> JSONResponse:
    return JSONResponse(ErrorResponse(message=message, next_step=next_step).model_dump(), status_code=status)


@app.exception_handler(ApiProblem)
async def _on_problem(_: Request, e: ApiProblem) -> JSONResponse:
    return _problem(e.status, e.message, e.next_step)


@app.exception_handler(Exception)
async def _on_crash(_: Request, e: Exception) -> JSONResponse:
    log.exception("unhandled error", exc_info=e)  # the trace stays in the server log
    return _problem(500, "Something went wrong on our side.", "Please try again. If it keeps happening, reload the page.")


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


def _session(session_id: str) -> Session:
    try:
        return store.get(session_id)
    except KeyError:
        raise ApiProblem(404, "Your session has expired.", "Please upload your files again.") from None


# ponytail: in-process sliding window per client IP. Fine for one worker; put the limiter in
# the proxy or Redis when there is more than one.
_asks: dict[str, deque[float]] = defaultdict(deque)
_asks_lock = threading.Lock()


def _check_rate(request: Request) -> None:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    now = time.time()
    with _asks_lock:
        window = _asks[ip]
        while window and now - window[0] > 3600:
            window.popleft()
        if len(window) >= settings.asks_per_ip_per_hour:
            raise ApiProblem(429, "You have asked a lot of questions in the last hour.",
                             "This demo runs on free model quotas. Please try again a little later.")
        window.append(now)


# --------------------------------------------------------------------------
# Sessions and data
# --------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions")
def create_session() -> dict[str, str]:
    return {"session_id": store.create().id}


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
                                 "Upload a smaller extract, or run Verity locally where the limit is configurable.")
            out.write(chunk)
    return target, name


@app.post("/api/sessions/{session_id}/files", response_model=Catalog)
async def upload_files(session_id: str, files: list[UploadFile] = File(...)) -> Catalog:
    session = _session(session_id)
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise ApiProblem(413, f"That is more than {MAX_FILES_PER_UPLOAD} files at once.", "Upload them in smaller batches.")
    folder = settings.work_dir / session.id / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        saved = [await run_in_threadpool(_save_upload, f, folder) for f in files]
        return await run_in_threadpool(session.add_files, saved)
    except IngestError as e:
        raise ApiProblem(422, str(e), "Fix or remove that file and upload again. The other files were not loaded.") from None
    finally:
        shutil.rmtree(folder, ignore_errors=True)  # cleaned data lives in DuckDB; raw uploads are not kept


@app.post("/api/sessions/{session_id}/sample", response_model=Catalog)
async def load_sample(session_id: str) -> Catalog:
    return await run_in_threadpool(_session(session_id).load_sample)


@app.get("/api/sessions/{session_id}/catalog", response_model=Catalog)
def get_catalog(session_id: str) -> Catalog:
    return _session(session_id).catalog


@app.patch("/api/sessions/{session_id}/links/{link_id:path}", response_model=Catalog)
async def update_link(session_id: str, link_id: str, body: LinkUpdate) -> Catalog:
    session = _session(session_id)
    try:
        return await run_in_threadpool(session.set_link_status, link_id, body.status)
    except KeyError:
        raise ApiProblem(404, "That link no longer exists.", "Reload the page to see the current links.") from None


@app.put("/api/sessions/{session_id}/glossary", response_model=Catalog)
async def put_glossary(session_id: str, metrics: list[Metric]) -> Catalog:
    if len(metrics) > 50:
        raise ApiProblem(413, "That is more than 50 glossary entries.", "Remove some entries and save again.")
    return await run_in_threadpool(_session(session_id).set_glossary, metrics)


# --------------------------------------------------------------------------
# Asking
# --------------------------------------------------------------------------


def _sse(event: str, payload: str) -> str:
    return f"event: {event}\ndata: {payload}\n\n"


@app.post("/api/sessions/{session_id}/ask")
async def ask(session_id: str, body: AskRequest, request: Request) -> StreamingResponse:
    session = _session(session_id)
    _check_rate(request)
    events: queue.Queue[tuple[str, str]] = queue.Queue()

    def work() -> None:
        def emit(step: StepEvent) -> None:
            events.put(("step", step.model_dump_json()))
        try:
            events.put(("answer", answer_question(session, body, llm, emit).model_dump_json()))
        except Exception:  # answer_question never raises by contract; this guards the contract
            log.exception("ask failed")
            events.put(("error", ErrorResponse(message="Something went wrong while answering that.",
                                               next_step="Please ask again.").model_dump_json()))

    threading.Thread(target=work, daemon=True).start()

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


_DIST = ROOT / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """Serve real files from dist/, and index.html for everything else (client-side routes)."""
        candidate = (_DIST / path).resolve()
        if path and candidate.is_file() and _DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
