"""Ask the app every golden question and grade what comes back.

Run from the repo root:

    PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split dev

Two sets of questions, chosen with `--set`:
  golden (the default)  eval/golden.yaml, graded against eval/truth.py, written into
                        eval/report.json. Thirty of its forty questions are tuned against.
  challenge             eval/challenge.yaml, graded against eval/truth_challenge.py, written
                        into eval/challenge_report.json. Sixteen harder questions, written after
                        the tuning was finished and never used to change a prompt, so its score
                        is the honest one. It can never write eval/report.json, and its section
                        of REPORT.md lists every failure.
Both share eval/.llm_cache, so a call one set has already paid for is replayed by the other.

Why it drives `answer_question` directly rather than the HTTP API: the grade should depend on
the pipeline, not on a server being up, and the runner needs the full `Answer` (SQL, attempts,
confidence) to explain a failure. Expected values come from `eval/truth.py`, which computes
them with pandas from the clean sample frames and never imports the app.

How a tuning loop is meant to use the flags:
  --split all --hide-holdout-failures --no-crosscheck   score everything, see only dev failures
  --only-failed                                          re-run what failed last time
  --split all --runs 3                                   final confirmation pass
  --chain groq:qwen/qwen3.8-27b                          same questions, another model; the
                                                         comparison table accumulates

A partial pass updates only the questions it ran; the rest of the report carries over as long
as the model is the same, so `report.json` always describes the whole golden set.
"""

from __future__ import annotations

import argparse
import importlib
import os
import re
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

import yaml
from app.contracts import (
    Answer,
    AskRequest,
    Clarification,
    ClarifyOption,
    EvalCase,
    EvalReport,
    ResultTable,
    StepEvent,
)

from eval.compare import matches
from eval.report import (
    HIDDEN_NOTE,
    NARRATION_FAILURE,
    build_report,
    load_report,
    report_filename,
    write_report,
)

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = EVAL_DIR / "golden.yaml"
CHALLENGE_PATH = EVAL_DIR / "challenge.yaml"
OUT_DIR = EVAL_DIR
# One cache for both sets: a challenge question that happens to need the same call as a golden
# one replays instead of spending, which on a free tier is the difference between a pass and no
# pass at all.
CACHE_DIR = EVAL_DIR / ".llm_cache"

MAX_RETRIES = 3
RETRY_WAIT_S = 20  # free tiers meter tokens per minute; 20 + 40 + 60 s spans two full windows

KINDS = ("answer", "clarify", "refusal", "assume_or_refuse")
SPLITS = ("dev", "holdout")
SETS = ("golden", "challenge")

Ask = Callable[[AskRequest], Answer]
Sleep = Callable[[float], None]


class EvalSetupError(Exception):
    """The run cannot start. The message is a sentence for the person at the terminal: what is
    wrong, then what to do. Raised before any model call, so a broken setup costs no tokens."""


@dataclass(frozen=True)
class GoldenCase:
    """One entry of golden.yaml, flattened so the grading code reads plainly."""

    id: str
    category: str
    split: str
    question: str
    kind: str  # what a good response is: answer | clarify | refusal | assume_or_refuse
    truth: str | None = None  # function name in the set's truth module
    ordered: bool = False
    options_include: list[str] = field(default_factory=list)
    then_choose: str | None = None
    text_must_not_contain: list[str] = field(default_factory=list)
    # The sentence, not only the table: must the answer text name the truth's highest row? its
    # lowest? See `_narration_problem` for what "name" means and what else is then checked.
    names_top: bool = False
    names_bottom: bool = False


@dataclass
class CaseResult:
    """One run of one question."""

    passed: bool
    got_kind: str  # kind of the last response the app gave
    note: str
    confidence: str | None
    latency_ms: int
    repairs: int
    cached: bool  # any model response was replayed from disk, so the latency is not real
    cross_check: str
    sql: str | None
    # A model call may have gone to a provider, so the next question must wait. Not the
    # opposite of `cached`: replayed SQL with a live narration or cross-check still spends.
    live: bool = True


class AppUnderTest(Protocol):
    """What the runner needs from the app. `SampleApp` is the real one; tests script a fake."""

    def model_label(self) -> str: ...
    def start_run(self, run_index: int) -> None: ...
    def new_conversation(self) -> None: ...
    def ask(self, req: AskRequest) -> Answer: ...


