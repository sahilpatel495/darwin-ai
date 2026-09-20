"""Turn graded eval cases into the Trust Report (`report.json`) and its readable twin (`REPORT.md`).

Why every number is recomputed from the case list: the report can then be merged across
partial runs, rebuilt from `report.json` alone, and checked by hand. The one exception is
cross-check agreement, which is not stored per case and so describes the latest pass only.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from app.contracts import CalibrationBucket, EvalCase, EvalReport, ModelScore
from pydantic import ValidationError

LEVELS = ("high", "medium", "low")
# Kinds where the app asserted something. Being wrong here costs a point; declining does not.
_ASSERTIVE_KINDS = ("answer", "meta")


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


def write_report(report: EvalReport, directory: Path, hide_holdout_failures: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (directory / "REPORT.md").write_text(render_markdown(report, hide_holdout_failures), encoding="utf-8")


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def render_markdown(report: EvalReport, hide_holdout_failures: bool = False) -> str:
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
        f"- **Accuracy: {report.accuracy:.1%}** ({passed} of {report.total} questions correct{every_run}).",
        _holdout_line(report, holdout),
        (f"- **Trust score: {report.trust_score:+.2f}** on a scale of -1 to +1 "
         "(+1 correct, 0 declined to answer, -1 gave a wrong answer)."),
        (f"- Speed: half of the questions finished within {_seconds(report.p50_ms)}, "
         f"95% within {_seconds(report.p95_ms)}. Questions replayed from the model cache are not timed."),
        f"- Repairs: {report.repair_rate:.1%} of questions needed the SQL to be corrected before it ran.",
        _crosscheck_line(report),
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

    lines += ["", "## Model comparison", "", "| Model | Accuracy | Typical time |", "|---|---|---|"]
    lines += [f"| `{m.model}` | {m.accuracy:.1%} | {_seconds(m.p50_ms)} |" for m in report.models]

    lines += ["", "## Failures", ""] + _failure_lines(cases, hide_holdout_failures)
    lines += [
        "",
        "## Reproduce",
        "",
        "`PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split all --runs 3`",
        "",
    ]
    return "\n".join(lines)


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


def _failure_lines(cases: list[EvalCase], hide_holdout: bool) -> list[str]:
    failures = [c for c in cases if not c.passed]
    hidden = [c for c in failures if hide_holdout and c.split == "holdout"]
    shown = [c for c in failures if c not in hidden]
    lines = []
    if shown:
        lines += ["| Id | Category | Split | Question | Expected | Got | What happened |", "|---|---|---|---|---|---|---|"]
        lines += [
            f"| {c.id} | {c.category} | {c.split} | {_cell(c.question)} | {c.expected_kind} | {c.got_kind} | {_cell(c.note)} |"
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
