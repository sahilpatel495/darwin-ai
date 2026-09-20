"""Turn graded eval cases into the Trust Report (`report.json`) and its readable twin (`REPORT.md`).

Why every number is recomputed from the case list: the report can then be merged across
partial runs, rebuilt from `report.json` alone, and checked by hand. The one exception is
cross-check agreement, which is not stored per case and so describes the latest pass only.

Why this module also reads the question files and holds a few constants: REPORT.md is
regenerated from scratch by every run, so anything a reader needs that `EvalReport` cannot
carry — which question's sentence is graded, which one a prompt was tuned for, what class a
failure belongs to, which model filled which role — has to be produced here or it is silently
dropped by the next pass. `backend/app/contracts.py` is not the eval's to grow, so the facts
live beside the renderer instead. Every line of REPORT.md comes out of this file.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import yaml
from app.contracts import CalibrationBucket, EvalCase, EvalReport, ModelScore
from pydantic import ValidationError

LEVELS = ("high", "medium", "low")
# Kinds where the app asserted something. Being wrong here costs a point; declining does not.
_ASSERTIVE_KINDS = ("answer", "meta")
# The failure the golden set could not see: the table was right and the sentence about it was
# not. The runner writes it into the note; `failure_kind` reads it back out. Kept here because
# both sides need the same words and the EvalCase contract has no field for a failure kind.
NARRATION_FAILURE = "right table, wrong sentence"
# What the runner leaves in place of a holdout failure's reason when it was told to hide it.
# It lives here, not in the runner, because REPORT.md is rebuilt from whichever reports are on
# disk: a challenge pass re-renders the golden section and must not put a hidden reason back.
HIDDEN_NOTE = "Hidden during tuning so prompts cannot be fitted to the holdout questions."
_REPORT_FILES = {"golden": "report.json", "challenge": "challenge_report.json"}
_QUESTION_FILES = {"golden": "golden.yaml", "challenge": "challenge.yaml"}
MODELS_FILE = "models_used.json"  # which model answered what, written by the runner
EVAL_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- what the JSON cannot carry

# A row of the model comparison table says nothing about *when* it was measured, and a stale
# row beside a fresh one is the easiest way to read a report wrongly. One short phrase per
# model, shown in the table's "Measured on" column.
MODEL_NOTES: dict[str, str] = {
    "openai/gpt-oss-120b": "the code of 2026-09-20 18:05, before the combined-view and prompt changes",
    "gemma-4-31b-it": "the final code (combined views and the 12-rule generate prompt)",
}

# The eight classes a failure is reported in. Four can be read off the case; the other four
# are a reading of the SQL, so a pass that reads one records it here by id rather than typing
# it into REPORT.md, where the next run would drop it.
READ_FROM_THE_CASE = ("provider error", "wrong sentence", "over-refusal", "missed refusal")
READ_FROM_THE_SQL = ("wrong SQL logic", "wrong column", "date logic", "fan-out")
CLASSIFIED: dict[str, str] = {}

# The closing paragraph: what the failures say about the ceiling, and which model to default
# to. Rewritten by hand after each pass, rendered by code so it cannot fall off the page.
CEILING = ""


def report_filename(question_set: str) -> str:
    """Which file a set's report lives in. `--set challenge` must never overwrite the golden
    report, so the name is decided here rather than passed in by the caller."""
    return _REPORT_FILES[question_set]


def _flagged(question_set: str, key: str) -> set[str]:
    """Ids in one question file carrying a flag the report has to name. Read from the YAML
    rather than the report, because `EvalCase` has no field for "this question's sentence is
    graded" or "a prompt was changed because this one failed"."""
    try:
        raw = yaml.safe_load((EVAL_DIR / _QUESTION_FILES[question_set]).read_text(encoding="utf-8")) or []
    except (OSError, KeyError, yaml.YAMLError):
        return set()
    return {
        str(entry.get("id")) for entry in raw
        if isinstance(entry, dict)
        and (entry.get(key) or (entry.get("expect") or {}).get(key))
    }