# --------------------------------------------------------------------------
# Golden file
# --------------------------------------------------------------------------


def load_cases(path: Path, truth: ModuleType | Any) -> list[GoldenCase]:
    """Read and check golden.yaml. Every problem is reported here, before tokens are spent."""
    if not path.exists():
        raise EvalSetupError(f"{path} does not exist. Create the question set first "
                             "(eval/golden.yaml is the one the other is modelled on).")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as problem:
        raise EvalSetupError(f"{path} is not valid YAML. Fix this and run again: {problem}") from problem
    if not raw:
        raise EvalSetupError(f"{path} has no questions in it. Add at least one case.")
    if not isinstance(raw, list) or not all(isinstance(entry, dict) for entry in raw):
        raise EvalSetupError(f"{path} must be a list of cases, each with id, category, split, question "
                             "and expect. The comment at the top of eval/golden.yaml shows the shape.")

    cases: list[GoldenCase] = []
    for entry in raw:
        case = _parse_case(entry)
        if any(case.id == other.id for other in cases):
            raise EvalSetupError(f"{case.id} appears more than once in {path.name}. Give every case its own id.")
        if case.truth and not callable(getattr(truth, case.truth, None)):
            module = getattr(truth, "__name__", "eval.truth").replace(".", "/")
            raise EvalSetupError(f"{case.id} expects truth.{case.truth}(), but {module}.py has no such function.")
        cases.append(case)
    return cases


def _parse_case(entry: dict[str, Any]) -> GoldenCase:
    expect = entry.get("expect")
    if not isinstance(expect, dict):
        expect = {}  # reported below as a missing expect.kind, in a sentence
    narration = entry.get("narration") or expect.get("narration") or {}
    # A typo here would silently stop grading the sentence, which is the one failure this whole
    # check exists to make visible. Refuse the file instead.
    if not isinstance(narration, dict) or set(narration) - {"names_top", "names_bottom"}:
        raise EvalSetupError(f"{entry.get('id') or 'A case'} has an expect.narration this runner does not "
                             "understand. It takes names_top and names_bottom, each true or false.")
    case = GoldenCase(
        id=str(entry.get("id", "")),
        category=str(entry.get("category", "")),
        split=str(entry.get("split", "")),
        question=str(entry.get("question", "")).strip(),
        kind=str(expect.get("kind", "")),
        truth=expect.get("truth"),
        ordered=bool(entry.get("ordered") or expect.get("ordered")),
        options_include=[str(o) for o in expect.get("options_include") or []],
        then_choose=expect.get("then_choose"),
        text_must_not_contain=[str(t) for t in expect.get("text_must_not_contain") or []],
        names_top=bool(narration.get("names_top")),
        names_bottom=bool(narration.get("names_bottom")),
    )
    name = case.id or f"The case asking {case.question!r}"
    if not (case.id and case.category and case.question):
        raise EvalSetupError(f"{name} needs an id, a category and a question.")
    if case.split not in SPLITS:
        raise EvalSetupError(f"{name} has split {case.split!r}. Use one of: {', '.join(SPLITS)}.")
    if case.kind not in KINDS:
        raise EvalSetupError(f"{name} has expect.kind {case.kind!r}. Use one of: {', '.join(KINDS)}.")
    if case.kind in ("answer", "assume_or_refuse") and not case.truth:
        raise EvalSetupError(f"{name} expects an answer, so it needs expect.truth: a function name in the truth module.")
    if (case.names_top or case.names_bottom) and not case.truth:
        raise EvalSetupError(f"{name} asks for its narration to be graded, which needs expect.truth: "
                             "the highest and lowest rows are read from the expected answer.")
    if case.kind == "clarify" and bool(case.truth) != bool(case.then_choose):
        raise EvalSetupError(f"{name} needs both expect.then_choose and expect.truth, or neither.")
    return case


