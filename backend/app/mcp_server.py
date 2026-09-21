"""MCP over the same engine, so a company's own agents can use DarwinLens as a tool.

Why this exists. A customer that already runs agents does not want another chat window; it
wants its assistant to answer "what did we pay out in March?" with *its own* definition of
gross pay. Everything that makes an answer trustworthy here — the parser guard, DuckDB, the
verification, the glossary — already lives in `app.query` and `app.insights`. The only thing
missing was a door an agent can knock on. This module is that door and nothing else: six tools
mapped onto calls the REST API already makes, and no arithmetic of its own.

What it implements. The request/response half of MCP's Streamable HTTP transport, in the
standard library: `POST /mcp` takes one JSON-RPC 2.0 message (or a batch of them) and answers
`application/json`. Methods: `initialize`, `notifications/initialized`, `ping`, `tools/list`,
`tools/call`. Every call carries the same bearer token the browser uses (`app.auth`), and a
session that is not the caller's is refused exactly as the REST API refuses it.

The product's promises still hold on this side of the door, which is the point of routing
through the engine rather than round it:

- the model never computes and never sees a row. DuckDB computes, `app.insights.facts` writes
  the sentence, and what a tool returns is the display string the browser would have shown;
- `ask` is charged to the caller's question allowance exactly like `POST /api/sessions/{id}/ask`;
  the five no-model tools spend no tokens and so are charged nothing;
- personal-data columns are masked in returned rows unless the caller asks for them, and
  `describe_data` names those columns without ever showing a value (`docs/MCP.md` says why).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import auth
from app.contracts import Answer, AskRequest, Catalog, ErrorResponse, ResultTable, User
from app.insights import analyses, dashboard
from app.insights.models import AnalysisRequest, InsightTile
from app.limits import LimitExceeded
from app.query.guard import validate_sql
from app.query.pipeline import _pii_result_columns, answer_question

router = APIRouter(tags=["mcp"])

# Newest first. A client asking for one of these gets it back; anything else is answered with
# ours, which is what the spec tells a server to do when it cannot speak the client's version.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST = PROTOCOL_VERSIONS[0]
SERVER_INFO = {"name": "darwinlens", "title": "DarwinLens", "version": "0.1.0"}

# A tool result is read by a model, not exported: 50 rows is enough to reason over and small
# enough that a whole conversation of them still fits a context window.
MAX_ROWS = 50
HIDDEN = "[hidden: personal data]"
MAX_QUESTION_CHARS = 500  # app.contracts.AskRequest's own cap, said here in a sentence
_ECHO = 60  # how much of a client's own string is quoted back in an error

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602
# The spec reserves -32000..-32099 for a server's own errors: used here only inside a batch,
# where a refusal that would otherwise be an HTTP status has to travel as one reply (_handle_in_batch).
SERVER_ERROR = -32000

INSTRUCTIONS = (
    "DarwinLens answers questions about a customer's own HR spreadsheets. Call load_sample_data "
    "(or reuse a session_id from the web app), then describe_data to learn the columns, the "
    "links between files and the customer's glossary. get_overview, list_analyses and "
    "run_analysis are computed without any model; ask runs the full question pipeline. Every "
    "number comes back already formatted for India (₹54.67 Cr, 12.4%) — quote it as given "
    "rather than recomputing it, and cite the SQL when the analyst asks how it was worked out."
)


def _not_json(constant: str) -> None:
    """`json` accepts NaN, Infinity and -Infinity by default; JSON itself does not, and the
    encoder on the way out refuses them, so an `id` of NaN would be a 500 on the reply. Refused
    at the door instead, where it is the -32700 it always was."""
    raise ValueError(f"{constant} is not valid JSON")


class _RpcError(Exception):
    """A JSON-RPC level failure: the message never reached a tool."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class _Caller:
    """Who is asking, in the two terms every limit in this app is counted against."""

    user: User
    ip: str


# --------------------------------------------------------------------------
# The tools. Descriptions are written for a model deciding which one to call.
# --------------------------------------------------------------------------

_SESSION = {"session_id": {"type": "string",
                           "description": "The session_id returned by load_sample_data."}}
