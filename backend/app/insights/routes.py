"""HTTP for the half of the product that never calls a model.

Three routes over `app.insights`: the automatic overview a session gets the moment its files
land, the picker that says what can be asked, and one guided analysis. They run no model and
hold no model client, so they are not counted against the question limits — the budget exists
to protect an API key, and nothing here can spend one. That is also why they live in their own
module: `app.main` is where the token-spending routes are, and the difference should be
visible from the import list rather than from reading every function.

Each route hands the request straight to the engine in a worker thread and turns its two
outcomes into the app's own error shapes: an unknown session is the existing human 404, and a
refusal (a ValueError carrying one sentence written for the analyst) is a 422 carrying that
sentence. Nothing else is caught: a template that cannot run is our bug, and the app's crash
handler already answers those without leaking DuckDB's text, which can quote a cell value.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.insights import analyses, dashboard
from app.insights.models import AnalysisCatalog, AnalysisRequest, Dashboard, InsightTile
from app.sessions import SessionLike

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["insights"])


def _session(session_id: str) -> SessionLike:
    """This session, or the app's human 404 for an expired one.

    `app.main` imports this module, so importing it back at module level would be a cycle;
    the import lives in here instead. That is one line, where a setter called from main would
    be a second edit to a file three other engineers have open, plus a global to initialise and
    a failure mode when nobody calls it. Reading the attribute at call time is also what lets a
    test swap the store.

    It calls main's own lookup rather than `store.get` so the 404 sentence stays one sentence:
    two copies of "Your session has expired." would drift the first time somebody reworded it.
    """
    from app import main

    return main._session(session_id)


@router.get("/dashboard", response_model=Dashboard)
async def get_dashboard(session_id: str) -> Dashboard:
    """Everything we can say about these files without a model: sections of computed tiles.

    The engine caches it per catalog version, so only the first call after an upload runs
    queries; a reload is a dict lookup. In a thread either way, because the first call is a
    dozen DuckDB queries and the event loop has other requests to serve.
    """
    return await run_in_threadpool(dashboard.build, _session(session_id))


@router.get("/analyses", response_model=AnalysisCatalog)
async def get_analyses(session_id: str) -> AnalysisCatalog:
    """The picker: the ten analyses, and which of this session's columns may fill each slot.

    Personal-data and identifier columns are absent from the column list — the engine leaves
    them out, so the UI cannot offer "average employee id by name" in the first place.
    """
    return await run_in_threadpool(analyses.catalog, _session(session_id))


@router.post("/analyses/run", response_model=InsightTile)
async def run_analysis(session_id: str, body: AnalysisRequest) -> InsightTile:
    """One guided analysis: catalog identifiers into SQL, guarded, run, formatted, read out.

    A ValueError here is the engine refusing the request in one sentence aimed at the person
    looking at the picker ("Pick two different groups to compare."), so it is passed through as
    the message; the next step is the same every time because the fix is always the same.
    422 rather than 400: the request is well-formed JSON asking for something the data cannot
    give. `from None` keeps the engine's sentence the whole of the response — the chained
    exception could carry DuckDB's text, and that can quote a cell.
    """
    from app.main import ApiProblem

    session = _session(session_id)
    try:
        return await run_in_threadpool(analyses.run, session, body)
    except ValueError as e:
        raise ApiProblem(422, str(e), "Change the selection and try again.") from None