def select_cases(
    cases: list[GoldenCase], *, split: str, ids: set[str] | None = None, failed_ids: set[str] | None = None
) -> list[GoldenCase]:
    """Filters combine: --split holdout --only-failed means the failed holdout questions."""
    unknown = (ids or set()) - {c.id for c in cases}
    if unknown:
        raise EvalSetupError(f"No golden question has the id: {', '.join(sorted(unknown))}. Check eval/golden.yaml.")
    return [
        c for c in cases
        if (split == "all" or c.split == split)
        and (ids is None or c.id in ids)
        and (failed_ids is None or c.id in failed_ids)
    ]


def _load_truth(module_name: str = "eval.truth") -> ModuleType:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as missing:
        raise EvalSetupError(
            f"Could not import {module_name.replace('.', '/')}.py ({missing.name} was not found). "
            "Run from the repo root with PYTHONPATH=backend:. as shown in CLAUDE.md."
        ) from missing


def _expected_values(cases: list[GoldenCase], truth: ModuleType | Any) -> dict[str, Any]:
    """Work out every expected value, and prove the comparer can grade it, before any question
    is asked. A truth function that crashes or returns an ungradable shape would otherwise
    stop the run halfway, after tokens were spent and before any report was written."""
    nothing = ResultTable(columns=[], rows=[], display=[], row_count=0)
    expected: dict[str, Any] = {}
    for case in cases:
        if not case.truth:
            expected[case.id] = None
            continue
        try:
            expected[case.id] = getattr(truth, case.truth)()
            matches(expected[case.id], nothing)  # raises ValueError on a value it cannot grade
        except Exception as problem:
            raise EvalSetupError(
                f"truth.{case.truth}() cannot be used for {case.id}: {problem!r}. "
                "Fix the truth module. No question was asked."
            ) from problem
        if (case.names_top or case.names_bottom) and _ranked_labels(expected[case.id]) is None:
            raise EvalSetupError(
                f"{case.id} asks for its narration to be graded, but truth.{case.truth}() is not a "
                "ranked breakdown: that needs (label, number) rows with a single highest and a "
                "single lowest value. No question was asked."
            )
    return expected


# --------------------------------------------------------------------------
# The sentence, graded against the same rows the table is graded against
# --------------------------------------------------------------------------

# Ranking words as written, never stemmed, and deliberately the same list the narrator checks
# itself against (app/query/narrator.py). The two are kept apart on purpose: the narrator's copy
# decides what to say, this one decides whether the eval believes it, and a bug in one must not
# excuse itself in the other.
_HIGHEST_WORD = re.compile(r"\b(?:highest|most|largest|biggest|greatest|top|leads|led|maximum|peak|peaked)\b", re.IGNORECASE)
_LOWEST_WORD = re.compile(r"\b(?:lowest|least|smallest|fewest|bottom|minimum|trails)\b", re.IGNORECASE)
# How far one claim reaches. A full stop or comma between digits belongs to a number
# ("₹6,33,334", "12.00"), so it never ends a clause. "than" ends one, because a ranking word
# belongs to the side before it: "Engineering pays the most of any department other than Support"
# otherwise puts both rows in one clause, and one of them is the right answer.
# ponytail: a bare comparative ("Pune has more employees than Mumbai") carries no ranking word at
# all, so neither this check nor the narrator's own sees it; adding "more" would fail true asides.
# Upgrade path: compare the two sides of "than" with each other, not each with the winner.
_CLAUSE = re.compile(r"(?<!\d)[.,](?!\d)|[;:!?]|\b(?:while|whereas|but|and|than)\b", re.IGNORECASE)


def _ranked_labels(expected: Any) -> tuple[list[str], list[str], list[str]] | None:
    """(every label, the highest rows' labels, the lowest rows' labels), or None when the
    expected answer is not a ranked breakdown and so says nothing about a highest row.

    Read from the truth, never from the app's own result: a sentence that agrees with a wrong
    table would otherwise grade as correct, which is exactly the failure this check exists for.
    Ties come back as several labels, because naming any of them is honest."""
    if not isinstance(expected, list) or not expected:
        return None
    if not all(isinstance(row, tuple) and len(row) == 2 for row in expected):
        return None
    labels = [str(row[0]) for row in expected]
    values = [row[1] for row in expected]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return None
    top, bottom = max(values), min(values)
    if top == bottom:
        return None  # a flat result has no highest row to name
    return (labels,
            [label for label, value in zip(labels, values) if value == top],
            [label for label, value in zip(labels, values) if value == bottom])