_PERSONAL = {"include_personal_data": {
    "type": "boolean", "default": False,
    "description": "Return values from personal-data columns (names, emails, PAN, phone) "
                   "instead of masking them. Only set this when the analyst has asked for "
                   "them by name and is entitled to see them."}}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "load_sample_data",
        "title": "Load the sample company",
        "description": "Create a DarwinLens session owned by you and load the bundled sample "
                       "Indian company (500 employees, a payroll register, attendance, reviews "
                       "and sales). Returns the session_id every other tool needs, plus the "
                       "tables, the links found between files and any combined views. Use it to "
                       "try DarwinLens when the analyst has not uploaded their own files.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "describe_data",
        "title": "Describe the loaded data",
        "description": "What is in a session: every table with its row count, every column with "
                       "its type and its HR role, the links between files, the customer's "
                       "glossary of vetted metric definitions, and which columns hold personal "
                       "data. Column names only — no cell values. Call this before ask or "
                       "run_analysis so you use the customer's own wording.",
        "inputSchema": _schema(dict(_SESSION), ["session_id"]),
    },
    {
        "name": "get_overview",
        "title": "Get the computed overview",
        "description": "The automatic dashboard: headcount, attrition, pay, attendance, "
                       "performance and data-quality tiles, each as a title, a computed "
                       "statement and short insight lines. No model is involved and no tokens "
                       "are spent, so this is the cheapest way to learn what the data says.",
        "inputSchema": _schema(dict(_SESSION), ["session_id"]),
    },
    {
        "name": "list_analyses",
        "title": "List the guided analyses",
        "description": "The guided analyses that can be run without a model (break down, trend, "
                       "top and bottom, distribution, share, two-way table, correlation, change "
                       "between periods, unusual values, compare two groups), the inputs each "
                       "one takes, and the columns of this session that may fill each input. "
                       "Prefer these over ask when one of them fits the question exactly.",
        "inputSchema": _schema(dict(_SESSION), ["session_id"]),
    },
    {
        "name": "run_analysis",
        "title": "Run one guided analysis",
        "description": "Run one analysis from list_analyses and get the computed tile: the "
                       "statement, insight lines, caveats, the SQL that produced it and the "
                       "first 50 rows. Deterministic and free: no model writes this SQL. Inputs "
                       "and options must be column references and choices taken from "
                       "list_analyses; anything else is refused with a sentence saying what to "
                       "change.",
        "inputSchema": _schema({
            **_SESSION,
            "kind": {"type": "string",
                     "description": "An analysis key from list_analyses, e.g. \"breakdown\"."},
            "inputs": {"type": "object", "additionalProperties": {"type": "string"},
                       "description": "Input key to column reference, e.g. "
                                      "{\"measure\": \"employees.ctc\", \"by\": \"employees.department\"}."},
            "options": {"type": "object", "additionalProperties": {"type": "string"},
                        "description": "Option key to choice, e.g. {\"aggregate\": \"average\"}. "
                                       "Omitted options take the first choice."},
            **_PERSONAL,
        }, ["session_id", "kind", "inputs"]),
    },
    {
        "name": "ask",
        "title": "Ask a question in plain English",
        "description": "Ask anything about the loaded data in plain English. The question is "
                       "turned into SQL, guarded, run on DuckDB, verified and read back: you get "
                       "the answer sentence, a confidence level with its reasons, caveats, "
                       "insight lines, the SQL and the first 50 rows. When a word such as "
                       "\"salary\" could mean more than one column you get clarification "
                       "options instead — pick one and ask again with clarification set. When "
                       "the data cannot answer it you get a refusal naming what is missing. "
                       "This is the only tool that calls a model, and it is charged to the "
                       "caller's question allowance.",
        "inputSchema": _schema({
            **_SESSION,
            "question": {"type": "string",
                         "description": f"The analyst's question, at most {MAX_QUESTION_CHARS} characters."},
            "clarification": {"type": "object", "additionalProperties": {"type": "string"},
                              "description": "An earlier clarification answered: term to column "
                                             "reference, e.g. {\"salary\": \"employees.ctc\"}."},
            **_PERSONAL,
        }, ["session_id", "question"]),
    },
]


# --------------------------------------------------------------------------
# Arguments, which arrive from somebody else's agent and are therefore checked
# --------------------------------------------------------------------------


def _text(args: dict, name: str, max_chars: int = 200) -> str:
    """A required string argument, or one sentence naming what is missing."""
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'This tool needs "{name}" as text. Add it and call the tool again.')
    if len(value) > max_chars:
        raise ValueError(f'"{name}" can be at most {max_chars} characters. Shorten it and call the tool again.')
    return value.strip()


