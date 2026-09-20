"""Confidence from observable signals, with the reasons spelled out.

Why arithmetic and not a model's opinion: an analyst has to defend the badge in front of their
CHRO, so every point gained or lost is a fact about this run with a sentence attached. The
weights are judgement calls; the Trust Report's calibration table (accuracy within High,
Medium and Low on the golden questions) is how they are checked and where to retune them.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts import Confidence


@dataclass
class Signals:
    repairs: int = 0
    cross_check: str = "skipped"  # agreed | disagreed | unavailable | skipped
    fan_out: bool = False
    max_null_fraction: float = 0.0
    min_join_match: float = 1.0
    used_unconfirmed_link: bool = False
    narration_fallback: bool = False
    vetted_metric: bool = False
    truncated: bool = False
    assumptions: int = 0


def score(signals: Signals) -> Confidence:
    """Start at 0.8; agreed +0.15, vetted_metric +0.05; each repair -0.15; disagreed -0.35;
    fan_out -0.25; max_null_fraction >= 0.2 -0.1; min_join_match < 0.8 -0.15; unconfirmed link
    -0.1; narration fallback -0.05; truncated -0.05; assumptions >= 2 -0.05. Clamp 0..1.
    high >= 0.8, medium >= 0.55, else low. Every applied signal adds a plain-English reason.

    The cross-check reason comes first because it is the strongest evidence either way; the
    rest follow from the biggest deduction to the smallest."""
    s = signals
    repairs = "1 repair" if s.repairs == 1 else f"{s.repairs} repairs"
    # (applies, points, sentence), in the order the user reads them.
    checks: list[tuple[bool, float, str]] = [
        (s.cross_check == "agreed", 0.15, "A second model wrote its own query and got the same result."),
        (s.cross_check == "disagreed", -0.35,
         "A second model wrote its own query and got a different result, so check the SQL before relying on this."),
        (s.fan_out, -0.25, "A join may have counted some rows more than once."),
        (s.repairs > 0, -0.15 * s.repairs, f"The query needed {repairs} before it ran correctly."),
        (s.min_join_match < 0.8, -0.15,
         f"Only {s.min_join_match:.0%} of the keys matched between the joined files, so some rows were left out."),
        (s.max_null_fraction >= 0.2, -0.1, f"One of the columns used here is {s.max_null_fraction:.0%} empty."),
        (s.used_unconfirmed_link, -0.1, "The answer relies on a link between files that you have not confirmed yet."),
        (s.narration_fallback, -0.05,
         "The summary sentence came from a fixed template because the model's wording could not be verified."),
        (s.truncated, -0.05, "The result hit the row limit, so the table is incomplete."),
        (s.assumptions >= 2, -0.05, f"The question needed {s.assumptions} assumptions, listed under How I got this."),
        (s.repairs == 0, 0.0, "No repairs were needed: the first query ran cleanly."),
        (s.vetted_metric, 0.05, "It uses a vetted definition from your glossary."),
        (s.cross_check == "unavailable", 0.0, "The second-model cross-check could not run this time."),
    ]
    applied = [(points, sentence) for applies, points, sentence in checks if applies]
    # Rounded before the level is read: 0.8 - 0.15 - 0.1 is 0.5499... in floating point, and a
    # badge must not flip from medium to low on a representation error.
    total = round(min(1.0, max(0.0, 0.8 + sum(points for points, _ in applied))), 2)
    level = "high" if total >= 0.8 else "medium" if total >= 0.55 else "low"
    return Confidence(level=level, score=total, reasons=[sentence for _, sentence in applied])