def _names(text: str, label: str) -> bool:
    """Whether the text says this label. Case-insensitive, whole words, so "HR" is not found
    inside "CHRO" and a label the model capitalised differently still counts."""
    return re.search(rf"(?<!\w){re.escape(label)}(?!\w)", text, re.IGNORECASE) is not None


def _narration_problem(case: GoldenCase, text: str, expected: Any) -> str:
    """What is wrong with the answer's sentence, or "" when nothing is.

    Two checks per direction, and only for the direction the case asks about:
      * the label of the truth's highest (lowest) row appears in the sentence at all;
      * no clause uses a highest-word about a *different* label.
    The second is the one that caught "Engineering has the highest average salary at ₹13.34 L"
    when the top row was Support at ₹15.53 L: the table was right and the sentence was not.

    Only the answer text is read. A follow-up chip ("How does Engineering compare?") asks a
    question, it does not claim a rank."""
    ranked = _ranked_labels(expected)
    if ranked is None:
        return ""
    labels, top, bottom = ranked
    for wanted, pattern, word in ((top if case.names_top else [], _HIGHEST_WORD, "highest"),
                                  (bottom if case.names_bottom else [], _LOWEST_WORD, "lowest")):
        if not wanted:
            continue
        # The misattribution first: when both are wrong, "you called Engineering the highest"
        # is the sentence someone can act on, and "it never names Support" is the same news
        # with the evidence left out.
        for clause in _CLAUSE.split(text):
            if not pattern.search(clause):
                continue
            named = [label for label in labels if _names(clause, label)]
            if named and not set(named) & set(wanted):
                return (f'{NARRATION_FAILURE.capitalize()}: "{clause.strip()}" calls {named[0]} the '
                        f"{word}; the {word} is {_either(wanted)} in the expected result.")
        if not any(_names(text, label) for label in wanted):
            return (f"{NARRATION_FAILURE.capitalize()}: the answer never names {_either(wanted)}, "
                    f"the {word} row of the result.")
    return ""


def _either(labels: list[str]) -> str:
    return " or ".join(labels[:3])


# --------------------------------------------------------------------------
# Asking and grading one question
# --------------------------------------------------------------------------


def run_case(case: GoldenCase, ask: Ask, expected: Any, sleep: Sleep = time.sleep) -> CaseResult:
    """Ask, follow a clarifying question if one is expected, and grade the last response."""
    answer, latency_ms = _ask_patiently(ask, AskRequest(question=case.question), sleep)
    answers = [answer]

    if case.kind == "clarify" and answer.kind == "clarify":
        passed, note, choice = _grade_options(case, answer.clarification)
        if choice is not None:
            request = AskRequest(question=case.question, clarification={answer.clarification.term: choice.value})
            answer, more_ms = _ask_patiently(ask, request, sleep)
            answers.append(answer)
            latency_ms += more_ms
            passed, problem = _grade_answer(case, answer, expected)
            note = (f"After choosing {choice.value}: {problem}" if not passed
                    else f"Asked which column was meant, then answered correctly once {choice.value} was chosen.")
    else:
        passed, note = _grade(case, answer, expected)

    return CaseResult(
        passed=passed,
        got_kind=answer.kind,
        note=note,
        confidence=answer.confidence.level if answer.confidence else None,
        latency_ms=latency_ms,
        repairs=sum(attempt.reason != "initial" for a in answers for attempt in a.work.attempts),
        cached=any(payload.cached for a in answers for payload in a.work.payloads),
        cross_check=answer.work.cross_check.status,
        sql=answer.work.sql,
        # ponytail: the cross-check call leaves no payload, so whenever it ran it counts as
        # live. A fully replayed pass then sleeps for nothing; run that one without --sleep.
        live=any(not payload.cached for a in answers for payload in a.work.payloads)
        or answer.work.cross_check.status != "skipped",
    )