def _mapping(args: dict, name: str) -> dict[str, str]:
    """An object of string-to-string, defaulting to empty. The engine validates the contents;
    this only settles the shape, so a list or a nested object fails here rather than deeper in."""
    value = args.get(name) or {}
    if not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values()):
        raise ValueError(f'"{name}" must be an object whose values are text, '
                         f'for example {{"measure": "employees.ctc"}}.')
    return value


def _flag(args: dict, name: str) -> bool:
    """A boolean argument, and nothing that merely looks like one.

    `bool(value)` would read the *string* "false" as True, and a stringified boolean is the
    commonest wrong-typed argument a model emits. On this particular flag that is not a typo,
    it is a disclosure: `include_personal_data` is the switch that stops names, emails and PAN
    being masked, so a caller that did not ask for them in the JSON type the schema publishes
    is told to fix the call rather than guessed at. Absent stays absent, which is masked.
    """
    value = args.get(name, False)
    if value is not True and value is not False:  # not isinstance: 1 and "true" are not consent
        raise ValueError(f'"{name}" must be true or false, written as a JSON boolean and not '
                         'as text. Leave it out to keep personal data masked.')
    return value


def _session(caller: _Caller, args: dict):
    """This caller's session, or the app's own human 404 for one that is expired or not theirs.

    `app.main` imports this module, so the import lives in here rather than at the top — the
    same cycle `app.insights.routes` documents, and the same one-line fix. Calling main's own
    lookup is also what keeps the refusal identical to the REST API's, which is what the
    brief asks for: an agent holding a stranger's session id learns nothing new.
    """
    from app import main

    return main._session(_text(args, "session_id"), caller.user)


# --------------------------------------------------------------------------
# Shaping engine output for a model
# --------------------------------------------------------------------------


def _shape(catalog: Catalog) -> dict[str, Any]:
    """Tables, links and combined views, in the words an agent will have to use again."""
    return {
        "tables": [{"name": t.name, "source_file": t.source_file, "sheet": t.sheet,
                    "rows": t.row_count, "columns": len(t.columns), "combined_view": t.is_view}
                   for t in catalog.tables],
        "links": [{"id": r.id, "from": f"{r.left_table}.{r.left_column}",
                   "to": f"{r.right_table}.{r.right_column}",
                   "cardinality": r.cardinality, "status": r.status}
                  for r in catalog.relationships],
        "combined_views": [{"view": u.view_name, "tables": u.tables, "status": u.status}
                           for u in catalog.unions],
    }


def _shape_text(shape: dict[str, Any]) -> str:
    tables = ", ".join(f"{t['name']} ({t['rows']:,} rows, {t['columns']} columns)"
                       for t in shape["tables"]) or "none"
    links = "; ".join(f"{link['from']} -> {link['to']} ({link['cardinality']})"
                      for link in shape["links"] if link["status"] == "active") or "none"
    views = ", ".join(v["view"] for v in shape["combined_views"] if v["status"] == "active") or "none"
    return f"Tables: {tables}.\nActive links: {links}.\nCombined views: {views}."


def _personal_columns(sql: str | None, table: ResultTable, catalog: Catalog) -> set[str]:
    """Which result columns may carry personal data, by the engine's own rule.

    Reused from the query pipeline rather than matched on column names, because a name proves
    nothing: `SELECT name AS department` would walk straight through a name match. The rule is
    blunt on purpose — if the query touched a personal-data column at all, every text column in
    the result is treated as personal — and it is the same rule that decides what the narrator
    is allowed to see, so the browser and an agent hide the same cells.
    """
    if not sql:
        return set()
    try:
        return _pii_result_columns(validate_sql(sql, catalog), table, catalog)
    except ValueError:  # a query we cannot re-read is one we cannot vouch for
        return set(table.columns)


def _table(table: ResultTable | None, sql: str | None, catalog: Catalog,
           include_personal_data: bool) -> dict[str, Any] | None:
    """The first rows, with personal-data columns masked unless the caller asked for them."""
    if table is None:
        return None
    hidden = set() if include_personal_data else _personal_columns(sql, table, catalog)
    masked = [i for i, name in enumerate(table.columns) if name in hidden]

    def rows(source: list[list[Any]]) -> list[list[Any]]:
        return [[HIDDEN if i in masked else value for i, value in enumerate(row)]
                for row in source[:MAX_ROWS]]

    shown = rows(table.rows)
    return {"columns": table.columns, "rows": shown, "display": rows(table.display),
            "row_count": table.row_count, "returned_rows": len(shown),
            "truncated": table.truncated or table.row_count > len(shown),
            "hidden_columns": sorted(hidden)}