def save_models_used(directory: Path, question_set: str, per_case: dict[str, list[tuple[str, str]]]) -> None:
    """Record which model filled which role, per question. Merged into whatever is already
    there, so a `--ids` pass updates only the questions it asked."""
    data = _models_used(directory)
    data.setdefault(question_set, {}).update({case_id: [list(pair) for pair in roles]
                                              for case_id, roles in per_case.items()})
    (directory / MODELS_FILE).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _models_used(directory: Path) -> dict[str, dict[str, list[list[str]]]]:
    try:
        return json.loads((directory / MODELS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def failure_kind(case: EvalCase) -> str:
    """Why this question failed, in a few words, so a reader can group the failures at a glance
    instead of reading six sentences to notice that three of them are the same problem."""
    if case.passed:
        return ""
    if NARRATION_FAILURE in case.note.casefold():
        return NARRATION_FAILURE
    if case.got_kind == "error":
        return "error"
    if case.got_kind != case.expected_kind:
        return f"{case.got_kind}, expected {case.expected_kind}"
    return "wrong result"


def failure_class(case: EvalCase) -> str:
    """Which of the eight classes this failure belongs to. A class recorded in `CLASSIFIED`
    wins, because only a person who read the SQL can tell a wrong column from date logic;
    everything else is read off the case itself."""
    if case.id in CLASSIFIED:
        return CLASSIFIED[case.id]
    if case.got_kind == "error":
        return "provider error"
    if NARRATION_FAILURE in case.note.casefold():
        return "wrong sentence"
    if case.got_kind == "refusal" and case.expected_kind != "refusal":
        return "over-refusal"
    if case.expected_kind == "refusal" and case.got_kind in _ASSERTIVE_KINDS:
        return "missed refusal"
    return "wrong SQL logic"  # the default until somebody reads the query and says otherwise


def trust_points(case: EvalCase) -> int:
    """+1 correct, 0 abstained (refused, asked, or errored), -1 wrong. An analyst can recover
    from "I can't answer that"; a confident wrong number in front of a CHRO is the real harm."""
    if case.passed:
        return 1
    return -1 if case.got_kind in _ASSERTIVE_KINDS else 0


def build_report(
    cases: list[EvalCase],
    *,
    model: str,
    runs: int,
    crosscheck_agreement: float | None,
    other_models: list[ModelScore],
    generated_at: str | None = None,
) -> EvalReport:
    """`other_models` is the comparison table from the previous report; this model's row is
    replaced and put first, so runs with different --chain values accumulate side by side."""
    timed = sorted(c.latency_ms for c in cases if c.latency_ms > 0)  # 0 = replayed from the LLM cache
    p50 = _percentile(timed, 0.50)
    accuracy = _accuracy(cases)
    categories = list(dict.fromkeys(c.category for c in cases))
    return EvalReport(
        generated_at=generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        model=model,
        runs=runs,
        total=len(cases),
        accuracy=accuracy,
        accuracy_holdout=_accuracy([c for c in cases if c.split == "holdout"]),
        trust_score=_mean([trust_points(c) for c in cases]),
        by_category={name: _accuracy([c for c in cases if c.category == name]) for name in categories},
        p50_ms=p50,
        p95_ms=_percentile(timed, 0.95),
        repair_rate=_mean([c.repairs > 0 for c in cases]),
        crosscheck_agreement=crosscheck_agreement,
        calibration={
            level: CalibrationBucket(n=len(bucket), accuracy=_accuracy(bucket))
            for level in LEVELS
            if (bucket := [c for c in cases if c.confidence == level])
        },
        models=[ModelScore(model=model, accuracy=accuracy, p50_ms=p50)]
        + [m for m in other_models if m.model != model],
        cases=cases,
    )


def load_report(path: Path) -> EvalReport | None:
    """The previous report, or None when there is none worth building on."""
    try:
        return EvalReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return None


def write_report(report: EvalReport, directory: Path, hide_holdout_failures: bool = False,
                 question_set: str = "golden") -> None:
    """Write this set's JSON, then rebuild REPORT.md from whichever of the two reports exist.

    Both sets share one readable report, so a challenge pass must not drop the golden section
    and a golden pass must not drop the challenge one. Each is read back off disk rather than
    remembered, which is also what makes `--set challenge` unable to touch eval/report.json."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / report_filename(question_set)).write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    golden = report if question_set == "golden" else load_report(directory / _REPORT_FILES["golden"])
    challenge = report if question_set == "challenge" else load_report(directory / _REPORT_FILES["challenge"])
    sections = [render_markdown(golden, hide_holdout_failures, directory) if golden else "",
                render_challenge(challenge, directory) if challenge else "",
                CEILING.strip() + "\n" if CEILING.strip() else ""]
    (directory / "REPORT.md").write_text("\n".join(s for s in sections if s), encoding="utf-8")


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def render_markdown(report: EvalReport, hide_holdout_failures: bool = False,
                    directory: Path = EVAL_DIR) -> str:
    cases = report.cases
    holdout = [c for c in cases if c.split == "holdout"]
    passed = sum(c.passed for c in cases)
    every_run = " in every run" if report.runs > 1 else ""

    lines = [
        "# Verity evaluation report",
        "",
        (f"Generated {report.generated_at} with `{report.model}`: {report.total} questions, "
         f"{report.runs} run(s) each. Expected answers are computed with pandas from the clean "
         "sample data, independently of the app."),
        "",
        "## Headline",
        "",
        (f"- **Accuracy: {report.accuracy:.1%}** ({passed} of {report.total} questions correct{every_run}). "
         f"By split: {_tally(cases, 'dev')} dev, {_tally(cases, 'holdout')} holdout."),
        _holdout_line(report, holdout),
        (f"- **Trust score: {report.trust_score:+.2f}** on a scale of -1 to +1 "
         "(+1 correct, 0 declined to answer, -1 gave a wrong answer)."),
        (f"- Speed: half of the questions finished within {_seconds(report.p50_ms)}, "
         f"95% within {_seconds(report.p95_ms)}. Questions replayed from the model cache are not timed."),
        f"- Repairs: {report.repair_rate:.1%} of questions needed the SQL to be corrected before it ran.",
        _crosscheck_line(report),
        _sentence_line(cases),
        "",
        "## Accuracy by category",
        "",
        "| Category | Questions | Correct | Accuracy |",
        "|---|---|---|---|",
    ]
    for name, accuracy in report.by_category.items():
        group = [c for c in cases if c.category == name]
        lines.append(f"| {name} | {len(group)} | {sum(c.passed for c in group)} | {accuracy:.1%} |")

    lines += [
        "",
        "## Is the confidence badge honest?",
        "",
        "A badge is only useful if High is right more often than Medium, and Medium more often than Low.",
        "",
        "| Badge | Questions | Accuracy |",
        "|---|---|---|",
    ]
    lines += [f"| {level.title()} | {b.n} | {b.accuracy:.1%} |" for level, b in report.calibration.items()]
    unbadged = sum(c.confidence is None for c in cases)
    if unbadged:
        lines += ["", f"{unbadged} question(s) carry no badge because the app refused, asked, or failed."]

    lines += ["", "## Model comparison", "",
              "| Model | Accuracy | Typical time | Measured on |", "|---|---|---|---|"]
    lines += [f"| `{m.model}` | {m.accuracy:.1%} | {_seconds(m.p50_ms)} | "
              f"{MODEL_NOTES.get(m.model, 'this question set')} |" for m in report.models]
    lines += _models_answered_lines("golden", cases, directory)

    lines += ["", "## Failures", ""] + _failure_lines(cases, hide_holdout_failures)
    lines += [
        "",
        "## Reproduce",
        "",
        "`PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split all --runs 3`",
        "",
    ]
    return "\n".join(lines)


def _tally(cases: list[EvalCase], split: str) -> str:
    group = [c for c in cases if c.split == split]
    return f"{sum(c.passed for c in group)} of {len(group)}"


def _sentence_line(cases: list[EvalCase], question_set: str = "golden") -> str:
    """The sentence is a second, separate failure class. It gets a headline line of its own
    because the table and the sentence can disagree and only one of them used to be graded."""
    graded = _flagged(question_set, "narration") & {c.id for c in cases}
    if not graded:
        return "- Only the result table is graded in this set; the sentence is graded in the golden set."
    wrong = [c.id for c in cases if not c.passed and failure_class(c) == "wrong sentence"]
    named = f" ({', '.join(wrong)})" if wrong else ""
    return (f"- **The sentence is graded too, not only the table:** {len(graded)} of the {len(cases)} "
            "questions must name the highest (and for one, the lowest) row of the expected result in "
            f"the answer text, and no clause may call a different row the highest. {len(wrong)} "
            f"failure(s) of that kind{named}. It is its own class because this set once scored 40/40 "
            'while the live app still said "Engineering has the highest average salary" over a table '
            "whose top row was Support (`DECISIONS.md` 20).")


def _models_answered_lines(question_set: str, cases: list[EvalCase], directory: Path) -> list[str]:
    """Which model filled which role, and for how many of these questions. Read from the calls
    the run actually made, never from the chain: a failover means the chain's first entry is
    not the model that replied."""
    per_case = _models_used(directory).get(question_set, {})
    tally: dict[tuple[str, str], int] = {}
    for case in cases:
        for pair in {(role, model) for role, model in per_case.get(case.id, [])}:
            tally[pair] = tally.get(pair, 0) + 1
    if not tally:
        return []
    return ["", "### Which models answered", "",
            (f"Counted over the {len(cases)} questions of this set by reading every call that was "
             "made, so a failover shows up as a second model on the same role."),
            "", "| Role | Model | Questions |", "|---|---|---|"] + [
        f"| {role} | `{model}` | {n} of {len(cases)} |"
        for (role, model), n in sorted(tally.items(), key=lambda item: (item[0][0], -item[1]))
    ]


def _holdout_line(report: EvalReport, holdout: list[EvalCase]) -> str:
    if not holdout:
        return "- Holdout questions have not been run yet, so there is no holdout accuracy to report."
    return (
        f"- **Holdout accuracy: {report.accuracy_holdout:.1%}** ({sum(c.passed for c in holdout)} of "
        f"{len(holdout)}). Holdout failures are never shown to the prompt-tuning loop, so this is "
        "the number that shows the prompts were not fitted to the test."
    )


def _crosscheck_line(report: EvalReport) -> str:
    if report.crosscheck_agreement is None:
        return "- Cross-check was off or unavailable in the latest pass, so there is no agreement rate."
    return (
        f"- Cross-check: a second model family reached the same result on "
        f"{report.crosscheck_agreement:.1%} of the answers it checked in the latest pass."
    )


def render_challenge(report: EvalReport, directory: Path = EVAL_DIR) -> str:
    """The challenge set's own section of REPORT.md: the score, then every failure, classified.

    Nothing is hidden and nothing is summarised away. The golden set is the regression bar; this
    section is the one that says how hard the app actually finds this data.

    The score is reported twice. A question a prompt was changed for after it failed is no
    longer evidence about unseen questions, so it is counted in the headline (it is still a
    question the app has to get right) and left out of the second number, which is the one
    that says what a never-tuned question costs."""
    cases = report.cases
    failures = [c for c in cases if not c.passed]
    tuned = _flagged("challenge", "tuned_after_failure") & {c.id for c in cases}
    untouched = [c for c in cases if c.id not in tuned]
    lines = [
        "## Challenge set (never tuned)",
        "",
        (f"{report.total} harder questions, written after the prompts were finished and never used to "
         f"change one. Run separately from the golden set. Generated {report.generated_at} with "
         f"`{report.model}`, {report.runs} run(s) each."),
        "",
        f"- **Accuracy: {report.accuracy:.1%}** ({report.total - len(failures)} of {report.total} correct).",
    ]
    if tuned:
        listed = ", ".join(f"`{case_id}`" for case_id in sorted(tuned))
        lines += [
            (f"- **Accuracy over the {len(untouched)} questions nothing was tuned on: "
             f"{_accuracy(untouched):.1%}** ({sum(c.passed for c in untouched)} of {len(untouched)})."),
            (f"- {listed} is reported as **tuned after failure**: it failed in an earlier pass and a "
             "rule was added to the generate prompt because of it, so its result is a measure of that "
             "rule and not of an unseen question. It is counted in the first number and left out of "
             "the second."),
        ]
    lines += [
        (f"- **Trust score: {report.trust_score:+.2f}** on the same scale as above "
         "(+1 correct, 0 declined to answer, -1 gave a wrong answer)."),
        (f"- Speed: half within {_seconds(report.p50_ms)}, 95% within {_seconds(report.p95_ms)}. "
         f"Repairs: {report.repair_rate:.1%}. {_crosscheck_line(report).lstrip('- ')}"),
        _sentence_line(cases, "challenge"),
    ]
    lines += _models_answered_lines("challenge", cases, directory)
    lines += ["", "### Every challenge failure", ""]
    if failures:
        lines += ["| Id | Category | Class | Kind of failure | Question | What happened |",
                  "|---|---|---|---|---|---|"]
        lines += [f"| {c.id} | {c.category} | {failure_class(c)} | {failure_kind(c)} | "
                  f"{_cell(c.question)} | {_cell(c.note)} |" for c in failures]
        lines += ["", (f"Classes: {', '.join(READ_FROM_THE_SQL)} (a reading of the query), "
                       f"{', '.join(READ_FROM_THE_CASE)} (read off the case itself). "
                       f"Classes with no failure this pass: "
                       f"{', '.join(c for c in READ_FROM_THE_SQL + READ_FROM_THE_CASE if c not in {failure_class(f) for f in failures})}.")]
    else:
        lines.append("None. Every challenge question passed.")
    lines += ["", "These questions were written to find where it breaks.", ""]
    return "\n".join(lines)


def _failure_lines(cases: list[EvalCase], hide_holdout: bool) -> list[str]:
    failures = [c for c in cases if not c.passed]
    # Either the caller asked to hide, or this row was written by a run that did: a report whose
    # reason is already gone must stay a count, whichever pass is rebuilding the page.
    hidden = [c for c in failures if c.split == "holdout" and (hide_holdout or c.note == HIDDEN_NOTE)]
    shown = [c for c in failures if c not in hidden]
    lines = []
    if shown:
        lines += ["| Id | Category | Split | Kind of failure | Question | Expected | Got | What happened |",
                  "|---|---|---|---|---|---|---|---|"]
        lines += [
            f"| {c.id} | {c.category} | {c.split} | {failure_kind(c)} | {_cell(c.question)} | "
            f"{c.expected_kind} | {c.got_kind} | {_cell(c.note)} |"
            for c in shown
        ]
    elif not hidden:
        lines.append("None. Every question passed.")
    if hidden:
        plural = "question" if len(hidden) == 1 else "questions"
        lines += ["", (f"{len(hidden)} holdout {plural} failed. The details are hidden during tuning so "
                       "prompts cannot be fitted to the holdout set; the final run lists them.")]
    return lines


def _cell(text: str) -> str:
    """Keep a table row on one line."""
    return " ".join(text.replace("|", "/").split())


def _seconds(ms: int) -> str:
    return f"{ms / 1000:.1f} s"


# --------------------------------------------------------------------------
# Arithmetic
# --------------------------------------------------------------------------


def _accuracy(cases: list[EvalCase]) -> float:
    return _mean([c.passed for c in cases])


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _percentile(sorted_values: list[int], fraction: float) -> int:
    """Nearest rank: the smallest value with at least `fraction` of the values at or below it.
    No interpolation, so the reported latency is one that actually happened."""
    if not sorted_values:
        return 0
    return sorted_values[max(0, math.ceil(fraction * len(sorted_values)) - 1)]