def _ask_patiently(ask: Ask, req: AskRequest, sleep: Sleep) -> tuple[Answer, int]:
    """One question, waiting out busy providers. Returns the answer and the time the last
    attempt took, so retry waits never count as latency.

    The pipeline turns a provider outage into an `error` answer instead of raising, so an
    outage-looking error answer is retried just like `LLMUnavailable`. Other errors (a query the
    model could not get right, a timeout) would replay identically, so they are recorded at once
    instead of costing two minutes of waiting each.
    """
    from app.llm.client import LLMUnavailable  # late import: see SampleApp

    for attempt in range(MAX_RETRIES + 1):
        started = time.perf_counter()
        try:
            answer = ask(req)
        except LLMUnavailable as outage:
            answer = _error_answer(req, f"No model was available: {outage}")
        except Exception as crash:  # noqa: BLE001 - one broken question must not lose the other 39
            return _error_answer(req, f"The app crashed with {type(crash).__name__}: {crash}"), _ms_since(started)
        if answer.kind != "error" or attempt == MAX_RETRIES or not _looks_like_outage(answer):
            return answer, _ms_since(started)
        sleep(RETRY_WAIT_S * (attempt + 1))
    raise AssertionError("unreachable: the loop always returns on its last attempt")


def _looks_like_outage(answer: Answer) -> bool:
    """ponytail: reads the sentence, because an error Answer carries no machine-readable reason.
    If the pipeline's wording changes, outages stop being retried and show up in the report as
    errors (visible, re-runnable with --only-failed). Upgrade path: an error code on Answer."""
    text = answer.text.casefold()
    return any(hint in text for hint in ("busy", "rate limit", "no model was available"))


def _error_answer(req: AskRequest, text: str) -> Answer:
    return Answer(id="eval-error", kind="error", question=req.question, text=text)


def _ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _grade(case: GoldenCase, answer: Answer, expected: Any) -> tuple[bool, str]:
    """Grade a first response. (The clarify-then-answer path is handled in run_case.)"""
    if case.kind == "refusal":
        if answer.kind != "refusal":
            return False, ("The app answered a question the data cannot answer. It should have refused and "
                           f"named the missing data. {_unexpected(answer)}")
        return True, "" if answer.missing else "Refused, but did not say which data is missing."

    if case.kind == "clarify":
        if answer.kind != "answer" or not case.truth:
            return False, f"Expected clarifying options. {_unexpected(answer)}"
        passed, problem = _grade_answer(case, answer, expected)
        if passed and not answer.work.assumptions:
            return False, "Answered an ambiguous question without asking and without stating which column it assumed."
        return passed, problem if not passed else "Answered directly and stated its assumption."

    if case.kind == "assume_or_refuse":
        # The question names a column that is not there. Declining honestly and answering the
        # near column out loud are both fine; answering it silently is the wrong answer waiting
        # to happen, because the analyst never learns which column was read.
        if answer.kind == "refusal":
            return True, ("Refused." if answer.missing else "Refused, but did not say which data is missing.")
        passed, problem = _grade_answer(case, answer, expected)
        if not passed:
            return False, problem
        if not answer.work.assumptions:
            return False, ("Answered a question about a column the data does not have, without refusing and "
                           "without stating which column it read instead.")
        return True, "Stated which column it read instead, and answered it correctly."

    return _grade_answer(case, answer, expected)


def _grade_answer(case: GoldenCase, answer: Answer, expected: Any) -> tuple[bool, str]:
    if answer.kind != "answer":
        return False, _unexpected(answer)
    if answer.table is None:
        return False, "The app answered in words but returned no result table, so there is nothing to check."
    if not matches(expected, answer.table, ordered=case.ordered):
        return False, (f"The result does not match the expected value. Expected {_short(expected)}; "
                       f"got {_short(answer.table.rows[:3])} ({answer.table.row_count} row(s)).")
    # Table cells may legitimately hold a planted instruction (it is data); prose may not repeat it.
    prose = " ".join([answer.text, *answer.followups]).casefold()
    for phrase in case.text_must_not_contain:
        if phrase.casefold() in prose:
            return False, f'The answer text contains "{phrase}", which comes from an instruction planted in the data.'
    if problem := _narration_problem(case, answer.text, expected):
        return False, problem
    return True, ""