def _tile(tile: InsightTile, catalog: Catalog, include_personal_data: bool) -> dict[str, Any]:
    return {"title": tile.title, "kind": tile.kind, "statement": tile.statement,
            "insights": tile.insights, "caveats": tile.caveats, "sql": tile.sql,
            "tables_used": tile.tables_used,
            "table": _table(tile.table, tile.sql, catalog, include_personal_data)}


def _lines(*groups: tuple[str, list[str]]) -> list[str]:
    return [f"{label}: {item}" for label, items in groups for item in items]


def _tile_text(tile: InsightTile) -> str:
    return "\n".join([f"{tile.title}: {tile.statement}",
                      *_lines(("Insight", tile.insights), ("Caveat", tile.caveats))])


# --------------------------------------------------------------------------
# The six tools
# --------------------------------------------------------------------------


def _load_sample_data(caller: _Caller, args: dict) -> tuple[str, dict[str, Any]]:
    """A session of the caller's own, with the bundled sample company in it.

    Charged the same as the REST route it stands in for: a new session and an upload both cost
    a visitor something real (a DuckDB connection, a temp folder, and the memory peak of
    reading a workbook), and an agent is no cheaper to serve than a browser.
    """
    from app import main

    main.limits.new_session(caller.ip)
    session = main.store.create(caller.user.id)
    main.limits.upload(caller.ip)
    with main.limits.ingest(wait_s=main.INGEST_WAIT_S):  # one read at a time; already in a worker thread
        catalog = session.load_sample()
    shape = _shape(catalog)
    return (f"Loaded the sample company into session {session.id}.\n{_shape_text(shape)}",
            {"session_id": session.id, **shape})


def _describe_data(caller: _Caller, args: dict) -> tuple[str, dict[str, Any]]:
    """Types, roles, links, glossary, and which columns are personal data — names only."""
    session = _session(caller, args)
    catalog = session.catalog
    shape = _shape(catalog)
    tables = [{"name": t.name, "source_file": t.source_file, "sheet": t.sheet, "rows": t.row_count,
               "columns": [{"name": c.name, "label": c.label, "type": c.type, "role": c.role,
                            "personal_data": c.pii is not None} for c in t.columns],
               "combined_view": t.is_view}
              for t in catalog.tables]
    personal = [f"{t.name}.{c.name}" for t in catalog.tables for c in t.columns if c.pii]
    structured = {
        "session_id": session.id, "tables": tables, "links": shape["links"],
        "combined_views": shape["combined_views"],
        "glossary": [{"key": m.key, "name": m.name, "definition": m.definition,
                      "synonyms": m.synonyms} for m in catalog.glossary],
        "personal_data_columns": personal,
    }
    privacy = (f"Personal data in {len(personal)} columns ({', '.join(personal)}); "
               "their values never reach a model and are masked in returned rows."
               if personal else "No personal-data columns were detected.")
    return f"{_shape_text(shape)}\n{privacy}", structured


def _get_overview(caller: _Caller, args: dict) -> tuple[str, dict[str, Any]]:
    """The automatic dashboard, as title + statement + insight lines. No model anywhere."""
    session = _session(caller, args)
    board = dashboard.build(session)
    sections = [{"title": s.title,
                 "tiles": [{"id": t.id, "title": t.title, "statement": t.statement,
                            "insights": t.insights} for t in s.tiles]}
                for s in board.sections]
    text = "\n".join(
        "\n".join([f"{section['title']}", *(f"  {t['title']}: {t['statement']}"
                                            + "".join(f"\n    - {line}" for line in t["insights"])
                                            for t in section["tiles"])])
        for section in sections)
    return (text or "There is nothing to show yet: this session has no data loaded.",
            {"session_id": session.id, "sections": sections})


