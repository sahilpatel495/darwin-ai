"""The query pipeline: one question in, one verifiable answer out.

Reading order is the product thesis. The model appears twice (write SQL, phrase the result)
and never touches data; everything between those two calls is deterministic and checked.

    cache -> ambiguity -> generate -> [guard -> execute -> fan-out + period checks] (repair <= 2)
          -> caveats -> present -> narrate || cross-check -> confidence
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.catalog.glossary import find_ambiguity, match_metrics
from app.catalog.prompt_context import build_metric_context, build_schema_context
from app.config import settings
from app.contracts import (
    Answer,
    AskRequest,
    Attempt,
    Catalog,
    Clarification,
    ClarifyOption,
    CrossCheck,
    StepEvent,
    Work,
)
from app.insights.facts import insight_lines
from app.llm.client import LLMClient, LLMUnavailable
from app.query.confidence import Signals, score
from app.query.executor import ExecResult, QueryError, QueryTimeout, execute
from app.query.generator import Generation, RepairContext, generate
from app.query.guard import GuardedQuery, GuardError, validate_sql
from app.query.narrator import Narration, narrate, template_answer
from app.query.presentation import build_table, choose_chart, column_kinds
from app.query.verify import fan_out_risks, null_caveats, period_risks, results_equivalent
from app.sessions import SessionLike, Turn

log = logging.getLogger(__name__)

MAX_REPAIRS = 2
Emit = Callable[[StepEvent], None]

# Sent back when the model asks for a choice the analyst has already made. The choice itself is
# already in the prompt (generator._clarification_lines), so nothing user-supplied is repeated.
CHOICE_ALREADY_MADE = ("You asked the analyst to choose a column, but they already chose: their "
                       "choice is listed above. Use it and write the SQL. Do not ask again.")

# Answers for identical data + semantics + question are shared across sessions, so the sample
# dataset's starter questions can be pre-warmed after a deploy and cost no tokens afterwards.
# ponytail: process-local LRU; move to Redis if this ever runs on more than one worker.
_SHARED_CACHE: OrderedDict[str, Answer] = OrderedDict()
_SHARED_CACHE_MAX = 200
_CACHEABLE_ROWS = 500  # bigger results are cheap to recompute and expensive to hold


class _Trace:
    """Collects what the user will see under "How I got this" while the pipeline runs."""

    def __init__(self, emit: Emit):
        self.work = Work()
        self._emit = emit
        self._t0 = time.perf_counter()

    def step(self, stage: str, status: str, detail: str = "") -> None:
        self._emit(StepEvent(stage=stage, status=status, detail=detail))

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.work.timings_ms[name] = int((now - self._t0) * 1000)
        self._t0 = now


def _cache_key(catalog: Catalog, req: AskRequest, history: list[Turn]) -> str:
    """Same data, same user decisions, same question, same conversational context."""
    semantics = {
        "data": catalog.fingerprint,
        "links": sorted((r.id, r.status) for r in catalog.relationships),
        "unions": sorted((u.id, u.status) for u in catalog.unions),
        "glossary": [m.model_dump() for m in catalog.glossary],
        "question": " ".join(req.question.lower().split()),
        "clarification": sorted((req.clarification or {}).items()),
        "context": history[-1].sql if history else "",  # follow-ups depend on the last turn
    }
    return hashlib.sha256(json.dumps(semantics, sort_keys=True).encode()).hexdigest()


def clear_answer_cache() -> None:
    """For the eval runner and tests: every question must be answered fresh."""
    _SHARED_CACHE.clear()


def answer_question(session: SessionLike, req: AskRequest, llm: LLMClient, emit: Emit) -> Answer:
    """Never raises: every failure becomes an Answer the UI can show with a next step."""
    req = _trusted(req, session.catalog)
    key = _cache_key(session.catalog, req, session.history)
    if cached := _SHARED_CACHE.get(key):
        _SHARED_CACHE.move_to_end(key)
        hit = cached.model_copy(deep=True, update={"id": uuid.uuid4().hex})
        hit.work.cached = True
        emit(StepEvent(stage="done", status="ok", detail="Answered from cache (same data, same question)"))
        _remember(session, hit)
        return hit

    try:
        answer = _run(session, req, llm, _Trace(emit))
    except LLMUnavailable as e:  # its message is a complete sentence for users; never contains keys
        answer = Answer(id=uuid.uuid4().hex, kind="error", question=req.question,
                        text=str(e) or "The AI models are busy right now. Please try again in a minute.",
                        retry_after_s=getattr(e, "retry_after_s", None))
    except ValueError:
        log.warning("unreadable model reply for question %r", req.question)
        answer = _error(req, "The AI model gave a reply I could not read.", "Ask again, or rephrase the question.")
    except Exception:  # last line of defence: the user gets a sentence, the log gets the trace
        log.exception("pipeline failed for question %r", req.question)
        answer = _error(req, "Something went wrong while answering that.",
                        "Try rephrasing the question. If it keeps happening, re-upload the file.")

    small = answer.table is None or len(answer.table.rows) <= _CACHEABLE_ROWS
    if answer.kind in ("answer", "refusal", "meta") and small:
        _SHARED_CACHE[key] = answer
        while len(_SHARED_CACHE) > _SHARED_CACHE_MAX:
            _SHARED_CACHE.popitem(last=False)
    _remember(session, answer)
    emit(StepEvent(stage="done", status="ok" if answer.kind != "error" else "failed"))
    return answer


def _trusted(req: AskRequest, catalog: Catalog) -> AskRequest:
    """`clarification` comes from the browser and ends up in a prompt, so only entries that
    name a real column of this session survive."""
    if not req.clarification:
        return req
    real = {f"{t.name}.{c.name}" for t in catalog.tables for c in t.columns}
    kept = {term[:40]: ref for term, ref in req.clarification.items() if ref in real}
    return req.model_copy(update={"clarification": kept or None})


def _remember(session: SessionLike, answer: Answer) -> None:
    """Follow-ups need the last question and SQL. Result rows are never kept in history."""
    if answer.kind == "answer" and answer.work.sql:
        session.history.append(Turn(answer.question, answer.work.interpretation, answer.work.sql))
        del session.history[:-10]


def _count(n: int, noun: str) -> str:
    """"1 table", "4 columns". Counts are pluralised where they are written, because "1 table(s)"
    in a step line is the kind of small wrongness that makes a careful analyst distrust the rest."""
    return f"{n:,} {noun}" + ("" if n == 1 else "s")


def _error(req: AskRequest, message: str, next_step: str) -> Answer:
    return Answer(id=uuid.uuid4().hex, kind="error", question=req.question, text=f"{message} {next_step}")


# --------------------------------------------------------------------------


def _run(session: SessionLike, req: AskRequest, llm: LLMClient, trace: _Trace) -> Answer:
    catalog = session.catalog
    if not catalog.tables:
        return _error(req, "There is no data to ask about yet.", "Upload a CSV or Excel file, or load the sample data.")

    # 1. Ambiguity is decided by rules first: cheap, repeatable, and no tokens spent.
    trace.step("understand", "started")
    if clarification := find_ambiguity(req.question, catalog, req.clarification):
        trace.step("understand", "warn", f'"{clarification.term}" could mean more than one column')
        return Answer(id=uuid.uuid4().hex, kind="clarify", question=req.question,
                      text=f'"{clarification.term}" could mean more than one column in your data. Which one should I use?',
                      clarification=clarification)
    metrics = match_metrics(req.question, catalog)
    used = [m.metric.name for m in metrics if not m.missing_roles]
    trace.step("understand", "ok", f"Using vetted definition: {', '.join(used)}" if used else "No ambiguous terms")
    trace.lap("understand")

    # 2. Generate -> guard -> execute, repairing at most twice.
    schema_context = build_schema_context(catalog)
    metric_context = build_metric_context(metrics)
    outcome = _generate_and_execute(session, req, llm, trace, schema_context, metric_context)
    if isinstance(outcome, Answer):
        return outcome
    generation, query, result, signals = outcome

    # 3. Caveats the user should know even though the query ran fine.
    trace.step("verify", "started")
    work = trace.work
    risks = fan_out_risks(query, catalog)
    periods = period_risks(req.question, query, catalog)
    work.caveats += risks + periods + null_caveats(query, catalog) + _link_caveats(query, catalog, signals)
    if result.truncated:
        work.caveats.append(f"Only the first {settings.row_cap:,} rows are shown.")
        signals.truncated = True
    signals.fan_out = bool(risks)
    signals.period_unfiltered = bool(periods)
    signals.max_null_fraction = _max_null_fraction(query, catalog)

    # 4. Present: rules pick the chart and format every number before any model sees it.
    kinds = column_kinds(result, query, catalog)
    table = build_table(result, kinds)
    chart = choose_chart(table, kinds, req.question)
    trace.step("chart", "ok", chart.type.replace("_", " ").title())
    trace.lap("present")

    # 5. Narrate and cross-check at the same time: both only need the executed result.
    with ThreadPoolExecutor(max_workers=1) as pool:
        second = pool.submit(_cross_check, session, req, llm, schema_context, metric_context, result, work.payloads[-1].model)
        narration, fallback = _narrate(llm, req, query, table, work, catalog, trace, _notes(req, generation))
        work.cross_check = second.result()
    signals.narration_fallback = fallback
    signals.cross_check = work.cross_check.status
    detail = {"agreed": "A second model reached the same result", "disagreed": "A second model got a different result",
              "unavailable": "Cross-check unavailable", "skipped": "Cross-check off"}[work.cross_check.status]
    alarming = work.cross_check.status == "disagreed" or signals.fan_out or signals.period_unfiltered
    trace.step("verify", "warn" if alarming else "ok",
               detail + (f"; {_count(len(work.caveats), 'caveat')} noted" if work.caveats else ""))
    trace.lap("narrate_and_verify")

    work.interpretation = generation.interpretation
    work.reading = narration.reading
    work.plan = generation.plan
    work.sql = query.sql
    work.tables_used = query.tables
    work.rows_scanned = sum(t.row_count for t in catalog.tables if t.name in query.tables)
    work.assumptions = generation.assumptions
    claimed = {name.strip().lower() for name in generation.metrics_used}  # the model may echo the key or the name
    work.metrics_used = [m.metric.key for m in metrics
                         if not m.missing_roles and {m.metric.key.lower(), m.metric.name.lower()} & claimed]
    signals.vetted_metric = bool(work.metrics_used)
    signals.assumptions = len(generation.assumptions)

    text = narration.text if result.rows else "No rows matched that question. " + narration.text
    return Answer(id=uuid.uuid4().hex, kind="answer", question=req.question, text=text.strip(), chart=chart,
                  table=table, work=work, confidence=score(signals), followups=narration.followups[:3],
                  insights=insight_lines(table, kinds))  # computed from the rows, never model-written


def _generate_and_execute(session, req, llm, trace, schema_context, metric_context):
    """Returns (generation, guarded query, result, signals) or a terminal Answer.

    Each loop is one attempt. `why` records why the attempt was made ("initial" or the kind of
    problem being repaired); a problem found in this attempt becomes the next attempt's `why`.
    """
    work, signals = trace.work, Signals()
    why, repair = "initial", None
    tried_empty_repair = tried_period_repair = asked_again = False
    # While every free model is rate limited the pool waits briefly; say so instead of hanging.
    sql_llm = llm.with_options(on_wait=lambda s: trace.step(
        "generate", "warn", f"All the free AI models are busy. Retrying in {int(s) + 1} seconds."))

    while True:
        stage = "repair" if repair else "generate"
        trace.step(stage, "started")
        generation, payload = generate(
            sql_llm, role="sql", question=req.question, schema_context=schema_context,
            metric_context=metric_context, history=session.history[-3:],
            clarification=req.clarification, repair=repair,
        )
        work.payloads.append(payload)
        trace.step(stage, "ok", f"{payload.model} wrote a {len(generation.plan)}-step plan")
        trace.lap(stage)
        if generation.status == "clarify" and req.clarification:
            # The analyst already picked a column; a fallback model that asks the same question
            # again would loop them forever. Say the choice once more, then stop asking.
            if asked_again:
                return _error(req, "I still could not tell which column you mean.",
                              "Try naming the column in your question.")
            asked_again = True
            trace.step(stage, "warn", "The model asked again about a choice you already made")
            repair = RepairContext(previous_sql="", problem=CHOICE_ALREADY_MADE)
            continue
        if generation.status != "ok":
            return _non_sql_answer(session.catalog, req, generation, work)

        query = result = None
        problem_kind = problem = None
        try:
            query = validate_sql(generation.sql, session.catalog)
            trace.step("guard", "ok", f"Read-only, {_count(len(query.tables), 'table')}, {_count(len(query.columns), 'column')}")
            result = execute(session.cursor(), query.sql, timeout_s=settings.query_timeout_s, row_cap=settings.row_cap)
            trace.step("execute", "ok", f"{_count(len(result.rows), 'row')} in {result.elapsed_ms} ms")
            trace.lap("execute")
            risks = fan_out_risks(query, session.catalog)
            periods = period_risks(req.question, query, session.catalog)
            if risks:
                problem_kind = "fan_out"
                problem = risks[0] + " Rewrite it so the many-side is aggregated in a CTE before joining."
            elif periods and not tried_period_repair:
                # One try only: if the model still writes no date filter, the result is kept and
                # the sentence becomes a caveat in _run. A caveat beats no answer.
                tried_period_repair = True
                problem_kind = "period_missing"
                problem = periods[0] + " Filter on the period the question names."
            elif not result.rows and not tried_empty_repair:
                tried_empty_repair = True
                problem_kind = "empty_result"
                problem = "The query returned no rows. Check filter values against the listed values and date ranges."
        except GuardError as e:
            trace.step("guard", "warn", e.message)
            problem_kind, problem = "guard_rejected", e.message + (f" {e.suggestion}" if e.suggestion else "")
        except QueryTimeout:
            return _error(req, f"That query took longer than {settings.query_timeout_s:.0f} seconds, so I stopped it.",
                          "Try narrowing the question, for example to one year or one department.")
        except QueryError as e:
            trace.step("execute", "warn", "The database rejected the query")
            problem_kind, problem = "sql_error", str(e)

        work.attempts.append(Attempt(sql=generation.sql, model=payload.model, reason=why, error=problem))
        ran = query is not None and result is not None
        if problem is None or (ran and signals.repairs >= MAX_REPAIRS):
            return generation, query, result, signals  # a result with a caveat beats no result
        if signals.repairs >= MAX_REPAIRS:
            return _error(req, "I couldn't write a query that runs against your data for that question.",
                          "Try naming the columns or files you mean, or ask a simpler version first.")
        signals.repairs += 1
        why, repair = problem_kind, RepairContext(previous_sql=generation.sql, problem=problem)


def _non_sql_answer(catalog: Catalog, req: AskRequest, generation: Generation, work: Work) -> Answer:
    work.interpretation = generation.interpretation
    base = dict(id=uuid.uuid4().hex, question=req.question, work=work)
    if generation.status == "meta":
        return Answer(kind="meta", text=_describe_data(catalog), **base)
    if generation.status == "clarify":
        known = {f"{t.name}.{c.name}": c.label for t in catalog.tables for c in t.columns}
        options = [ClarifyOption(label=f"{known[o]} ({o})", value=o) for o in generation.clarify_options if o in known]
        if len(options) >= 2:  # only honoured when the options are real columns
            question = generation.clarify_question or "Which one do you mean?"
            return Answer(kind="clarify", text=question, clarification=Clarification(
                term=req.question, question=question, options=options), **base)
    return Answer(kind="refusal", missing=generation.missing or None, text=(
        "I can't answer that from the uploaded files. " + (generation.interpretation or "")).strip(), **base)


def _describe_data(catalog: Catalog) -> str:
    """Meta questions are answered from the catalog by template: no SQL, nothing to get wrong."""
    lines = [f"You have {_count(len(catalog.tables), 'table')}:"]
    for t in catalog.tables:
        kind = "view" if t.is_view else "table"
        names = ", ".join(c.label for c in t.columns[:8]) + (", ..." if len(t.columns) > 8 else "")
        lines.append(f"- {t.name} ({kind}, {t.row_count:,} rows, from {t.source_file}): {names}")
    links = [r for r in catalog.relationships if r.status == "active"]
    if links:
        lines.append("They join on: " + "; ".join(
            f"{r.left_table}.{r.left_column} = {r.right_table}.{r.right_column}" for r in links))
    return "\n".join(lines)


def _notes(req: AskRequest, generation: Generation) -> list[str]:
    """What the narrator needs to name the measure correctly ("average annual CTC", not
    "salary"). Column references and assumptions only: never row data."""
    chosen = [f'The analyst said "{term}" means {ref}.' for term, ref in (req.clarification or {}).items()]
    return chosen + list(generation.assumptions)


def _narrate(llm, req, query: GuardedQuery, table, work: Work, catalog: Catalog, trace: _Trace,
             notes: list[str]) -> tuple[Narration, bool]:
    trace.step("narrate", "started")
    try:
        narration, payload, fallback = narrate(llm, question=req.question, sql=query.sql, table=table,
                                               caveats=work.caveats, pii_columns=_pii_result_columns(query, table, catalog), notes=notes)
        work.payloads.append(payload)
    except LLMUnavailable:
        narration, fallback = Narration(text=template_answer(req.question, table)), True
    trace.step("narrate", "warn" if fallback else "ok",
               "Used a plain template because the wording could not be verified" if fallback else "Every number traced to the result")
    return narration, fallback


def _pii_result_columns(query: GuardedQuery, table, catalog: Catalog) -> set[str]:
    """If the query touches any PII column, EVERY result column that holds text is hidden from
    the narrator. A column name proves nothing: `SELECT e.name AS department` would otherwise
    walk straight through. Tokens are swapped back before the user sees the sentence."""
    profiles = {(t.name, c.name): c for t in catalog.tables for c in t.columns}
    if not any(profiles.get(ref) and profiles[ref].pii for ref in query.columns):
        return set()
    return {name for i, name in enumerate(table.columns) if any(isinstance(row[i], str) for row in table.rows)}


def _cross_check(session, req, llm, schema_context, metric_context, primary: ExecResult, avoid_model: str) -> CrossCheck:
    """A second model family writes its own SQL. Agreement is evidence; disagreement is a flag.
    Any failure here is 'unavailable', never an error for the user."""
    if not settings.crosscheck:
        return CrossCheck(status="skipped")
    try:
        # Agreement only means something if a DIFFERENT model wrote the second query.
        generation, payload = generate(llm.with_options(avoid_model=avoid_model), role="crosscheck", question=req.question, schema_context=schema_context,
                                       metric_context=metric_context, history=session.history[-3:],
                                       clarification=req.clarification)
        if generation.status != "ok":
            return CrossCheck(status="unavailable", model=payload.model, detail="The second model did not produce a query.")
        query = validate_sql(generation.sql, session.catalog)
        other = execute(session.cursor(), query.sql, timeout_s=settings.query_timeout_s, row_cap=settings.row_cap)
    except Exception as e:  # noqa: BLE001 - deliberately broad, see docstring
        return CrossCheck(status="unavailable", detail=f"The second model could not be used ({type(e).__name__}).")
    if results_equivalent(primary, other):
        return CrossCheck(status="agreed", model=payload.model, sql=query.sql,
                          detail="A second model wrote its own SQL and got the same result.")
    return CrossCheck(status="disagreed", model=payload.model, sql=query.sql,
                      detail=f"A second model wrote different SQL and got a different result ({_count(len(other.rows), 'row')}). Check the SQL before relying on this.")


def _link_caveats(query: GuardedQuery, catalog: Catalog, signals: Signals) -> list[str]:
    """An inner join silently leaves out keys that have no partner; say which side, because
    "7% of employees have no payroll rows" and "7% of payroll rows have no employee" are very
    different problems. Confidence looks at the better-contained side: in a healthy
    parent/child link the child's keys are all found in the parent."""
    caveats = []
    for join in query.joins:
        ends = {(join.left_table, join.left_column), (join.right_table, join.right_column)}
        for r in catalog.relationships:
            if {(r.left_table, r.left_column), (r.right_table, r.right_column)} != ends:
                continue
            signals.min_join_match = min(signals.min_join_match, max(r.match_left, r.match_right))
            for table, other, match in ((r.left_table, r.right_table, r.match_left),
                                        (r.right_table, r.left_table, r.match_right)):
                if match < 0.98:
                    caveats.append(f"{1 - match:.0%} of the keys in {table} have no match in {other}, "
                                   "so those rows are left out of joined results.")
            if r.status == "suggested":
                signals.used_unconfirmed_link = True
                caveats.append(f"The link {r.left_table}.{r.left_column} = {r.right_table}.{r.right_column} "
                               "is a suggestion you have not confirmed.")
    return caveats


def _max_null_fraction(query: GuardedQuery, catalog: Catalog) -> float:
    profiles = {(t.name, c.name): c for t in catalog.tables for c in t.columns}
    return max((profiles[ref].null_fraction for ref in query.columns if ref in profiles), default=0.0)