def _grade_options(case: GoldenCase, clarification: Clarification | None) -> tuple[bool, str, ClarifyOption | None]:
    """Check the offered options. Returns (passed so far, note, option to choose next or None)."""
    options = clarification.options if clarification else []

    def offered(word: str) -> list[ClarifyOption]:
        folded = word.casefold()
        exact = [o for o in options if o.value.casefold().split(".")[-1] == folded]
        loose = [o for o in options if folded in o.value.casefold() or folded in o.label.casefold()]
        return exact + loose

    missing = [word for word in case.options_include if not offered(word)]
    if missing:
        listed = ", ".join(o.value for o in options) or "none"
        return False, f"The clarifying options did not include: {', '.join(missing)}. Offered: {listed}.", None
    if not case.then_choose:
        return True, "Asked which column was meant, as expected.", None
    choices = offered(case.then_choose)
    if not choices:
        return False, f"The option to choose next ({case.then_choose}) was not offered.", None
    return True, "", choices[0]


def _unexpected(answer: Answer) -> str:
    return {
        "refusal": "The app declined to answer a question the data can answer.",
        "clarify": "The app asked a clarifying question where none was expected.",
        "meta": "The app described the data instead of answering the question.",
        "error": f"The app returned an error: {answer.text}",
        "answer": "The app gave an answer.",
    }[answer.kind]


def _short(value: Any, limit: int = 160) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


# --------------------------------------------------------------------------
# From runs to report rows
# --------------------------------------------------------------------------


def collapse_runs(case: GoldenCase, runs: list[CaseResult], earlier: EvalCase | None) -> EvalCase:
    """One report row per question. A question passes only if every run passed, because an
    answer that is right two times out of three is not one to put in front of a CHRO. When a
    run failed, that run is the one shown, so the badge and the note belong to the failure."""
    shown = next((r for r in runs if not r.passed), runs[0])
    passes = sum(r.passed for r in runs)
    note = f"Passed {passes} of {len(runs)} runs. {shown.note}".strip() if 0 < passes < len(runs) else shown.note
    live = [r.latency_ms for r in runs if not r.cached]
    return EvalCase(
        id=case.id, category=case.category, split=case.split, question=case.question,
        expected_kind=case.kind, got_kind=shown.got_kind, passed=passes == len(runs),
        confidence=shown.confidence,
        # A replay from the LLM cache takes milliseconds. Keep the last real timing instead.
        latency_ms=int(statistics.median(live)) if live else (earlier.latency_ms if earlier else 0),
        repairs=max(r.repairs for r in runs), note=note,
    )


def merge_cases(earlier: list[EvalCase], fresh: list[EvalCase], golden: list[GoldenCase]) -> list[EvalCase]:
    """Fresh results replace earlier ones, in golden-set order. An earlier result is carried
    over only while the golden case it describes is unchanged. If the question was reworded,
    removed, or moved between dev and holdout, the old row would put a stale pass into the
    headline accuracy, so it drops out until that question is asked again."""
    by_id = {c.id: c for c in [*earlier, *fresh]}
    return [
        by_id[g.id] for g in golden
        if g.id in by_id
        and (by_id[g.id].question, by_id[g.id].split, by_id[g.id].category) == (g.question, g.split, g.category)
    ]


def hide_holdout_notes(cases: list[EvalCase]) -> list[EvalCase]:
    """ponytail: report.json still says which holdout questions failed, because the Trust Report
    is computed from it. Only the reasons are withheld; a tuning agent is told not to open the
    file. Split the holdout into its own file if that ever needs enforcing."""
    return [
        c if c.split != "holdout" else c.model_copy(update={"note": "" if c.passed else HIDDEN_NOTE})
        for c in cases
    ]


def _agreement(results: dict[str, list[CaseResult]]) -> float | None:
    statuses = [r.cross_check for runs in results.values() for r in runs]
    checked = [s for s in statuses if s in ("agreed", "disagreed")]
    return round(checked.count("agreed") / len(checked), 3) if checked else None


# --------------------------------------------------------------------------
# The real app
# --------------------------------------------------------------------------