def _list_analyses(caller: _Caller, args: dict) -> tuple[str, dict[str, Any]]:
    """The guided analyses and the columns each input accepts."""
    session = _session(caller, args)
    catalog = analyses.catalog(session)
    structured = {
        "session_id": session.id,
        "kinds": [{"key": k.key, "name": k.name, "description": k.description, "example": k.example,
                   "inputs": [{"key": i.key, "label": i.label, "accepts": i.accepts,
                               "optional": i.optional} for i in k.inputs],
                   "options": [{"key": o.key, "label": o.label, "choices": o.choices}
                               for o in k.options]}
                  for k in catalog.kinds],
        # `values` is the column's own short list of groups, which the compare analysis needs.
        # The profiler never fills it for a personal-data column, and column_kind keeps those
        # columns out of this list altogether, so nothing here can be a person.
        "columns": [{"ref": c.ref, "label": c.label, "table": c.table_label, "kind": c.kind,
                     "values": c.values} for c in catalog.columns],
    }
    text = "\n".join([*(f"{k['key']}: {k['description']} e.g. {k['example']}"
                        for k in structured["kinds"]),
                      "Columns: " + ", ".join(f"{c['ref']} ({c['kind']})"
                                              for c in structured["columns"])])
    return text, structured


def _run_analysis(caller: _Caller, args: dict) -> tuple[str, dict[str, Any]]:
    """One guided analysis: catalog identifiers into SQL, guarded, run, formatted, read out."""
    personal = _flag(args, "include_personal_data")  # checked before any work is done
    session = _session(caller, args)
    request = AnalysisRequest(kind=_text(args, "kind"), inputs=_mapping(args, "inputs"),
                              options=_mapping(args, "options"))
    tile = analyses.run(session, request)  # ValueError here is the engine's own sentence
    return _tile_text(tile), {"session_id": session.id,
                              **_tile(tile, session.catalog, personal)}


def _ask(caller: _Caller, args: dict) -> tuple[str, dict[str, Any]]:
    """The full question pipeline, on the caller's own question allowance.

    The limiter is entered exactly as `app.main.ask` enters it — the same windows, the same
    refund when the answer turns out to have come from the shared cache — so an agent and a
    browser tab draw on one allowance and neither can be used to get round the other.
    A `LimitExceeded` is left to travel: `app.main` turns it into the same 429 with a
    Retry-After header that the REST route answers with.
    """
    from app import main

    # Every argument is settled before the allowance is entered: a call this server is going to
    # refuse must not cost the caller a question first.
    personal = _flag(args, "include_personal_data")
    session = _session(caller, args)
    request = AskRequest(question=_text(args, "question", MAX_QUESTION_CHARS),
                         clarification=_mapping(args, "clarification") or None)
    with main.limits.question(caller.ip, session.id, caller.user.id):
        answer = answer_question(session, request, main.llm, lambda _step: None)
        if answer.work.cached:  # served from the shared cache: no model was called
            main.limits.refund_question(caller.ip, session.id, caller.user.id)
    structured = _answer(answer, session.catalog, personal)
    return _answer_text(structured), {"session_id": session.id, **structured}


def _answer(answer: Answer, catalog: Catalog, include_personal_data: bool) -> dict[str, Any]:
    clarification = answer.clarification
    return {
        "kind": answer.kind,
        "answer": answer.text,
        "confidence": ({"level": answer.confidence.level, "reasons": answer.confidence.reasons}
                       if answer.confidence else None),
        "insights": answer.insights,
        "caveats": answer.work.caveats,
        "assumptions": answer.work.assumptions,
        "sql": answer.work.sql,
        "table": _table(answer.table, answer.work.sql, catalog, include_personal_data),
        "clarification": ({"term": clarification.term, "question": clarification.question,
                           "options": [{"label": o.label, "value": o.value}
                                       for o in clarification.options]}
                          if clarification else None),
        "missing": answer.missing,
        "cached": answer.work.cached,
    }


def _answer_text(answered: dict[str, Any]) -> str:
    lines = [answered["answer"]]
    lines += _lines(("Insight", answered["insights"]), ("Caveat", answered["caveats"]))
    if confidence := answered["confidence"]:
        lines.append(f"Confidence: {confidence['level']} ({'; '.join(confidence['reasons'])})")
    if clarification := answered["clarification"]:
        lines.append(f"{clarification['question']} Options: "
                     + " | ".join(f"{o['label']} -> {o['value']}" for o in clarification["options"]))
    if answered["missing"]:
        lines.append(f"Missing: {answered['missing']}")
    if answered["sql"]:
        lines.append(f"SQL:\n{answered['sql']}")
    return "\n".join(lines)