class SampleApp:
    """The real pipeline over the sample HR data, held the way the API holds a session.

    Why the `app.*` imports are inside methods: importing this module (tests do) must not pull
    in the whole app or touch its settings; only a real run does.
    """

    def __init__(self, chain_spec: str | None, crosscheck: bool):
        if chain_spec:
            os.environ["LLM_SQL_CHAIN"] = chain_spec  # app.config.chain() reads this on every call
        if not crosscheck:
            _override_setting("crosscheck", False)

        from app.sessions import SessionStore

        self._session = SessionStore().create()
        try:
            self._session.load_sample()
        except ValueError as problem:  # IngestError carries a sentence meant for people
            raise EvalSetupError(f"The sample data could not be loaded: {problem}") from problem
        if not self._session.catalog.tables:
            raise EvalSetupError("No sample data was found in demo_data/. Run `uv run python demo_data/generate.py` first.")
        self._llm: Any = None

    def model_label(self) -> str:
        """The primary SQL model: the first entry of the chain that has an API key."""
        from app.config import PROVIDERS, chain

        try:
            usable = chain("sql")
        except KeyError as unknown:
            raise EvalSetupError(f"--chain names a provider this app does not know: {unknown}. "
                                 f"Known providers: {', '.join(PROVIDERS)}.") from unknown
        if not usable:
            raise EvalSetupError("No model provider has an API key. Add one to .env (see .env.example) "
                                 "and start the run with `uv run --env-file .env ...`.")
        return usable[0].model

    def start_run(self, run_index: int) -> None:
        """Each run index gets its own response cache. Run 1 replays from eval/.llm_cache, so a
        prompt change only re-spends the calls it changed; runs 2..N have their own folders,
        otherwise `--runs 3` would replay run 1 three times and "passed every run" would mean nothing."""
        from app.llm.client import PoolClient

        cache = CACHE_DIR if run_index == 0 else CACHE_DIR / f"run{run_index + 1}"
        _override_setting("llm_cache_dir", str(cache))  # what LLM_CACHE_DIR would have set
        self._llm = PoolClient()

    def new_conversation(self) -> None:
        """Golden questions are independent: no follow-up context, no remembered answers. The
        pipeline's process-wide answer cache is cleared too, or a second run would be a replay."""
        from app.query.pipeline import clear_answer_cache

        self._session.history.clear()
        self._session.answer_cache.clear()
        clear_answer_cache()

    def ask(self, req: AskRequest) -> Answer:
        from app.query.pipeline import answer_question

        return answer_question(self._session, req, self._llm, _ignore_step)


def _ignore_step(event: StepEvent) -> None:
    """The UI streams these; the eval only needs the final answer."""


def _override_setting(name: str, value: object) -> None:
    """`settings` is read from the environment once, on first import, and then frozen because
    the app never changes it while running. The eval runner is the documented exception
    (config.py: "set by the eval runner only"), and setting the object works whether or not
    something imported `app.config` before us, which an environment variable would not."""
    from app.config import settings

    object.__setattr__(settings, name, value)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m eval.run_eval", description="Grade the app on the golden questions.")
    parser.add_argument("--set", dest="question_set", choices=list(SETS), default="golden",
                        help="golden (the tuned 40) or challenge (16 harder questions, never tuned on)")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="all")
    parser.add_argument("--ids", default="", help="comma-separated case ids, e.g. tot-01,hr-03")
    parser.add_argument("--only-failed", action="store_true", help="re-run the questions that failed in the last report")
    parser.add_argument("--runs", type=int, default=1, help="ask every question N times; it passes only if every run passes")
    parser.add_argument("--no-crosscheck", action="store_true", help="skip the second model (saves tokens while tuning)")
    parser.add_argument("--sleep", type=float, default=0.0, help="seconds to pause between questions (rate limits)")
    parser.add_argument("--hide-holdout-failures", action="store_true",
                        help="print and write only totals for holdout questions, so tuning cannot fit them")
    parser.add_argument("--chain", default=None, help='override the SQL model chain, e.g. "groq:qwen/qwen3.8-27b"')
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    return args


def main(argv: list[str] | None = None, app: AppUnderTest | None = None, sleep: Sleep = time.sleep) -> int:
    """Exit code 0 when the pass completed (whatever the score), 2 when it could not start."""
    args = _parse_args(argv)
    try:
        return _run(args, app, sleep)
    except EvalSetupError as problem:
        print(problem)
        return 2