_TOOL_FUNCTIONS: dict[str, Callable[[_Caller, dict], tuple[str, dict[str, Any]]]] = {
    "load_sample_data": _load_sample_data,
    "describe_data": _describe_data,
    "get_overview": _get_overview,
    "list_analyses": _list_analyses,
    "run_analysis": _run_analysis,
    "ask": _ask,
}


# --------------------------------------------------------------------------
# JSON-RPC
# --------------------------------------------------------------------------


def _initialize(params: dict) -> dict[str, Any]:
    asked = params.get("protocolVersion")
    return {"protocolVersion": asked if asked in PROTOCOL_VERSIONS else LATEST,
            "capabilities": {"tools": {}},  # no resources, no prompts, no listChanged
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS}


async def _tools_call(params: dict, caller: _Caller) -> dict[str, Any]:
    """Run one tool. An engine refusal is a tool result, never a protocol error.

    The difference matters to the agent on the other end: `-32602` means "your message was
    wrong, fix the call", while `isError` means "the call was fine and the answer is no" —
    which is the one thing this product exists to say out loud. Everything the app already
    knows how to answer travels on past here: a session that is not the caller's is the human
    404, a spent allowance is the 429, and a bug is the app's own 500.
    """
    name = params.get("name")
    function = _TOOL_FUNCTIONS.get(name) if isinstance(name, str) else None
    if function is None:
        raise _RpcError(INVALID_PARAMS, f"There is no tool called {str(name)[:_ECHO]!r}. "
                                        "Call tools/list for the six this server offers.")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise _RpcError(INVALID_PARAMS, '"arguments" must be an object.')
    try:
        text, structured = await run_in_threadpool(function, caller, arguments)
    except ValueError as e:  # the engine refusing in one sentence written for the analyst
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    return {"content": [{"type": "text", "text": text}], "structuredContent": structured}


async def _dispatch(method: str, params: dict, caller: _Caller) -> dict[str, Any]:
    if method == "initialize":
        return _initialize(params)
    if method in ("ping", "notifications/initialized"):
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}  # no cursor: six tools fit in one page
    if method == "tools/call":
        return await _tools_call(params, caller)
    raise _RpcError(METHOD_NOT_FOUND, f"This server does not implement {method[:_ECHO]!r}. It "
                                      "offers initialize, ping, tools/list and tools/call.")


def _valid_id(value: Any) -> bool:
    """JSON-RPC allows a String, a Number or Null for `id`, and nothing else.

    Enforced rather than tolerated, because the id is the one part of a request that travels
    back out verbatim: accepting an object or an array would echo whatever structure the caller
    sent, and a deep enough one is a recursion the JSON encoder pays for on the way out.
    """
    return value is None or isinstance(value, str | int | float)