def _run(args: argparse.Namespace, app: AppUnderTest | None, sleep: Sleep) -> int:
    challenge = args.question_set == "challenge"
    truth = _load_truth("eval.truth_challenge") if challenge else _load_truth()
    golden = load_cases(CHALLENGE_PATH if challenge else GOLDEN_PATH, truth)
    report_path = OUT_DIR / report_filename(args.question_set)
    previous = load_report(report_path)
    # The challenge set is never tuned on, so there is nothing to hide from a tuning loop and
    # its section of REPORT.md promises every failure. The flag stays off for it whatever the
    # command line said.
    hide = args.hide_holdout_failures and not challenge

    failed_ids = None
    if args.only_failed:
        if previous is None:
            raise EvalSetupError(f"There is no earlier report in eval/{report_path.name}, so there are no failures "
                                 "to re-run. Run a full pass first: --split all.")
        failed_ids = {c.id for c in previous.cases if not c.passed}
    wanted_ids = {i.strip() for i in args.ids.split(",") if i.strip()} or None
    selected = select_cases(golden, split=args.split, ids=wanted_ids, failed_ids=failed_ids)
    if not selected:
        print("No questions match those options, so nothing was run and the report is unchanged.")
        return 0

    expected = _expected_values(selected, truth)
    app = app or SampleApp(args.chain, crosscheck=not args.no_crosscheck)
    model = app.model_label()
    print(f"Asking {len(selected)} question(s), {args.runs} run(s) each, with {model}.")

    results: dict[str, list[CaseResult]] = {c.id: [] for c in selected}
    for run_index in range(args.runs):
        app.start_run(run_index)
        for position, case in enumerate(selected, start=1):
            app.new_conversation()
            result = run_case(case, app.ask, expected[case.id], sleep)
            results[case.id].append(result)
            _print_case(f"run {run_index + 1}, {position}/{len(selected)}", case, result,
                        hidden=hide and case.split == "holdout")
            last = run_index == args.runs - 1 and position == len(selected)
            if args.sleep and result.live and not last:
                sleep(args.sleep)  # a fully replayed question spent no tokens, so there is nothing to pace

    earlier = {c.id: c for c in previous.cases} if previous and previous.model == model else {}
    fresh = [collapse_runs(case, results[case.id], earlier.get(case.id)) for case in selected]
    cases = merge_cases(list(earlier.values()), fresh, golden)
    if hide:
        cases = hide_holdout_notes(cases)
    report = build_report(cases, model=model, runs=args.runs, crosscheck_agreement=_agreement(results),
                          other_models=previous.models if previous else [])
    write_report(report, OUT_DIR, hide, args.question_set)
    _print_summary(report, results, carried_over=len(cases) - len(fresh), report_path=report_path)
    return 0


def _print_case(progress: str, case: GoldenCase, result: CaseResult, hidden: bool) -> None:
    if hidden:
        print(f"[{progress}] holdout question (result hidden)")
        return
    verdict = "PASS" if result.passed else "FAIL"
    print(f"[{progress}] {verdict} {case.id} ({case.category}): {result.got_kind}, "
          f"{result.confidence or 'no'} confidence, {result.latency_ms} ms, {result.repairs} repair(s)")
    if not result.passed:
        print(f"    {result.note}")
        if result.sql:
            print(f"    SQL: {result.sql}")


def _print_summary(report: EvalReport, results: dict[str, list[CaseResult]], carried_over: int,
                   report_path: Path) -> None:
    def tally(split: str) -> str:
        group = [c for c in report.cases if c.split == split]
        return f"{sum(c.passed for c in group)} of {len(group)}"

    passed = sum(c.passed for c in report.cases)
    print()
    print(f"Correct: {passed} of {report.total} ({report.accuracy:.1%})" + (" in every run" if report.runs > 1 else ""))
    print(f"Dev: {tally('dev')}. Holdout: {tally('holdout')}. Trust score: {report.trust_score:+.2f}.")
    if report.runs > 1:
        per_run = [sum(runs[i].passed for runs in results.values()) / len(results) for i in range(report.runs)]
        print("Per run, for the questions asked in this pass: " + ", ".join(f"{share:.1%}" for share in per_run))
    if carried_over:
        print(f"{carried_over} question(s) were not asked in this pass; their earlier results were kept.")
    print(f"Wrote {report_path} and {OUT_DIR / 'REPORT.md'}.")


if __name__ == "__main__":
    raise SystemExit(main())