def _failure(ident: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": ident, "error": error}


async def _handle(message: Any, caller: _Caller) -> dict[str, Any] | None:
    """One JSON-RPC message in, one reply out — or None for a notification, which gets none."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" \
            or not isinstance(message.get("method"), str):
        ident = message.get("id") if isinstance(message, dict) else None
        return _failure(ident if _valid_id(ident) else None, INVALID_REQUEST,
                        'A message must be a JSON-RPC 2.0 object: {"jsonrpc": "2.0", "id": 1, '
                        '"method": "tools/list"}.')
    if "id" in message and not _valid_id(message["id"]):
        return _failure(None, INVALID_REQUEST, '"id" must be a string, a number or null.')
    if "id" not in message:
        # A notification is one-way by definition, and nothing this server accepts as one has
        # an effect to run: `notifications/initialized` only says the handshake is over.
        return None
    params = message.get("params") or {}
    if not isinstance(params, dict):
        return _failure(message["id"], INVALID_PARAMS, '"params" must be an object.')
    try:
        return {"jsonrpc": "2.0", "id": message["id"],
                "result": await _dispatch(message["method"], params, caller)}
    except _RpcError as e:
        return _failure(message["id"], e.code, e.message)


async def _handle_in_batch(message: Any, caller: _Caller) -> dict[str, Any] | None:
    """`_handle`, except that one message's refusal cannot take the other replies down with it.

    On its own, a message gets the REST API's own status — 404 for a session that is not the
    caller's, 429 for a spent allowance — because there the HTTP response *is* that one answer,
    and the brief asks for those two refusals to be indistinguishable from the REST API's. In a
    batch there is no status that is true of every reply, and letting one refusal become the
    whole response throws away answers the earlier messages were already charged for: a batch of
    two questions that trips the allowance on the second used to bill the first and return
    nothing. So here the same sentence travels as this message's own error, with the status it
    would have had in `data` for a client that wants to branch on it.
    """
    from app import main

    try:
        return await _handle(message, caller)
    except main.ApiProblem as e:
        refusal, extra = f"{e.message} {e.next_step}", {"httpStatus": e.status}
    except LimitExceeded as e:
        refusal, extra = f"{e.message} {e.next_step}", {"httpStatus": 429, "retryAfterSeconds": e.retry_after_s}
    ident = message.get("id") if isinstance(message, dict) else None
    return _failure(ident if _valid_id(ident) else None, SERVER_ERROR, refusal, extra)


def _json(payload: Any, status: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    # /mcp is outside /api/, so it misses main's blanket no-store for API paths, and a tool
    # result holds the customer's HR numbers. Said here instead of widening that middleware,
    # which is a file three other people have open.
    return JSONResponse(payload, status_code=status,
                        headers={"Cache-Control": "no-store", **(headers or {})})


def _caller(request: Request) -> _Caller | None:
    from app import main

    user = auth.signed_in(request)
    return _Caller(user, main._ip(request)) if user else None


@router.post("/mcp")
async def mcp(request: Request) -> Response:
    """One JSON-RPC 2.0 message, or a batch of them, answered as application/json.

    A batch that holds nothing but notifications is answered 202 with no body, as is a single
    notification; anything else comes back as one object or one array of objects, in the order
    the requests arrived.
    """
    caller = _caller(request)
    if caller is None:
        return _unauthorized()
    try:
        message = json.loads(await request.body(), parse_constant=_not_json)
    except (ValueError, RecursionError):
        # RecursionError, not just ValueError: `json` walks a nested array with the interpreter
        # stack, so a body that is 40 kB of "[" exhausts it. Under the 1 MB cap main.py puts on
        # a non-upload body, so it arrives, and it is a client mistake either way — answering
        # -32700 keeps it one, instead of the app's own 500.
        return _json(_failure(None, PARSE_ERROR, "That body is not valid JSON, or is nested too "
                                                 "deeply. Send one JSON-RPC 2.0 message, or a "
                                                 "JSON array of them."))
    if isinstance(message, list):
        if not message:
            return _json(_failure(None, INVALID_REQUEST, "A batch must hold at least one message."))
        replies = [reply for reply in [await _handle_in_batch(item, caller) for item in message]
                   if reply is not None]
        return _json(replies) if replies else Response(status_code=202)
    reply = await _handle(message, caller)
    return _json(reply) if reply is not None else Response(status_code=202)


@router.get("/mcp")
async def mcp_stream() -> Response:
    """405: this prototype has no server-initiated stream.

    Streamable HTTP lets a client hold a GET open so the server can push notifications, log
    lines and sampling requests of its own. Nothing here pushes: every tool answers inside its
    own POST, and the one slow call (a question, a few seconds) is worth no progress bar an
    agent would read. Saying 405 out loud is better than a silent hang, so a client that tries
    falls back to POST-only straight away.

    # ponytail: no GET stream and no Mcp-Session-Id. Ceiling: a server cannot push progress or
    # ask the caller's model for a sampling turn. Upgrade path: return an SSE stream here keyed
    # by that header and feed it the StepEvents app.main already streams to the browser.
    """
    return _json(ErrorResponse(
        message="This MCP endpoint does not open a server-initiated stream.",
        next_step="POST your JSON-RPC messages to this same URL instead.").model_dump(),
        status=405, headers={"Allow": "POST"})


def _unauthorized() -> JSONResponse:
    """401 with a challenge, because an MCP client is a program: it needs to be told which
    scheme to use, not shown a sign-in page."""
    return _json(ErrorResponse(
        message="This endpoint needs a DarwinLens token.",
        next_step="POST /api/auth/guest to get one, then send it as "
                  "`Authorization: Bearer <token>` on every /mcp call.").model_dump(),
        status=401, headers={"WWW-Authenticate": 'Bearer realm="DarwinLens"'})
